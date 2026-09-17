// Package ha implements active-passive leader election over the shared
// application database (enterprise round).
//
// A single leader_lock row with a heartbeat. The node holding a fresh lock is
// the leader and runs the monitor worker + queue-adjacent jobs; standbys serve
// reads but refuse mutations (409 + X-Leader hint). TTL 45s, heartbeat 15s.
//
// Leadership is a *lease*, not a flag: a node only acts as leader while it is
// inside a TTL window it successfully renewed against the database. A
// transient database error therefore does not extend leadership - it just
// leaves the current lease running, and the node demotes itself when that
// lease runs out. This is the one property that keeps two nodes from both
// believing they are leader when the database briefly stops answering.
//
// The remaining split-brain window is bounded by clock skew between the nodes
// plus TTL; fencing is operator-driven (STONITH) for now - documented.
//
// IMPORTANT deployment note: "shared database" means a database both nodes can
// really lock. With the bundled SQLite driver that means a single host (two
// processes on one filesystem), NOT a file on NFS/CIFS - network filesystems
// do not implement POSIX locking reliably enough for this, and the lock row is
// exactly what has to be reliable. See README "High availability".
package ha

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"sync"
	"time"
)

const (
	// TTL bounds the split-brain window; Heartbeat is TTL/3, so a leader gets
	// two chances to renew before its lease lapses.
	TTL       = 45 * time.Second
	Heartbeat = 15 * time.Second
)

// Elector owns this node's identity and its current lease.
type Elector struct {
	mu     sync.RWMutex
	nodeID string
	leader bool
	owner  string
	// leaseUntil is when the leadership confirmed by the last successful
	// heartbeat expires. Zero means "never held a lease".
	leaseUntil time.Time
	// singleNode is set when the database has no leader_lock table at all
	// (a database written by a pre-HA version): there is nothing to contend
	// for, so this node is permanently the leader.
	singleNode bool
}

// New returns an elector with a unique node id. It starts as a standby: a
// node must earn leadership from the database before it acts on it, otherwise
// two freshly started nodes would both consider themselves leader for the
// window before their first heartbeat. Call Start (or Beat) before serving
// traffic - Start does the first round synchronously for exactly this reason.
func New() *Elector {
	host, _ := os.Hostname()
	if host == "" {
		host = "uptime"
	}
	if len(host) > 32 {
		host = host[:32]
	}
	var suffix [4]byte
	_, _ = rand.Read(suffix[:])
	return &Elector{nodeID: fmt.Sprintf("%s-%s", host, hex.EncodeToString(suffix[:]))}
}

// NodeID identifies this node in logs and the X-Leader hint.
func (e *Elector) NodeID() string { return e.nodeID }

// IsLeader reports whether this node currently holds a valid lease.
func (e *Elector) IsLeader() bool {
	e.mu.RLock()
	defer e.mu.RUnlock()
	if e.singleNode {
		return true
	}
	return e.leader && time.Now().Before(e.leaseUntil)
}

// Owner returns the last known lock owner.
func (e *Elector) Owner() string {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.owner
}

// promote records a lease confirmed by the database at time now.
func (e *Elector) promote(now time.Time, owner string) {
	e.mu.Lock()
	e.leader, e.owner, e.leaseUntil = true, owner, now.Add(TTL)
	e.mu.Unlock()
}

// demote records that another node owns the lock.
func (e *Elector) demote(owner string) {
	e.mu.Lock()
	e.leader, e.owner, e.leaseUntil = false, owner, time.Time{}
	e.mu.Unlock()
}

