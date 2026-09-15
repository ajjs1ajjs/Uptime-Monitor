// Package ha implements active-passive leader election over the shared
// SQLite/Postgres database (enterprise round).
//
// A single leader_lock row with heartbeat. The node holding a fresh lock is
// the leader and runs the monitor worker + queue-adjacent jobs; standbys
// serve reads but refuse mutations (409 + X-Leader hint). TTL 45s, heartbeat
// 15s. Split-brain window is bounded by clock skew + TTL; fencing is
// operator-driven (STONITH) for now — documented.
package ha

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"fmt"
	"os"
	"sync"
	"time"
)

const (
	// TTL bounds the split-brain window; Heartbeat is TTL/3.
	TTL       = 45 * time.Second
	Heartbeat = 15 * time.Second
)

// Elector owns this node's identity and cached leadership flag.
type Elector struct {
	mu     sync.RWMutex
	nodeID string
	leader bool
	owner  string
}

// New returns an elector with a unique node id.
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
	return &Elector{nodeID: fmt.Sprintf("%s-%s", host, hex.EncodeToString(suffix[:])), leader: true}
}

// NodeID identifies this node in logs and the X-Leader hint.
func (e *Elector) NodeID() string { return e.nodeID }

// IsLeader reports the cached flag (true until the first heartbeat says no,
// so single-node and pre-migration DBs behave as leader).
func (e *Elector) IsLeader() bool {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.leader
}

// Owner returns the last known lock owner.
func (e *Elector) Owner() string {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.owner
}

// set updates the cache.
func (e *Elector) set(leader bool, owner string) {
	e.mu.Lock()
	e.leader, e.owner = leader, owner
	e.mu.Unlock()
}

// Beat performs one heartbeat round: take over when the row is missing,
// expired, or ours. Returns true when this node is leader after the round.
// Missing table (old DB) means single-node mode: leader.
func (e *Elector) Beat(ctx context.Context, db *sql.DB) bool {
	now := time.Now().Unix()
	res, err := db.ExecContext(ctx,
		`INSERT INTO leader_lock (id, owner, heartbeat) VALUES ('leader', ?, ?)
		 ON CONFLICT(id) DO UPDATE SET owner=excluded.owner, heartbeat=excluded.heartbeat
		 WHERE leader_lock.owner = ? OR leader_lock.heartbeat < ?`,
		e.nodeID, now, e.nodeID, now-int64(TTL.Seconds()))
	if err != nil {
		// Old DB without the migration (or a driver that rejects the
		// upsert): stay leader rather than wedge a working single node.
		e.set(true, e.nodeID)
		return true
	}
	if n, _ := res.RowsAffected(); n > 0 {
		e.set(true, e.nodeID)
		return true
	}
	var owner string
	var hb int64
	if err := db.QueryRowContext(ctx, `SELECT owner, heartbeat FROM leader_lock WHERE id = 'leader'`).Scan(&owner, &hb); err != nil {
		e.set(true, e.nodeID)
		return true
	}
	if owner == e.nodeID {
		e.set(true, owner)
		return true
	}
	e.set(false, owner)
	return false
}

// Run heartbeats until ctx ends.
func (e *Elector) Run(ctx context.Context, db *sql.DB) {
	t := time.NewTicker(Heartbeat)
	defer t.Stop()
	e.Beat(ctx, db)
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			e.Beat(ctx, db)
		}
	}
}
