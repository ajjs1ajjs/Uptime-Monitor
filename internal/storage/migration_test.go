package storage

import (
	"database/sql"
	"path/filepath"
	"testing"
	"time"
)

// Simulates upgrading a real 3.6.x database: rows written in the old
// Kyiv-offset format, then Open() runs the migration on it.
func TestUpgradeFromLegacyDatabase(t *testing.T) {
	path := filepath.Join(t.TempDir(), "legacy.db")

	// First boot writes the schema, then we plant legacy-format rows.
	db, abs, err := Open(path)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	st := NewStore(db, abs)
	uid, _ := st.CreateUser("legacy", "hash", "admin")
	_, _ = st.CreateSite("s", "https://example.com", 60, true, "[]", "http", "", "[]")

	legacyNow := time.Now().In(kyivLoc).Format("2006-01-02T15:04:05.000000-07:00")
	legacyExpired := time.Now().Add(-2 * time.Hour).In(kyivLoc).Format("2006-01-02T15:04:05.000000-07:00")
	legacyValid := time.Now().Add(48 * time.Hour).In(kyivLoc).Format("2006-01-02T15:04:05.000000-07:00")
	mustExec := func(q string, args ...any) {
		if _, err := db.Exec(q, args...); err != nil {
			t.Fatalf("%s: %v", q, err)
		}
	}
	mustExec(`INSERT INTO sessions (user_id, session_id, created_at, expires_at) VALUES (?,?,?,?)`,
		uid, "legacy-expired", legacyNow, legacyExpired)
	mustExec(`INSERT INTO sessions (user_id, session_id, created_at, expires_at) VALUES (?,?,?,?)`,
		uid, "legacy-valid", legacyNow, legacyValid)
	mustExec(`INSERT INTO status_history (site_id, status, checked_at) VALUES (1,'up',?)`, legacyNow)
	mustExec(`INSERT INTO audit_log (username, action, created_at) VALUES ('legacy','login',?)`, legacyNow)
	_ = db.Close()

	// Second boot: the migration must run against the existing file.
	db2, abs2, err := Open(path)
	if err != nil {
		t.Fatalf("reopen: %v", err)
	}
	defer db2.Close()
	st2 := NewStore(db2, abs2)

	var nonCanonical int
	if err := db2.QueryRow(`SELECT COUNT(*) FROM (
	    SELECT expires_at v FROM sessions
	    UNION ALL SELECT checked_at FROM status_history
	    UNION ALL SELECT created_at FROM audit_log)
	  WHERE v LIKE '____-__-__T%' AND v NOT LIKE '%Z'`).Scan(&nonCanonical); err != nil {
		t.Fatalf("count: %v", err)
	}
	if nonCanonical != 0 {
		t.Errorf("%d legacy timestamps survived the migration", nonCanonical)
	}

	// The expired legacy session must now actually be rejected...
	if u, err := st2.GetSession("legacy-expired"); err != nil {
		t.Fatalf("get expired: %v", err)
	} else if u != nil {
		t.Errorf("an expired legacy session is still accepted after the upgrade")
	}
	// ...and the valid one must survive the upgrade (no forced re-login).
	if u, err := st2.GetSession("legacy-valid"); err != nil {
		t.Fatalf("get valid: %v", err)
	} else if u == nil {
		t.Errorf("a valid legacy session was invalidated by the upgrade")
	}

	// And the migrated history row is still readable and inside the window.
	var got sql.NullString
	if err := db2.QueryRow(`SELECT checked_at FROM status_history`).Scan(&got); err != nil {
		t.Fatalf("read history: %v", err)
	}
	ts, err := ParseTime(got.String)
	if err != nil {
		t.Fatalf("ParseTime(%q): %v", got.String, err)
	}
	if d := time.Since(ts); d < 0 || d > time.Minute {
		t.Errorf("migrated timestamp %q is %v away from now", got.String, d)
	}
	if got.String <= Since(30*day) {
		t.Errorf("migrated row %q falls outside the 30-day retention window", got.String)
	}
}
