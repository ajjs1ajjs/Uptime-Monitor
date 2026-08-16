package storage

import (
	"database/sql"
	"os"
	"path/filepath"
	"strings"
	"testing"

	_ "modernc.org/sqlite"
)

// oldSchema mimics the sites/ssl_certificates tables as written by the
// Python/FastAPI backend (v2.x), which lack the columns added later in Go.
const oldSchema = `
CREATE TABLE sites (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
  check_interval INTEGER DEFAULT 60, is_active BOOLEAN DEFAULT 1,
  last_notification TEXT, notify_methods TEXT DEFAULT '[]',
  status TEXT DEFAULT 'unknown', status_code INTEGER, response_time REAL,
  error_message TEXT, monitor_type TEXT DEFAULT 'http',
  failed_attempts INTEGER DEFAULT 0, success_attempts INTEGER DEFAULT 0,
  last_down_alert TEXT, keyword TEXT DEFAULT NULL, tags TEXT DEFAULT '[]'
);
CREATE TABLE ssl_certificates (
  id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER UNIQUE, hostname TEXT,
  issuer TEXT, subject TEXT, start_date TEXT, expire_date TEXT,
  days_until_expire INTEGER, is_valid BOOLEAN, last_checked TEXT,
  last_notified TEXT
);
`

func columns(t *testing.T, db *sql.DB, table string) map[string]bool {
	t.Helper()
	rows, err := db.Query(`PRAGMA table_info(` + table + `)`)
	if err != nil {
		t.Fatalf("pragma %s: %v", table, err)
	}
	defer rows.Close()
	cols := map[string]bool{}
	for rows.Next() {
		var cid, name, ctype string
		var notnull, pk int
		var dflt any
		if err := rows.Scan(&cid, &name, &ctype, &notnull, &dflt, &pk); err != nil {
			t.Fatalf("scan: %v", err)
		}
		cols[name] = true
	}
	return cols
}

func TestOpenMigratesOldSchema(t *testing.T) {
	path := filepath.Join(t.TempDir(), "sites.db")

	db, err := sql.Open("sqlite", "file:"+path)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	if _, err := db.Exec(oldSchema); err != nil {
		t.Fatalf("create old schema: %v", err)
	}
	db.Close()

	// Open() applies the current schema AND migrates the missing columns.
	migrated, _, err := Open(path)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer migrated.Close()

	siteCols := columns(t, migrated, "sites")
	for _, col := range []string{"request_timeout_seconds", "retry_interval_seconds", "max_retries", "up_success_threshold", "first_failure_at", "silenced_until", "acknowledged"} {
		if !siteCols[col] {
			t.Errorf("sites is missing migrated column %q", col)
		}
	}
	sslCols := columns(t, migrated, "ssl_certificates")
	if !sslCols["ssl_notified_thresholds"] {
		t.Errorf("ssl_certificates is missing migrated column %q", "ssl_notified_thresholds")
	}

	// Existing rows must remain valid after the migration.
	if _, err := migrated.Exec(`INSERT INTO sites (name, url) VALUES ('a', 'https://example.com')`); err != nil {
		t.Errorf("insert after migration: %v", err)
	}
	var timeout, retryInterval, maxRetries, upThreshold int
	if err := migrated.QueryRow(`SELECT request_timeout_seconds, retry_interval_seconds, max_retries, up_success_threshold FROM sites WHERE name = 'a'`).Scan(&timeout, &retryInterval, &maxRetries, &upThreshold); err != nil {
		t.Fatalf("read migrated monitor policy: %v", err)
	}
	if timeout != 30 || retryInterval != 20 || maxRetries != 3 || upThreshold != 2 {
		t.Fatalf("migrated monitor policy = %d/%d/%d/%d, want 30/20/3/2", timeout, retryInterval, maxRetries, upThreshold)
	}

	// Re-opening must be idempotent.
	again, _, err := Open(path)
	if err != nil {
		t.Fatalf("second Open: %v", err)
	}
	defer again.Close()
	if !columns(t, again, "sites")["acknowledged"] {
		t.Errorf("second Open lost migrated columns")
	}
}

