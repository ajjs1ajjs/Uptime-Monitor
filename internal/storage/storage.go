package storage

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"time"

	_ "modernc.org/sqlite"
)

var Schema = `
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
  action TEXT NOT NULL, target_type TEXT, target_id TEXT, details TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS sites (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
  check_interval INTEGER DEFAULT 60, is_active BOOLEAN DEFAULT 1,
  request_timeout_seconds INTEGER DEFAULT 15,
  retry_interval_seconds INTEGER DEFAULT 10,
  max_retries INTEGER DEFAULT 3,
  up_success_threshold INTEGER DEFAULT 3,
  last_notification TEXT, notify_methods TEXT DEFAULT '[]',
  status TEXT DEFAULT 'unknown', status_code INTEGER, response_time REAL,
  error_message TEXT, monitor_type TEXT DEFAULT 'http',
  failed_attempts INTEGER DEFAULT 0, success_attempts INTEGER DEFAULT 0,
  last_down_alert TEXT, first_failure_at TEXT, keyword TEXT DEFAULT NULL,
  tags TEXT DEFAULT '[]', silenced_until TEXT DEFAULT NULL,
  acknowledged INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS status_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE, status TEXT,
  status_code INTEGER, response_time REAL, error_message TEXT, checked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sh_site_ts ON status_history(site_id, checked_at);
CREATE TABLE IF NOT EXISTS notify_config (
  id INTEGER PRIMARY KEY, config TEXT
);
CREATE TABLE IF NOT EXISTS ssl_certificates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id INTEGER UNIQUE REFERENCES sites(id) ON DELETE CASCADE, hostname TEXT,
  issuer TEXT, subject TEXT, start_date TEXT, expire_date TEXT,
  days_until_expire INTEGER, is_valid BOOLEAN, last_checked TEXT,
  last_notified TEXT, ssl_notified_thresholds TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS app_settings (
  id INTEGER PRIMARY KEY, display_address TEXT,
  site_title TEXT DEFAULT 'Uptime Monitor', logo_url TEXT DEFAULT '',
  footer_text TEXT DEFAULT '', primary_color TEXT DEFAULT '#00ff88',
  brand_accent_color TEXT DEFAULT '#06b6d4'
);
CREATE TABLE IF NOT EXISTS notification_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE, site_name TEXT,
  method TEXT, status TEXT, message_preview TEXT, sent_at TEXT
);
CREATE TABLE IF NOT EXISTS backups (
  id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, filepath TEXT,
  size_bytes INTEGER, site_count INTEGER, created_at TEXT
);
CREATE TABLE IF NOT EXISTS rate_limits (
  id INTEGER PRIMARY KEY AUTOINCREMENT, endpoint TEXT NOT NULL, ip TEXT NOT NULL,
  attempt_count INTEGER DEFAULT 1, reset_at REAL NOT NULL, UNIQUE(endpoint, ip)
);
CREATE TABLE IF NOT EXISTS maintenance_windows (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
  site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE,
  rule_type TEXT DEFAULT 'one_off', start_time TEXT, end_time TEXT,
  day_of_week INTEGER, start_hour_minute TEXT, duration_minutes INTEGER,
  is_active BOOLEAN DEFAULT 1
);
CREATE TABLE IF NOT EXISTS csrf_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
  token TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_csrf_session ON csrf_tokens(session_id);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT DEFAULT 'viewer',
  must_change_password BOOLEAN DEFAULT 0, created_at TEXT, last_login TEXT,
  password_encrypted TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, session_id TEXT UNIQUE,
  created_at TEXT, expires_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS api_keys (
  key_id TEXT PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, name TEXT,
  key_hash TEXT NOT NULL, created_at TEXT, last_used_at TEXT,
  is_active INTEGER DEFAULT 1
);
`

func Open(path string) (*sql.DB, string, error) {
	if path == "" {
		path = "sites.db"
	}
	abs, err := filepath.Abs(path)
	if err != nil {
		abs = path
	}
	if dir := filepath.Dir(abs); dir != "." && dir != "" {
		_ = os.MkdirAll(dir, 0o755)
	}
	dsn := fmt.Sprintf("file:%s?_pragma=journal_mode(WAL)&_pragma=busy_timeout(30000)&_pragma=synchronous(NORMAL)&_pragma=foreign_keys(ON)", abs)
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, abs, err
	}
	db.SetMaxOpenConns(10)
	if _, err := db.Exec(Schema); err != nil {
		return nil, abs, fmt.Errorf("apply schema: %w", err)
	}
	if err := migrateSchema(db); err != nil {
		return nil, abs, fmt.Errorf("migrate schema: %w", err)
	}
	if err := ensureForeignKeys(db); err != nil {
		return nil, abs, fmt.Errorf("migrate foreign keys: %w", err)
	}
	return db, abs, nil
}

