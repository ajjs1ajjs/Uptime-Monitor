package storage

import (
	"database/sql"
	"path/filepath"
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
	for _, col := range []string{"first_failure_at", "silenced_until", "acknowledged"} {
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