// preFKSchema mimics tables as created before REFERENCES clauses were added:
// no FK, so orphan rows (a site_id/user_id pointing at nothing) can exist.
const preFKSchema = `
CREATE TABLE sites (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE
);
CREATE TABLE status_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER, status TEXT,
  status_code INTEGER, response_time REAL, error_message TEXT, checked_at TEXT
);
CREATE TABLE ssl_certificates (
  id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER UNIQUE, hostname TEXT,
  issuer TEXT, subject TEXT, start_date TEXT, expire_date TEXT,
  days_until_expire INTEGER, is_valid BOOLEAN, last_checked TEXT,
  last_notified TEXT, ssl_notified_thresholds TEXT DEFAULT '[]'
);
CREATE TABLE notification_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER, site_name TEXT,
  method TEXT, status TEXT, message_preview TEXT, sent_at TEXT
);
CREATE TABLE maintenance_windows (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, site_id INTEGER,
  rule_type TEXT DEFAULT 'one_off', start_time TEXT, end_time TEXT,
  day_of_week INTEGER, start_hour_minute TEXT, duration_minutes INTEGER,
  is_active BOOLEAN DEFAULT 1
);
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT DEFAULT 'viewer',
  must_change_password BOOLEAN DEFAULT 0, created_at TEXT, last_login TEXT,
  password_encrypted TEXT
);
CREATE TABLE sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, session_id TEXT UNIQUE,
  created_at TEXT, expires_at TEXT
);
CREATE TABLE api_keys (
  key_id TEXT PRIMARY KEY, user_id INTEGER, name TEXT,
  key_hash TEXT NOT NULL, created_at TEXT, last_used_at TEXT,
  is_active INTEGER DEFAULT 1
);
`

// TestOpenAddsForeignKeysAndDropsOrphans verifies the table-rebuild migration
// that retrofits REFERENCES clauses onto databases created before FK
// constraints existed: pre-existing orphan rows (referencing a deleted/never
// -existing parent) must be dropped rather than block the migration, valid
// rows must survive with their data intact, and the FK must actually be
// enforced afterwards (cascade delete works, inserting a new orphan fails).
func TestOpenAddsForeignKeysAndDropsOrphans(t *testing.T) {
	path := filepath.Join(t.TempDir(), "sites.db")

	setup, err := sql.Open("sqlite", "file:"+path)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	if _, err := setup.Exec(preFKSchema); err != nil {
		t.Fatalf("create pre-FK schema: %v", err)
	}
	if _, err := setup.Exec(`INSERT INTO sites (id, name, url) VALUES (1, 'kept', 'https://example.com')`); err != nil {
		t.Fatalf("seed site: %v", err)
	}
	// A valid row (site_id=1 exists) and an orphan row (site_id=999 does not).
	if _, err := setup.Exec(`INSERT INTO status_history (site_id, status, checked_at) VALUES (1, 'up', 'now'), (999, 'down', 'now')`); err != nil {
		t.Fatalf("seed status_history: %v", err)
	}
	if _, err := setup.Exec(`INSERT INTO ssl_certificates (site_id, hostname) VALUES (999, 'orphan.example.com')`); err != nil {
		t.Fatalf("seed ssl_certificates: %v", err)
	}
	if _, err := setup.Exec(`INSERT INTO users (id, username, password_hash) VALUES (1, 'admin', 'hash')`); err != nil {
		t.Fatalf("seed user: %v", err)
	}
	if _, err := setup.Exec(`INSERT INTO sessions (user_id, session_id, created_at, expires_at) VALUES (1, 'tok-kept', 'now', 'later'), (999, 'tok-orphan', 'now', 'later')`); err != nil {
		t.Fatalf("seed sessions: %v", err)
	}
	setup.Close()

	db, _, err := Open(path)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer db.Close()

	// Orphans must be gone, valid rows must survive.
	var count int
	if err := db.QueryRow(`SELECT COUNT(*) FROM status_history`).Scan(&count); err != nil {
		t.Fatalf("count status_history: %v", err)
	}
	if count != 1 {
		t.Errorf("status_history: want 1 surviving row, got %d", count)
	}
	if err := db.QueryRow(`SELECT COUNT(*) FROM ssl_certificates`).Scan(&count); err != nil {
		t.Fatalf("count ssl_certificates: %v", err)
	}
	if count != 0 {
		t.Errorf("ssl_certificates: want orphan row dropped, got %d rows", count)
	}
	if err := db.QueryRow(`SELECT COUNT(*) FROM sessions`).Scan(&count); err != nil {
		t.Fatalf("count sessions: %v", err)
	}
	if count != 1 {
		t.Errorf("sessions: want 1 surviving row, got %d", count)
	}
	var status string
	if err := db.QueryRow(`SELECT status FROM status_history WHERE site_id = 1`).Scan(&status); err != nil {
		t.Fatalf("surviving row lost: %v", err)
	}
	if status != "up" {
		t.Errorf("surviving row data corrupted: got status %q", status)
	}

	// The FK must now be live: inserting a new orphan must fail...
	if _, err := db.Exec(`INSERT INTO status_history (site_id, status, checked_at) VALUES (999, 'down', 'now')`); err == nil {
		t.Error("expected FK violation inserting orphan status_history row, got none")
	}
	// ...and deleting the parent must cascade.
	if _, err := db.Exec(`DELETE FROM sites WHERE id = 1`); err != nil {
		t.Fatalf("delete site: %v", err)
	}
	if err := db.QueryRow(`SELECT COUNT(*) FROM status_history`).Scan(&count); err != nil {
		t.Fatalf("count status_history after cascade: %v", err)
	}
	if count != 0 {
		t.Errorf("expected cascade delete to remove status_history rows, got %d remaining", count)
	}

	// Re-opening must be idempotent (tableHasForeignKey short-circuits).
	again, _, err := Open(path)
	if err != nil {
		t.Fatalf("second Open: %v", err)
	}
	again.Close()
}