// migrateSchema upgrades databases created by older versions — including the
// Python/FastAPI backend — that lack columns added later. CREATE TABLE IF NOT
// EXISTS only creates missing tables, never missing columns, so the new columns
// are added explicitly here. Every column has a DEFAULT, so existing rows stay
// valid and old binary builds keep working against the migrated file.
func migrateSchema(db *sql.DB) error {
	type colDef struct{ table, name, ddl string }
	// (table, column, ADD COLUMN definition) — table/column names are
	// hardcoded constants, never user input, so ALTER TABLE is safe.
	steps := []colDef{
		{"sites", "request_timeout_seconds", "request_timeout_seconds INTEGER DEFAULT 15"},
		{"sites", "retry_interval_seconds", "retry_interval_seconds INTEGER DEFAULT 10"},
		{"sites", "max_retries", "max_retries INTEGER DEFAULT 3"},
		{"sites", "up_success_threshold", "up_success_threshold INTEGER DEFAULT 3"},
		{"sites", "first_failure_at", "first_failure_at TEXT DEFAULT NULL"},
		{"sites", "silenced_until", "silenced_until TEXT DEFAULT NULL"},
		{"sites", "acknowledged", "acknowledged INTEGER DEFAULT 0"},
		{"ssl_certificates", "ssl_notified_thresholds", "ssl_notified_thresholds TEXT DEFAULT '[]'"},
	}
	for _, s := range steps {
		rows, err := db.Query(`PRAGMA table_info(` + s.table + `)`)
		if err != nil {
			return err
		}
		found := false
		for rows.Next() {
			var cid, name, ctype string
			var notnull, pk int
			var dflt any
			if err := rows.Scan(&cid, &name, &ctype, &notnull, &dflt, &pk); err == nil && name == s.name {
				found = true
				break
			}
		}
		rows.Close()
		if found {
			continue
		}
		if _, err := db.Exec(`ALTER TABLE ` + s.table + ` ADD COLUMN ` + s.ddl); err != nil {
			return fmt.Errorf("add %s.%s: %w", s.table, s.name, err)
		}
	}
	return nil
}

// fkTable describes a table that must reference a parent table by FK. createSQL
// is the full CREATE TABLE statement for the rebuilt version (with the FK
// clause); columns lists the exact column list, in order, for the INSERT ...
// SELECT copy; orphanSQL (optional) deletes rows that would violate the new
// FK so the copy cannot fail; indexSQL recreates indexes lost when the old
// table is dropped.
type fkTable struct {
	table     string
	createSQL string
	columns   string
	orphanSQL string
	indexSQL  []string
}

var fkMigrations = []fkTable{
	{
		table: "status_history",
		createSQL: `CREATE TABLE status_history_new (
		  id INTEGER PRIMARY KEY AUTOINCREMENT,
		  site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE, status TEXT,
		  status_code INTEGER, response_time REAL, error_message TEXT, checked_at TEXT
		)`,
		columns:   "id, site_id, status, status_code, response_time, error_message, checked_at",
		orphanSQL: `DELETE FROM status_history WHERE site_id IS NOT NULL AND site_id NOT IN (SELECT id FROM sites)`,
		indexSQL:  []string{`CREATE INDEX IF NOT EXISTS idx_sh_site_ts ON status_history(site_id, checked_at)`},
	},
	{
		table: "ssl_certificates",
		createSQL: `CREATE TABLE ssl_certificates_new (
		  id INTEGER PRIMARY KEY AUTOINCREMENT,
		  site_id INTEGER UNIQUE REFERENCES sites(id) ON DELETE CASCADE, hostname TEXT,
		  issuer TEXT, subject TEXT, start_date TEXT, expire_date TEXT,
		  days_until_expire INTEGER, is_valid BOOLEAN, last_checked TEXT,
		  last_notified TEXT, ssl_notified_thresholds TEXT DEFAULT '[]'
		)`,
		columns:   "id, site_id, hostname, issuer, subject, start_date, expire_date, days_until_expire, is_valid, last_checked, last_notified, ssl_notified_thresholds",
		orphanSQL: `DELETE FROM ssl_certificates WHERE site_id IS NOT NULL AND site_id NOT IN (SELECT id FROM sites)`,
	},
	{
		table: "notification_history",
		createSQL: `CREATE TABLE notification_history_new (
		  id INTEGER PRIMARY KEY AUTOINCREMENT,
		  site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE, site_name TEXT,
		  method TEXT, status TEXT, message_preview TEXT, sent_at TEXT
		)`,
		columns:   "id, site_id, site_name, method, status, message_preview, sent_at",
		orphanSQL: `DELETE FROM notification_history WHERE site_id IS NOT NULL AND site_id NOT IN (SELECT id FROM sites)`,
	},
	{
		table: "maintenance_windows",
		createSQL: `CREATE TABLE maintenance_windows_new (
		  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
		  site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE,
		  rule_type TEXT DEFAULT 'one_off', start_time TEXT, end_time TEXT,
		  day_of_week INTEGER, start_hour_minute TEXT, duration_minutes INTEGER,
		  is_active BOOLEAN DEFAULT 1
		)`,
		columns:   "id, name, site_id, rule_type, start_time, end_time, day_of_week, start_hour_minute, duration_minutes, is_active",
		orphanSQL: `DELETE FROM maintenance_windows WHERE site_id IS NOT NULL AND site_id NOT IN (SELECT id FROM sites)`,
	},
	{
		table: "sessions",
		createSQL: `CREATE TABLE sessions_new (
		  id INTEGER PRIMARY KEY AUTOINCREMENT,
		  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, session_id TEXT UNIQUE,
		  created_at TEXT, expires_at TEXT
		)`,
		columns:   "id, user_id, session_id, created_at, expires_at",
		orphanSQL: `DELETE FROM sessions WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)`,
		indexSQL:  []string{`CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)`},
	},
	{
		table: "api_keys",
		createSQL: `CREATE TABLE api_keys_new (
		  key_id TEXT PRIMARY KEY,
		  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, name TEXT,
		  key_hash TEXT NOT NULL, created_at TEXT, last_used_at TEXT,
		  is_active INTEGER DEFAULT 1
		)`,
		columns:   "key_id, user_id, name, key_hash, created_at, last_used_at, is_active",
		orphanSQL: `DELETE FROM api_keys WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)`,
	},
}

