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
  last_notification TEXT, notify_methods TEXT DEFAULT '[]',
  status TEXT DEFAULT 'unknown', status_code INTEGER, response_time REAL,
  error_message TEXT, monitor_type TEXT DEFAULT 'http',
  failed_attempts INTEGER DEFAULT 0, success_attempts INTEGER DEFAULT 0,
  last_down_alert TEXT, first_failure_at TEXT, keyword TEXT DEFAULT NULL,
  tags TEXT DEFAULT '[]', silenced_until TEXT DEFAULT NULL,
  acknowledged INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS status_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER, status TEXT,
  status_code INTEGER, response_time REAL, error_message TEXT, checked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sh_site_ts ON status_history(site_id, checked_at);
CREATE TABLE IF NOT EXISTS notify_config (
  id INTEGER PRIMARY KEY, config TEXT
);
CREATE TABLE IF NOT EXISTS ssl_certificates (
  id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER UNIQUE, hostname TEXT,
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
  id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER, site_name TEXT,
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
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, site_id INTEGER,
  rule_type TEXT DEFAULT 'one_off', start_time TEXT, end_time TEXT,
  day_of_week INTEGER, start_hour_minute TEXT, duration_minutes INTEGER,
  is_active BOOLEAN DEFAULT 1
);
CREATE TABLE IF NOT EXISTS csrf_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
  token TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_csrf_session ON csrf_tokens(session_id);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, session_id TEXT UNIQUE,
  created_at TEXT, expires_at TEXT
);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT DEFAULT 'viewer',
  must_change_password BOOLEAN DEFAULT 0, created_at TEXT, last_login TEXT,
  password_encrypted TEXT
);
CREATE TABLE IF NOT EXISTS api_keys (
  key_id TEXT PRIMARY KEY, user_id INTEGER, name TEXT,
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
	return db, abs, nil
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