// TestRestoreBackupFileReportsSpecificErrors verifies restoreFromPath no
// longer collapses every failure into an uninformative "" - an operator
// restoring a database during an incident needs to know exactly what failed.
func TestRestoreBackupFileReportsSpecificErrors(t *testing.T) {
	dir := t.TempDir()
	dbPath := filepath.Join(dir, "sites.db")
	db, abs, err := Open(dbPath)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	store := NewStore(db, abs)
	// store.DB is reassigned by a successful restore below, so close whatever
	// it points to when the test ends, not the original *sql.DB captured now.
	defer func() { store.DB.Close() }()

	backupDir := filepath.Join(dir, "backups")
	if err := os.MkdirAll(backupDir, 0o755); err != nil {
		t.Fatalf("mkdir backups: %v", err)
	}

	// Missing backup file: must return a specific error, not "" with nil err,
	// and the store's DB must remain open and usable afterwards.
	_, err = store.RestoreBackupFile(backupDir, "does-not-exist.db")
	if err == nil {
		t.Fatal("expected an error for a missing backup file, got nil")
	}
	if !strings.Contains(err.Error(), "backup file not found") {
		t.Errorf("expected a 'backup file not found' error, got: %v", err)
	}
	if _, execErr := store.DB.Exec(`SELECT 1`); execErr != nil {
		t.Errorf("store DB unusable after failed restore: %v", execErr)
	}

	// Path traversal in the filename must still be rejected outright.
	_, err = store.RestoreBackupFile(backupDir, "../escape.db")
	if err == nil || !strings.Contains(err.Error(), "invalid backup filename") {
		t.Errorf("expected 'invalid backup filename' error, got: %v", err)
	}

	// A real backup file must restore successfully and leave the store usable.
	if _, err := store.DB.Exec(`INSERT INTO sites (name, url) VALUES ('before-restore', 'https://example.com')`); err != nil {
		t.Fatalf("seed site: %v", err)
	}
	backupPath := filepath.Join(backupDir, "good.db")
	if _, err := store.DB.Exec(`VACUUM INTO ?`, backupPath); err != nil {
		t.Fatalf("create backup snapshot: %v", err)
	}
	restored, err := store.RestoreBackupFile(backupDir, "good.db")
	if err != nil {
		t.Fatalf("restore good backup: %v", err)
	}
	if restored != backupPath {
		t.Errorf("expected restored path %q, got %q", backupPath, restored)
	}
	var name string
	if err := store.DB.QueryRow(`SELECT name FROM sites WHERE url = ?`, "https://example.com").Scan(&name); err != nil {
		t.Fatalf("query restored data: %v", err)
	}
	if name != "before-restore" {
		t.Errorf("restored data mismatch: got %q", name)
	}
}
