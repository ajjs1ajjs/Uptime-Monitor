package storage

import (
	"database/sql"
	"fmt"
	"time"
)

// TimeLayout is the single canonical format for every machine-written
// timestamp column in this database.
//
// It is UTC, always, and it is RFC3339 (so browsers can feed the value
// straight into `new Date(...)` and render it in the viewer's own timezone).
//
// Why this matters more than it looks: SQLite has no date type, so these
// columns are TEXT and every "is it expired / is it within the last N days"
// check is a *lexicographic string comparison*. That only gives the right
// answer when both sides of the comparison use the exact same format.
//
// Before this was fixed, timestamps were written as Kyiv local time with an
// offset ("2026-09-17T12:00:00.000000+03:00") but compared against SQLite's
// datetime('now'), which returns UTC with a space separator
// ("2026-09-17 09:00:00"). Comparing those two byte-for-byte, the first
// difference is at index 10: 'T' (0x54) vs ' ' (0x20). 'T' always wins, so
// `expires_at > datetime('now')` was true for *any* time on the same UTC day
// and sessions stayed valid until midnight UTC after they had expired.
//
// So: write timestamps with Now()/TimeString, and compare them against
// Since()/TimeString — never against datetime('now').
const TimeLayout = "2006-01-02T15:04:05.000000Z07:00"

// legacyTimeLayouts are formats written by older versions (Kyiv local time
// with an offset) or supplied by clients. Read paths must still accept them:
// migrateTimestamps rewrites stored rows, but values can also arrive from the
// API (silenced_until) or from a database an older binary wrote to after the
// upgrade.
var legacyTimeLayouts = []string{
	TimeLayout,
	time.RFC3339Nano,
	time.RFC3339,
	"2006-01-02T15:04:05.999999-07:00",
	"2006-01-02T15:04:05",
	"2006-01-02T15:04",
	"2006-01-02 15:04:05.999999-07:00",
	"2006-01-02 15:04:05",
}

// Now returns the current time in the canonical format.
func Now() string { return TimeString(time.Now()) }

// TimeString renders t in the canonical format (converting to UTC first).
func TimeString(t time.Time) string { return t.UTC().Format(TimeLayout) }

// Since returns the canonical timestamp for "d ago" — the right-hand side of
// a retention or reporting window (`WHERE checked_at >= ?`).
func Since(d time.Duration) string { return TimeString(time.Now().Add(-d)) }

// ParseTime parses a stored timestamp, accepting both the canonical format and
// every legacy format this project has written or accepted. Values without a
// zone are interpreted as Kyiv local time, which is what the versions that
// wrote them meant.
func ParseTime(s string) (time.Time, error) {
	if s == "" {
		return time.Time{}, fmt.Errorf("empty timestamp")
	}
	for _, layout := range legacyTimeLayouts {
		if t, err := time.ParseInLocation(layout, s, kyivLoc); err == nil {
			return t, nil
		}
	}
	return time.Time{}, fmt.Errorf("unrecognized timestamp %q", s)
}

// timestampColumns are the columns written by Now() — machine timestamps that
// participate in string comparisons and therefore must all share one format.
//
// Deliberately excluded:
//   - maintenance_windows.start_time/end_time — operator-supplied wall clock,
//     parsed with parseFlexTime, not written by Now().
//   - ssl_certificates.start_date/expire_date — copied from the X.509
//     certificate in its own display format, never compared.
//   - sites.silenced_until — client-supplied via the API.
//   - csrf_tokens.created_at — filled by a SQLite DEFAULT (datetime('now'))
//     and only ever compared against datetime('now'), so it is already
//     self-consistent.
var timestampColumns = []struct{ table, column string }{
	{"status_history", "checked_at"},
	{"notification_history", "sent_at"},
	{"audit_log", "created_at"},
	{"backups", "created_at"},
	{"users", "created_at"},
	{"users", "last_login"},
	{"sessions", "created_at"},
	{"sessions", "expires_at"},
	{"api_keys", "created_at"},
	{"api_keys", "last_used_at"},
	{"sites", "last_notification"},
	{"sites", "last_down_alert"},
	{"sites", "first_failure_at"},
	{"ssl_certificates", "last_checked"},
	{"ssl_certificates", "last_notified"},
}

// migrateTimestamps rewrites legacy offset-bearing timestamps to the canonical
// UTC format so old and new rows compare correctly against each other.
//
// SQLite's own date functions parse ISO-8601 with an offset and normalize to
// UTC, so the conversion happens in the database and needs no round trip:
// '2026-09-17T12:00:00.123456+03:00' becomes '2026-09-17T09:00:00.123000Z'
// (sub-millisecond precision is dropped, which nothing here depends on).
//
// The WHERE clause makes this idempotent and cheap on an already-migrated
// database: only values that look like an ISO timestamp and do NOT already end
// in 'Z' are touched.
func migrateTimestamps(db *sql.DB) error {
	for _, c := range timestampColumns {
		if !tableHasColumn(db, c.table, c.column) {
			continue // table or column belongs to a newer/older schema
		}
		// Table and column names come from the hardcoded list above, never
		// from user input.
		q := fmt.Sprintf(
			`UPDATE %s SET %s = strftime('%%Y-%%m-%%dT%%H:%%M:%%f000Z', %s)
			   WHERE %s IS NOT NULL AND %s LIKE '____-__-__T%%' AND %s NOT LIKE '%%Z'
			     AND strftime('%%Y-%%m-%%dT%%H:%%M:%%f000Z', %s) IS NOT NULL`,
			c.table, c.column, c.column, c.column, c.column, c.column, c.column)
		if _, err := db.Exec(q); err != nil {
			return fmt.Errorf("normalize %s.%s: %w", c.table, c.column, err)
		}
	}
	return nil
}

// tableHasColumn reports whether table exists and has the given column.
func tableHasColumn(db *sql.DB, table, column string) bool {
	rows, err := db.Query(`PRAGMA table_info(` + table + `)`)
	if err != nil {
		return false
	}
	defer rows.Close()
	for rows.Next() {
		var cid, name, ctype string
		var notnull, pk int
		var dflt any
		if err := rows.Scan(&cid, &name, &ctype, &notnull, &dflt, &pk); err == nil && name == column {
			return true
		}
	}
	return false
}
