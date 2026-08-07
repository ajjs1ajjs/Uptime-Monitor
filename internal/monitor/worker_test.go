package monitor

import (
	"path/filepath"
	"testing"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/config"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"
)

type fakeAlert struct {
	alerts []map[string]any
}

func (f *fakeAlert) Dispatch(alertType, message string, alert map[string]any) {
	f.alerts = append(f.alerts, alert)
}

type fakeWS struct{}

func (fakeWS) Broadcast(event map[string]any) {}

func newTestWorker(t *testing.T, grace int) (*Worker, *storage.Store, *fakeAlert) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "test.db")
	db, abs, err := storage.Open(path)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })
	store := storage.NewStore(db, abs)
	cfg := config.Default()
	cfg.AlertPolicy.GracePeriodSeconds = grace
	cfg.AlertPolicy.UpSuccessThreshold = 1
	cfg.AlertPolicy.StillDownRepeatSeconds = 600
	fake := &fakeAlert{}
	w := New(cfg, store, fakeWS{}, fake)
	return w, store, fake
}

// TestGracePeriodAlertsOnLaterCheck verifies the regression where with
// grace_period_seconds > 0 a site that just went down never triggered an alert:
// the first check waited for the grace period, but the next checks required
// LastDownAlert to be non-nil and therefore never fired the initial "down".
func TestGracePeriodAlertsOnLaterCheck(t *testing.T) {
	w, store, fake := newTestWorker(t, 30)

	id, err := store.CreateSite("srv", "https://example.com", 60, true, `["telegram"]`, "http", "", "")
	if err != nil {
		t.Fatalf("add: %v", err)
	}

	// first failure: prev=up, inside grace period -> no alert yet
	s, _ := store.GetSite(id)
	s.Status = "up"
	s.FirstFailureAt = nil
	s.LastDownAlert = nil
	w.persist(s, "down", 504, 100, "HTTP 504")

	if len(fake.alerts) != 0 {
		t.Fatalf("expected no alert during grace period, got %d", len(fake.alerts))
	}

	// simulate the grace period elapsing: push first_failure_at back in time
	old := time.Now().UTC().Add(-60 * time.Second).Format("2006-01-02T15:04:05.999999-07:00")
	if err := store.UpdateSite(id, map[string]any{"first_failure_at": old}); err != nil {
		t.Fatalf("update: %v", err)
	}

	// later check: still down, prev=down, no alert ever fired -> fire now
	// that the grace period has elapsed (FirstFailureAt is in the past)
	s, _ = store.GetSite(id)
	w.persist(s, "down", 504, 100, "HTTP 504")

	if len(fake.alerts) != 1 {
		t.Fatalf("expected 1 alert after grace elapsed, got %d", len(fake.alerts))
	}
	if fake.alerts[0]["alert_type"] != "down" {
		t.Fatalf("alert type = %v, want down", fake.alerts[0]["alert_type"])
	}

	// repeated check inside the repeat window -> still_down not sent yet
	s, _ = store.GetSite(id)
	w.persist(s, "down", 504, 100, "HTTP 504")
	if len(fake.alerts) != 1 {
		t.Fatalf("expected no still_down before repeat window, got %d", len(fake.alerts))
	}
}

// TestGraceZeroAlertsImmediately verifies grace_period_seconds=0 alerts on the
// very first failing check (previous behaviour).
func TestGraceZeroAlertsImmediately(t *testing.T) {
	w, store, fake := newTestWorker(t, 0)

	id, err := store.CreateSite("srv", "https://example.com", 60, true, `["telegram"]`, "http", "", "")
	if err != nil {
		t.Fatalf("add: %v", err)
	}

	s, _ := store.GetSite(id)
	w.persist(s, "down", 500, 100, "HTTP 500")

	if len(fake.alerts) != 1 {
		t.Fatalf("expected immediate alert with grace=0, got %d", len(fake.alerts))
	}
	if fake.alerts[0]["alert_type"] != "down" {
		t.Fatalf("alert type = %v, want down", fake.alerts[0]["alert_type"])
	}
}

// TestStillDownRepeat verifies the still_down alert repeats after
// StillDownRepeatSeconds.
func TestStillDownRepeat(t *testing.T) {
	w, store, fake := newTestWorker(t, 0)

	id, err := store.CreateSite("srv", "https://example.com", 60, true, `["telegram"]`, "http", "", "")
	if err != nil {
		t.Fatalf("add: %v", err)
	}

	s, _ := store.GetSite(id)
	// mark the site as already down with a recent alert so the first persist
	// is a repeat check, not a fresh failure
	_ = store.UpdateSite(id, map[string]any{"status": "down"})
	s, _ = store.GetSite(id)
	now := storage.Now()
	s.LastDownAlert = &now
	s.FirstFailureAt = &now
	w.persist(s, "down", 500, 100, "HTTP 500")
	if len(fake.alerts) != 0 {
		t.Fatalf("expected no alert inside repeat window, got %d", len(fake.alerts))
	}

	// simulate elapsed repeat window
	old := time.Now().UTC().Add(-700 * time.Second).Format("2006-01-02T15:04:05.999999-07:00")
	s, _ = store.GetSite(id)
	s.LastDownAlert = &old
	s.FirstFailureAt = &old
	w.persist(s, "down", 500, 100, "HTTP 500")
	if len(fake.alerts) != 1 {
		t.Fatalf("expected still_down after repeat window, got %d", len(fake.alerts))
	}
	if fake.alerts[0]["alert_type"] != "still_down" {
		t.Fatalf("alert type = %v, want still_down", fake.alerts[0]["alert_type"])
	}
}
