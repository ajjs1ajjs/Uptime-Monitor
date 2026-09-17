package ha

import (
	"context"
	"database/sql"
	"path/filepath"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

// lockDB returns a database with the leader_lock table, matching the schema
// storage.Open creates.
func lockDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", "file:"+filepath.ToSlash(filepath.Join(t.TempDir(), "ha.db")))
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })
	if _, err := db.Exec(`CREATE TABLE leader_lock (
	  id TEXT PRIMARY KEY, owner TEXT NOT NULL, heartbeat INTEGER NOT NULL)`); err != nil {
		t.Fatalf("schema: %v", err)
	}
	return db
}

// bareDB has no leader_lock table: a database written by a pre-HA version.
func bareDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", "file:"+filepath.ToSlash(filepath.Join(t.TempDir(), "old.db")))
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })
	return db
}

// A node must earn leadership from the database. Starting out as leader meant
// two freshly booted nodes both acted as leader until their first heartbeat.
func TestNewStartsAsStandby(t *testing.T) {
	if New().IsLeader() {
		t.Fatalf("a brand new elector must not claim leadership before its first heartbeat")
	}
}

func TestBeatTakesAndHoldsTheLock(t *testing.T) {
	db := lockDB(t)
	ctx := context.Background()
	a, b := New(), New()

	if !a.Beat(ctx, db) {
		t.Fatalf("A must win an empty lock")
	}
	if !a.IsLeader() {
		t.Fatalf("A must report leadership after winning")
	}
	if b.Beat(ctx, db) {
		t.Fatalf("B must stand by while A's lease is fresh")
	}
	if b.Owner() != a.NodeID() {
		t.Errorf("B's owner hint = %q, want A's node id %q", b.Owner(), a.NodeID())
	}
	// Renewing our own lock keeps it, and does not hand it to anyone else.
	if !a.Beat(ctx, db) {
		t.Fatalf("A must keep its own lock on renewal")
	}
}

func TestTakeoverOnlyAfterTTL(t *testing.T) {
	db := lockDB(t)
	ctx := context.Background()
	a, b := New(), New()
	if !a.Beat(ctx, db) {
		t.Fatalf("A must win an empty lock")
	}
	// Age A's heartbeat past the TTL: a crash with no graceful handoff.
	if _, err := db.Exec(`UPDATE leader_lock SET heartbeat = ? WHERE id = 'leader'`,
		time.Now().Add(-2*TTL).Unix()); err != nil {
		t.Fatalf("age heartbeat: %v", err)
	}
	if !b.Beat(ctx, db) {
		t.Fatalf("B must take over an expired lock")
	}
	if a.Beat(ctx, db) {
		t.Fatalf("the crashed leader must not retake the lock while B is fresh")
	}
	if a.IsLeader() && b.IsLeader() {
		t.Fatalf("double leader")
	}
}

// The central regression: Beat used to set leader = true on *any* database
// error, so a transient failure (SQLITE_BUSY, lock timeout, I/O error) handed
// out leadership to whoever asked - including a standby, and including both
// nodes at once.
func TestTransientErrorNeverManufacturesLeadership(t *testing.T) {
	db := lockDB(t)
	ctx := context.Background()
	standby := New()

	// Another node owns a fresh lock.
	leader := New()
	if !leader.Beat(ctx, db) {
		t.Fatalf("leader must win the empty lock")
	}
	if standby.Beat(ctx, db) {
		t.Fatalf("standby must not win a fresh lock")
	}

	// Now the database stops answering.
	_ = db.Close()
	if standby.Beat(ctx, db) {
		t.Fatalf("a standby must stay a standby when the database errors")
	}
	if standby.IsLeader() {
		t.Fatalf("a standby must not report leadership after a database error")
	}
}

// A leader that loses the database keeps serving only for the remainder of the
// lease it actually renewed, then stands down.
func TestLeaderHoldsLeaseThenStandsDown(t *testing.T) {
	db := lockDB(t)
	ctx := context.Background()
	leader := New()
	if !leader.Beat(ctx, db) {
		t.Fatalf("leader must win the empty lock")
	}
	_ = db.Close()

	// Inside the renewed lease: keep going (a blip must not cause a flap).
	if !leader.Beat(ctx, db) {
		t.Fatalf("leader must hold its unexpired lease across a transient error")
	}
	if !leader.IsLeader() {
		t.Fatalf("leader must still report leadership inside its lease")
	}

	// Lease lapses with the database still unreachable: fail closed.
	leader.mu.Lock()
	leader.leaseUntil = time.Now().Add(-time.Second)
	leader.mu.Unlock()

	if leader.IsLeader() {
		t.Fatalf("an expired lease must not report leadership")
	}
	if leader.Beat(ctx, db) {
		t.Fatalf("leader must stand down once its lease expires without a renewal")
	}
}

// A database written before the HA migration has no lock table. That is
// single-node mode, not an error, and it must not wedge a working install.
func TestMissingTableMeansSingleNode(t *testing.T) {
	db := bareDB(t)
	e := New()
	if !e.Beat(context.Background(), db) {
		t.Fatalf("a database without leader_lock means single-node mode: leader")
	}
	if !e.IsLeader() {
		t.Fatalf("single-node mode must report leadership")
	}
	// Latched: no further queries, and no lease expiry either.
	e.mu.Lock()
	e.leaseUntil = time.Now().Add(-time.Hour)
	e.mu.Unlock()
	if !e.IsLeader() {
		t.Fatalf("single-node mode must not expire")
	}
}

func TestStartDoesFirstBeatSynchronously(t *testing.T) {
	db := lockDB(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	e := New()
	e.Start(ctx, db)
	// No sleep: Start must have settled leadership before returning.
	if !e.IsLeader() {
		t.Fatalf("Start must complete the first heartbeat before returning")
	}
}

func TestHeartbeatIsWellInsideTTL(t *testing.T) {
	// Two heartbeat attempts must fit in one lease, otherwise a single lost
	// round trip demotes a healthy leader.
	if Heartbeat*2 >= TTL {
		t.Fatalf("Heartbeat %v vs TTL %v leaves no room for a retry", Heartbeat, TTL)
	}
}