// holdLease is the answer to a database error: keep whatever lease is already
// running, but never extend it. A leader that cannot reach the database stops
// being leader once the window it last renewed has passed - it must not assume
// it still owns a lock it can no longer see.
func (e *Elector) holdLease(now time.Time, cause error) bool {
	e.mu.Lock()
	still := e.leader && now.Before(e.leaseUntil)
	if !still {
		e.leader = false
		e.leaseUntil = time.Time{}
	}
	remaining := e.leaseUntil.Sub(now)
	e.mu.Unlock()
	if still {
		slog.Warn("ha: heartbeat failed, holding lease", "error", cause, "expires_in", remaining.Round(time.Second))
	} else {
		slog.Error("ha: heartbeat failed and lease expired, standing down", "error", cause)
	}
	return still
}

// markSingleNode latches "this database has no lock table", so the check is
// not repeated on every heartbeat.
func (e *Elector) markSingleNode() {
	e.mu.Lock()
	e.singleNode, e.leader, e.owner = true, true, e.nodeID
	e.leaseUntil = time.Now().Add(365 * 24 * time.Hour)
	e.mu.Unlock()
}

// missingTable reports whether err means the leader_lock table does not exist,
// i.e. the database predates the HA migration. Every other error is treated as
// transient, which is the safe direction: a transient error must not be able to
// manufacture leadership.
func missingTable(err error) bool {
	return err != nil && strings.Contains(strings.ToLower(err.Error()), "no such table")
}

// Beat performs one heartbeat round: take the lock over when the row is
// missing, expired, or already ours. Returns true when this node holds a valid
// lease after the round.
func (e *Elector) Beat(ctx context.Context, db *sql.DB) bool {
	if e.isSingleNode() {
		return true
	}
	now := time.Now()
	res, err := db.ExecContext(ctx,
		`INSERT INTO leader_lock (id, owner, heartbeat) VALUES ('leader', ?, ?)
		 ON CONFLICT(id) DO UPDATE SET owner=excluded.owner, heartbeat=excluded.heartbeat
		 WHERE leader_lock.owner = ? OR leader_lock.heartbeat < ?`,
		e.nodeID, now.Unix(), e.nodeID, now.Unix()-int64(TTL.Seconds()))
	if err != nil {
		if missingTable(err) {
			// Database written by a pre-HA version: nothing to contend for.
			e.markSingleNode()
			return true
		}
		return e.holdLease(now, err)
	}
	if n, affErr := res.RowsAffected(); affErr == nil && n > 0 {
		e.promote(now, e.nodeID)
		return true
	}
	var owner string
	var hb int64
	if err := db.QueryRowContext(ctx,
		`SELECT owner, heartbeat FROM leader_lock WHERE id = 'leader'`).Scan(&owner, &hb); err != nil {
		if err == sql.ErrNoRows {
			// The row vanished between the upsert and this read (another node
			// rebuilding the table). Next heartbeat will settle it; until then
			// only an unexpired lease counts.
			return e.holdLease(now, fmt.Errorf("leader_lock row missing"))
		}
		if missingTable(err) {
			e.markSingleNode()
			return true
		}
		return e.holdLease(now, err)
	}
	if owner == e.nodeID {
		// Our own row, already fresh enough that the upsert's WHERE matched
		// nothing new: still ours.
		e.promote(now, owner)
		return true
	}
	e.demote(owner)
	return false
}

func (e *Elector) isSingleNode() bool {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.singleNode
}

// Start performs the first heartbeat synchronously and then heartbeats in the
// background until ctx ends. Doing the first round before the caller starts
// serving traffic is what keeps a starting node from answering as leader
// before the database has confirmed it.
func (e *Elector) Start(ctx context.Context, db *sql.DB) {
	e.Beat(ctx, db)
	go e.run(ctx, db)
}

// Run heartbeats until ctx ends. Prefer Start, which does the first round
// synchronously.
func (e *Elector) Run(ctx context.Context, db *sql.DB) {
	e.Beat(ctx, db)
	e.run(ctx, db)
}

func (e *Elector) run(ctx context.Context, db *sql.DB) {
	t := time.NewTicker(Heartbeat)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			e.Beat(ctx, db)
		}
	}
}