// ensureForeignKeys rebuilds tables created by pre-FK versions of this
// program so PRAGMA foreign_keys=ON (already set on every connection, see
// Open) actually enforces referential integrity instead of being a no-op
// because the tables never declared REFERENCES clauses. SQLite cannot ALTER
// TABLE to add a constraint, so each table is rebuilt: create the new table
// with the FK, drop rows that would violate it (pre-existing orphans from
// before this fix), copy the rest across, drop the old table, and rename the
// new one into place. New databases already get the FK from Schema directly
// and skip this (tableHasForeignKey returns true immediately).
func ensureForeignKeys(db *sql.DB) error {
	for _, t := range fkMigrations {
		has, err := tableHasForeignKey(db, t.table)
		if err != nil {
			return err
		}
		if has {
			continue
		}
		if err := rebuildWithForeignKey(db, t); err != nil {
			return fmt.Errorf("add FK to %s: %w", t.table, err)
		}
	}
	return nil
}

func tableHasForeignKey(db *sql.DB, table string) (bool, error) {
	rows, err := db.Query(`PRAGMA foreign_key_list(` + table + `)`)
	if err != nil {
		return false, err
	}
	defer rows.Close()
	return rows.Next(), rows.Err()
}

func rebuildWithForeignKey(db *sql.DB, t fkTable) error {
	// PRAGMA foreign_keys cannot be toggled inside a transaction in SQLite, so
	// it is turned off for the duration of the rebuild (no FK exists on this
	// table yet, so nothing is weakened) and restored unconditionally after.
	if _, err := db.Exec(`PRAGMA foreign_keys=OFF`); err != nil {
		return err
	}
	defer db.Exec(`PRAGMA foreign_keys=ON`)

	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if t.orphanSQL != "" {
		if _, err := tx.Exec(t.orphanSQL); err != nil {
			return fmt.Errorf("drop orphan rows: %w", err)
		}
	}
	if _, err := tx.Exec(t.createSQL); err != nil {
		return fmt.Errorf("create rebuilt table: %w", err)
	}
	insertSQL := fmt.Sprintf(`INSERT INTO %s_new (%s) SELECT %s FROM %s`, t.table, t.columns, t.columns, t.table)
	if _, err := tx.Exec(insertSQL); err != nil {
		return fmt.Errorf("copy rows: %w", err)
	}
	if _, err := tx.Exec(`DROP TABLE ` + t.table); err != nil {
		return fmt.Errorf("drop old table: %w", err)
	}
	if _, err := tx.Exec(fmt.Sprintf(`ALTER TABLE %s_new RENAME TO %s`, t.table, t.table)); err != nil {
		return fmt.Errorf("rename table: %w", err)
	}
	for _, idx := range t.indexSQL {
		if _, err := tx.Exec(idx); err != nil {
			return fmt.Errorf("recreate index: %w", err)
		}
	}
	return tx.Commit()
}

func Now() string {
	return time.Now().UTC().Format("2006-01-02T15:04:05.000000+00:00")
}

type Store struct {
	DB     *sql.DB
	DBPath string
	mu     chan struct{} // serializes backup/restore
}

func NewStore(db *sql.DB, path string) *Store {
	return &Store{DB: db, DBPath: path, mu: make(chan struct{}, 1)}
}

// cleanOldData applies retention rules.
func (st *Store) Cleanup() error {
	queries := []string{
		`DELETE FROM status_history WHERE checked_at < datetime('now', '-30 days')`,
		`DELETE FROM notification_history WHERE sent_at < datetime('now', '-90 days')`,
		`DELETE FROM rate_limits WHERE reset_at < ?`,
		`DELETE FROM csrf_tokens WHERE created_at < datetime('now', '-1 day')`,
		`DELETE FROM sessions WHERE expires_at < datetime('now')`,
		`DELETE FROM audit_log WHERE created_at < datetime('now', '-365 days')`,
		`DELETE FROM backups WHERE created_at < datetime('now', '-180 days')`,
	}
	for _, q := range queries {
		if _, err := st.DB.Exec(q, float64(time.Now().Add(-7*24*time.Hour).Unix())); err != nil {
			return err
		}
	}
	return nil
}
