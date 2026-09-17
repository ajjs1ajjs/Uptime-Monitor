package storage

import (
	"path/filepath"
	"testing"
	"time"
)

func newTestStore(t *testing.T) *Store {
	t.Helper()
	db, abs, err := Open(filepath.Join(t.TempDir(), "sites.db"))
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })
	return NewStore(db, abs)
}

// Regression: expires_at was written as Kyiv local time with an offset but
// compared against SQLite's datetime('now') (UTC, space separator). The string
// comparison hit 'T' vs ' ' at index 10 and 'T' always wins, so a session
// stayed valid until midnight UTC after its expiry.
func TestSessionExpiresOnTime(t *testing.T) {
	st := newTestStore(t)
	uid, err := st.CreateUser("alice", "hash", "admin")
	if err != nil {
		t.Fatalf("create user: %v", err)
	}

	for _, tc := range []struct {
		name    string
		expires time.Time
		want    bool
	}{
		{"expired an hour ago", time.Now().Add(-time.Hour), false},
		{"expired a second ago", time.Now().Add(-time.Second), false},
		{"expired yesterday", time.Now().Add(-25 * time.Hour), false},
		{"valid for another hour", time.Now().Add(time.Hour), true},
		{"valid for another week", time.Now().Add(7 * 24 * time.Hour), true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			sid := "sess-" + tc.name
			if err := st.CreateSession(uid, sid, tc.expires); err != nil {
				t.Fatalf("create session: %v", err)
			}
			u, err := st.GetSession(sid)
			if err != nil {
				t.Fatalf("get session: %v", err)
			}
			if got := u != nil; got != tc.want {
				t.Fatalf("session accepted = %v, want %v (expires_at %s, now %s)",
					got, tc.want, TimeString(tc.expires), Now())
			}
		})
	}
}

// Cleanup must actually delete expired sessions, for the same reason.
func TestCleanupDeletesExpiredSessions(t *testing.T) {
	st := newTestStore(t)
	uid, _ := st.CreateUser("bob", "hash", "viewer")
	_ = st.CreateSession(uid, "stale", time.Now().Add(-time.Hour))
	_ = st.CreateSession(uid, "fresh", time.Now().Add(time.Hour))

	if err := st.Cleanup(); err != nil {
		t.Fatalf("cleanup: %v", err)
	}
	var n int
	if err := st.DB.QueryRow(`SELECT COUNT(*) FROM sessions WHERE session_id = 'stale'`).Scan(&n); err != nil {
		t.Fatalf("count: %v", err)
	}
	if n != 0 {
		t.Errorf("expired session survived Cleanup")
	}
	if err := st.DB.QueryRow(`SELECT COUNT(*) FROM sessions WHERE session_id = 'fresh'`).Scan(&n); err != nil {
		t.Fatalf("count: %v", err)
	}
	if n != 1 {
		t.Errorf("valid session was deleted by Cleanup")
	}
}

// Retention cutoffs are string comparisons against a canonical timestamp, so
// verify both sides of each boundary rather than trusting the format.
func TestCleanupRetentionBoundaries(t *testing.T) {
	st := newTestStore(t)
	if _, err := st.CreateSite("s", "https://example.com", 60, true, "[]", "http", "", "[]"); err != nil {
		t.Fatalf("create site: %v", err)
	}
	insert := func(ts string) {
		if _, err := st.DB.Exec(
			`INSERT INTO status_history (site_id, status, checked_at) VALUES (1,'up',?)`, ts); err != nil {
			t.Fatalf("insert history: %v", err)
		}
	}
	insert(Since(31 * day)) // outside the 30-day window
	insert(Since(29 * day)) // inside
	insert(Now())           // inside

	if err := st.Cleanup(); err != nil {
		t.Fatalf("cleanup: %v", err)
	}
	var n int
	if err := st.DB.QueryRow(`SELECT COUNT(*) FROM status_history`).Scan(&n); err != nil {
		t.Fatalf("count: %v", err)
	}
	if n != 2 {
		t.Fatalf("status_history rows after cleanup = %d, want 2 (only the 31-day-old row removed)", n)
	}
}

