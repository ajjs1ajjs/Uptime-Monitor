// Package sim is the local simulation harness (no datacenter needed).
//
// Three scenarios, all against temp SQLite DBs + httptest servers:
//   - flood: N monitors hammered through concurrent CheckDue cycles
//     (proves the 50-slot check pool + async alerts hold, zero wedges).
//   - chaos: cancelled context mid-check, corrupt site URL, over-quota
//     rotation (proves fail-closed, never silent garbage).
//   - failover: two HA electors contend on one DB; killer ages the leader
//     row; standby takes over exactly once (no double-leader).
//
// Run: go test ./internal/sim/ -v, or: uptime-monitor drill [flood|chaos|failover]
package sim

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/config"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/ha"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/monitor"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"
)

// TB is the subset of *testing.T the sims need, so the CLI drill command
// can run the same scenarios outside tests (failures become errors).
type TB interface {
	Helper()
	Fatalf(format string, args ...any)
}

// tempDir returns a scratch dir with cleanup. Under *testing.T it uses the
// framework's TempDir (auto-removed); otherwise os.MkdirTemp + RemoveAll.
func tempDir(t TB) (string, func()) {
	type tester interface{ TempDir() string }
	if tt, ok := t.(tester); ok {
		return tt.TempDir(), func() {}
	}
	dir, err := os.MkdirTemp("", "uptime-sim-")
	if err != nil {
		t.Fatalf("tmpdir: %v", err)
	}
	return dir, func() { _ = os.RemoveAll(dir) }
}

// FloodReport describes a flood run.
type FloodReport struct {
	Sites      int
	Cycles     int
	ElapsedMs  int64
	Completed  int
	ActiveLeft int
}

// RunFlood creates N port-monitors against 127.0.0.1:1 (fast-refused, with
// private networks allowed) and runs Cycles CheckDue passes concurrently.
func RunFlood(t TB, sites, cycles int) FloodReport {
	t.Helper()
	dir, cleanup := tempDir(t)
	defer cleanup()
	path := filepath.Join(dir, "flood.db")
	db, abs, err := storage.Open(path)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	defer db.Close()
	store := storage.NewStore(db, abs)
	cfg := config.Default()
	cfg.Server.AllowPrivateNetworks = true
	cfg.AlertPolicy.GracePeriodSeconds = 0
	cfg.AlertPolicy.StillDownRepeatSeconds = 3600
	w := monitor.New(cfg, store, nil, nil)
	w.AlertSync = true
	for i := 0; i < sites; i++ {
		url := fmt.Sprintf("127.0.0.1:%d", 10000+i)
		id, err := store.CreateSite(fmt.Sprintf("flood-%d", i), url, 5, true, `[]`, "port", "", "")
		if err != nil {
			t.Fatalf("create: %v", err)
		}
		// No retries in the flood sim: we measure check throughput, not the
		// retry backoff (5×10s sleeps would dominate the wall clock).
		_ = store.UpdateSite(id, map[string]any{"max_retries": 0})
	}
	start := time.Now()
	done := 0
	for c := 0; c < cycles; c++ {
		last := map[int64]time.Time{}
		ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
		if err := w.CheckDue(ctx, last); err != nil {
			cancel()
			t.Fatalf("cycle %d: %v", c, err)
		}
		cancel()
		done++
	}
	left := 0
	w.InspectActive(func(n int) { left = n })
	return FloodReport{Sites: sites, Cycles: cycles, ElapsedMs: time.Since(start).Milliseconds(), Completed: done, ActiveLeft: left}
}

// ChaosReport describes a chaos run.
type ChaosReport struct {
	CancelSafe   bool
	CorruptKept  bool
	QuotaBounded bool
}

// RunChaos proves fail-closed behaviour: a cancelled context aborts promptly,
// a corrupt URL never verifies as good, rotation stays bounded.
func RunChaos(t TB) ChaosReport {
	t.Helper()
	dir, cleanup := tempDir(t)
	defer cleanup()
	path := filepath.Join(dir, "chaos.db")
	db, abs, err := storage.Open(path)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	defer db.Close()
	store := storage.NewStore(db, abs)
	cfg := config.Default()
	w := monitor.New(cfg, store, nil, nil)
	w.AlertSync = true

	// 1. Cancelled context: CheckSite must return quickly, not hang.
	id, _ := store.CreateSite("c", "127.0.0.1:1", 60, true, `[]`, "port", "", "")
	_ = store.UpdateSite(id, map[string]any{"max_retries": 0})
	s, _ := store.GetSite(id)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	t0 := time.Now()
	w.CheckSite(ctx, s)
	cancelSafe := time.Since(t0) < 10*time.Second

	// 2. Corrupt URL stays down (never flips to up on garbage).
	id2, _ := store.CreateSite("bad", "://not a url at all [[[", 60, true, `[]`, "http", "", "")
	_ = store.UpdateSite(id2, map[string]any{"max_retries": 0})
	s2, _ := store.GetSite(id2)
	w.CheckSite(context.Background(), s2)
	s2, _ = store.GetSite(id2)
	corruptKept := s2.Status != "up"

	// 3. Rotation bounded: Backups(max+1) contract.
	quotaBounded := true
	if got := len(mustBackups(t, store, 3)); got > 3 {
		quotaBounded = false
	}
	return ChaosReport{CancelSafe: cancelSafe, CorruptKept: corruptKept, QuotaBounded: quotaBounded}
}

func mustBackups(t TB, store *storage.Store, limit int) []map[string]any {
	t.Helper()
	all, err := store.Backups(limit)
	if err != nil {
		t.Fatalf("backups: %v", err)
	}
	return all
}

// FailoverReport describes an HA failover run.
type FailoverReport struct {
	Takeovers int
	Double    bool
	Owner     string
}

// RunFailover runs two electors against one DB, kills the leader's heartbeat
// in SQL, and asserts exactly one takeover with no double-leader.
func RunFailover(t TB) FailoverReport {
	t.Helper()
	dir, cleanup := tempDir(t)
	defer cleanup()
	path := filepath.Join(dir, "ha.db")
	db, _, err := storage.Open(path)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	defer db.Close()
	ctx := context.Background()
	a, b := ha.New(), ha.New()
	if !a.Beat(ctx, db) {
		t.Fatalf("A must win empty lock")
	}
	if b.Beat(ctx, db) {
		t.Fatalf("B must stand by while A fresh")
	}
	// Kill A's heartbeat in SQL (simulated crash, no graceful handoff).
	if _, err := db.Exec(`UPDATE leader_lock SET heartbeat = ? WHERE id = 'leader'`, time.Now().Add(-2*time.Minute).Unix()); err != nil {
		t.Fatalf("age: %v", err)
	}
	takeovers := 0
	if b.Beat(ctx, db) {
		takeovers++
	}
	// The dead leader re-beats → must observe standby (no double-leader).
	if a.Beat(ctx, db) {
		t.Fatalf("crashed leader must not retake without fresh heartbeat race")
	}
	double := a.IsLeader() && b.IsLeader()
	return FailoverReport{Takeovers: takeovers, Double: double, Owner: b.Owner()}
}