// migrateTimestamps must rewrite rows written by older versions (Kyiv local
// time with an offset) into canonical UTC, so old and new rows compare
// correctly against each other, and must leave already-canonical rows alone.
func TestMigrateTimestampsNormalizesLegacyRows(t *testing.T) {
	st := newTestStore(t)
	_, _ = st.CreateSite("s", "https://example.com", 60, true, "[]", "http", "", "[]")

	const legacy = "2026-09-17T12:00:00.123456+03:00" // == 09:00:00 UTC
	const canonical = "2026-09-17T09:00:00.000000Z"
	_, _ = st.DB.Exec(`INSERT INTO status_history (site_id, status, checked_at) VALUES (1,'up',?)`, legacy)
	_, _ = st.DB.Exec(`INSERT INTO status_history (site_id, status, checked_at) VALUES (1,'up',?)`, canonical)

	if err := migrateTimestamps(st.DB); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	rows, err := st.DB.Query(`SELECT checked_at FROM status_history ORDER BY id`)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	defer rows.Close()
	var got []string
	for rows.Next() {
		var v string
		if err := rows.Scan(&v); err != nil {
			t.Fatalf("scan: %v", err)
		}
		got = append(got, v)
	}
	if len(got) != 2 {
		t.Fatalf("rows = %d, want 2", len(got))
	}
	// Sub-millisecond precision is dropped by SQLite's %f, which is fine.
	if got[0] != "2026-09-17T09:00:00.123000Z" {
		t.Errorf("legacy row = %q, want the same instant in canonical UTC", got[0])
	}
	if got[1] != canonical {
		t.Errorf("canonical row was rewritten: %q (migration must be idempotent)", got[1])
	}
	// Both rows must now parse and land on the same UTC day/hour.
	for _, v := range got {
		ts, err := ParseTime(v)
		if err != nil {
			t.Fatalf("ParseTime(%q): %v", v, err)
		}
		if ts.UTC().Hour() != 9 {
			t.Errorf("ParseTime(%q) hour = %d, want 9 UTC", v, ts.UTC().Hour())
		}
	}
}

func TestParseTimeAcceptsLegacyAndCanonicalFormats(t *testing.T) {
	// Same instant, every format this project has ever written or accepted.
	want := time.Date(2026, 9, 17, 9, 0, 0, 0, time.UTC)
	for _, in := range []string{
		"2026-09-17T09:00:00.000000Z",
		"2026-09-17T09:00:00Z",
		"2026-09-17T12:00:00.000000+03:00",
		"2026-09-17T12:00:00+03:00",
	} {
		got, err := ParseTime(in)
		if err != nil {
			t.Fatalf("ParseTime(%q): %v", in, err)
		}
		if !got.Equal(want) {
			t.Errorf("ParseTime(%q) = %v, want %v", in, got.UTC(), want)
		}
	}
	// Zone-less values mean Kyiv local time (that is what wrote them).
	got, err := ParseTime("2026-09-17T12:00:00")
	if err != nil {
		t.Fatalf("ParseTime zone-less: %v", err)
	}
	if !got.Equal(want) {
		t.Errorf("zone-less value = %v, want it read as Kyiv local (%v)", got.UTC(), want)
	}
	if _, err := ParseTime("not a timestamp"); err == nil {
		t.Errorf("ParseTime accepted garbage")
	}
	if _, err := ParseTime(""); err == nil {
		t.Errorf("ParseTime accepted an empty string")
	}
}

// Now() is the format every comparison depends on; assert it explicitly so a
// well-meaning change to the layout fails loudly here.
func TestNowIsCanonicalUTC(t *testing.T) {
	now := Now()
	if len(now) != len("2026-09-17T09:00:00.000000Z") || now[len(now)-1] != 'Z' {
		t.Fatalf("Now() = %q, want canonical UTC RFC3339 with microseconds", now)
	}
	ts, err := time.Parse(TimeLayout, now)
	if err != nil {
		t.Fatalf("Now() not parseable with TimeLayout: %v", err)
	}
	if d := time.Since(ts); d < 0 || d > time.Minute {
		t.Fatalf("Now() is %v away from time.Now()", d)
	}
	// Lexicographic order must match chronological order — that is the whole
	// point of the format.
	if !(Since(time.Hour) < now) {
		t.Fatalf("Since(1h)=%q is not lexicographically before Now()=%q", Since(time.Hour), now)
	}
}
