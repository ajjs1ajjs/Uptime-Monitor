package storage

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type Site struct {
	ID               int64    `json:"id"`
	Name             string   `json:"name"`
	URL              string   `json:"url"`
	CheckInterval    int      `json:"check_interval"`
	IsActive         bool     `json:"is_active"`
	LastNotification *string  `json:"last_notification"`
	NotifyMethods    string   `json:"-"`
	Status           string   `json:"status"`
	StatusCode       *int     `json:"status_code"`
	ResponseTime     *float64 `json:"response_time"`
	ErrorMessage     *string  `json:"error_message"`
	MonitorType      string   `json:"monitor_type"`
	FailedAttempts   int      `json:"failed_attempts"`
	SuccessAttempts  int      `json:"success_attempts"`
	LastDownAlert    *string  `json:"last_down_alert"`
	FirstFailureAt   *string  `json:"first_failure_at"`
	Keyword          *string  `json:"keyword"`
	Tags             string   `json:"-"`
	SilencedUntil    *string  `json:"silenced_until"`
	Acknowledged     int      `json:"acknowledged"`
	Uptime           float64  `json:"uptime"`
}

const siteCols = `id, name, url, check_interval, is_active, last_notification, notify_methods,
 status, status_code, response_time, error_message, monitor_type, failed_attempts, success_attempts,
 last_down_alert, first_failure_at, keyword, tags, silenced_until, acknowledged`

func (s *Site) notifyMethodsJSON() string {
	if s.NotifyMethods == "" {
		return "[]"
	}
	return s.NotifyMethods
}

func (s *Site) tagsJSON() string {
	if s.Tags == "" {
		return "[]"
	}
	return s.Tags
}

func scanSite(row interface{ Scan(...any) error }) (*Site, error) {
	var s Site
	var active, ack int
	var lastNotif, statusCode, respTime, errMsg, lastDown, firstFail, keyword, silenced sql.NullString
	var lastNotifS, statusCodeS, respTimeS, errMsgS, lastDownS, firstFailS, keywordS, silencedS any
	_ = lastNotifS
	_ = statusCodeS
	_ = respTimeS
	_ = errMsgS
	_ = lastDownS
	_ = firstFailS
	_ = keywordS
	_ = silencedS
	err := row.Scan(&s.ID, &s.Name, &s.URL, &s.CheckInterval, &active, &lastNotif,
		&s.NotifyMethods, &s.Status, &statusCode, &respTime, &errMsg, &s.MonitorType,
		&s.FailedAttempts, &s.SuccessAttempts, &lastDown, &firstFail, &keyword, &s.Tags,
		&silenced, &ack)
	if err != nil {
		return nil, err
	}
	s.IsActive = active == 1
	s.Acknowledged = ack
	s.LastNotification = nullStrPtr(lastNotif)
	if statusCode.Valid {
		n, _ := strconv.Atoi(statusCode.String)
		s.StatusCode = &n
	}
	if respTime.Valid {
		f, _ := strconv.ParseFloat(respTime.String, 64)
		s.ResponseTime = &f
	}
	s.ErrorMessage = nullStrPtr(errMsg)
	s.LastDownAlert = nullStrPtr(lastDown)
	s.FirstFailureAt = nullStrPtr(firstFail)
	s.Keyword = nullStrPtr(keyword)
	s.SilencedUntil = nullStrPtr(silenced)
	return &s, nil
}

func nullStrPtr(n sql.NullString) *string {
	if !n.Valid {
		return nil
	}
	v := n.String
	return &v
}

func (st *Store) GetSites() ([]Site, error) {
	rows, err := st.DB.Query(`SELECT ` + siteCols + ` FROM sites ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Site
	for rows.Next() {
		s, err := scanSite(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, *s)
	}
	// attach last status + uptime in bulk
	if len(out) > 0 {
		st.attachStatus(out)
	}
	return out, rows.Err()
}

func (st *Store) attachStatus(sites []Site) {
	// Bound both scans to recent windows so dashboard/public loads do not walk
	// the whole status_history table. Active sites are checked at least every
	// 24h, so a 7-day window covers their latest row; anything older falls back
	// to the sites.status column the worker already maintains.
	lastRows, err := st.DB.Query(`SELECT site_id, status FROM (
	  SELECT site_id, status, ROW_NUMBER() OVER (PARTITION BY site_id ORDER BY checked_at DESC) rn
	  FROM status_history WHERE checked_at >= datetime('now','-7 days')) WHERE rn = 1`)
	if err == nil {
		defer lastRows.Close()
		lastMap := map[int64]string{}
		for lastRows.Next() {
			var sid int64
			var status string
			if lastRows.Scan(&sid, &status) == nil {
				lastMap[sid] = status
			}
		}
		for i := range sites {
			if st, ok := lastMap[sites[i].ID]; ok {
				sites[i].Status = st
			}
		}
	}
	statsRows, err := st.DB.Query(`SELECT site_id, COUNT(*), SUM(CASE WHEN status='up' THEN 1 ELSE 0 END)
	  FROM status_history WHERE checked_at >= datetime('now','-30 days') GROUP BY site_id`)
	if err == nil {
		defer statsRows.Close()
		statsMap := map[int64][2]float64{}
		for statsRows.Next() {
			var sid int64
			var total, up sql.NullFloat64
			if statsRows.Scan(&sid, &total, &up) == nil {
				statsMap[sid] = [2]float64{total.Float64, up.Float64}
			}
		}
		for i := range sites {
			if t, ok := statsMap[sites[i].ID]; ok && t[0] > 0 {
				sites[i].Uptime = round2(t[1] / t[0] * 100)
			}
		}
	}
}

func round2(f float64) float64 {
	return float64(int(f*100+0.5)) / 100
}

func (st *Store) GetActiveSites() ([]Site, error) {
	rows, err := st.DB.Query(`SELECT ` + siteCols + ` FROM sites WHERE is_active = 1 ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Site
	for rows.Next() {
		s, err := scanSite(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, *s)
	}
	return out, rows.Err()
}

func (st *Store) GetSite(id int64) (*Site, error) {
	row := st.DB.QueryRow(`SELECT `+siteCols+` FROM sites WHERE id = ?`, id)
	s, err := scanSite(row)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return s, err
}

func (st *Store) CreateSite(name, url string, interval int, active bool, notifyMethods, monitorType, keyword, tags string) (int64, error) {
	a := 0
	if active {
		a = 1
	}
	res, err := st.DB.Exec(`INSERT INTO sites (name, url, check_interval, is_active, notify_methods, monitor_type, keyword, tags)
	  VALUES (?,?,?,?,?,?,?,?)`, name, url, interval, a, notifyMethods, monitorType, keyword, tags)
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func (st *Store) UpdateSite(id int64, fields map[string]any) error {
	if len(fields) == 0 {
		return nil
	}
	var sets []string
	var args []any
	for k, v := range fields {
		sets = append(sets, k+" = ?")
		args = append(args, v)
	}
	args = append(args, id)
	_, err := st.DB.Exec(`UPDATE sites SET `+strings.Join(sets, ", ")+` WHERE id = ?`, args...)
	return err
}

func (st *Store) DeleteSite(id int64) error {
	tx, err := st.DB.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for _, q := range []string{
		`DELETE FROM status_history WHERE site_id = ?`,
		`DELETE FROM ssl_certificates WHERE site_id = ?`,
		`DELETE FROM maintenance_windows WHERE site_id = ?`,
		`DELETE FROM notification_history WHERE site_id = ?`,
		`DELETE FROM sites WHERE id = ?`,
	} {
		if _, err := tx.Exec(q, id); err != nil {
			return err
		}
	}
	return tx.Commit()
}

func (st *Store) AddStatusHistory(siteID int64, status string, code *int, respTime *float64, errMsg *string) error {
	_, err := st.DB.Exec(`INSERT INTO status_history (site_id, status, status_code, response_time, error_message, checked_at)
	  VALUES (?,?,?,?,?,?)`, siteID, status, code, respTime, errMsg, Now())
	return err
}

func (st *Store) SiteHistory(siteID int64, limit int) ([]map[string]any, error) {
	rows, err := st.DB.Query(`SELECT status, status_code, checked_at FROM status_history WHERE site_id = ? ORDER BY checked_at DESC LIMIT ?`, siteID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]map[string]any, 0)
	for rows.Next() {
		var status string
		var code sql.NullInt64
		var ts sql.NullString
		if err := rows.Scan(&status, &code, &ts); err != nil {
			return nil, err
		}
		row := map[string]any{"status": status, "checked_at": ts.String}
		if code.Valid {
			row["status_code"] = code.Int64
		} else {
			row["status_code"] = nil
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

func (st *Store) HistoryAll() (map[int64][]map[string]any, error) {
	rows, err := st.DB.Query(`SELECT site_id, status, checked_at FROM status_history WHERE checked_at >= datetime('now','-24 hours') ORDER BY checked_at ASC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[int64][]map[string]any{}
	for rows.Next() {
		var sid int64
		var status string
		var ts sql.NullString
		if err := rows.Scan(&sid, &status, &ts); err != nil {
			return nil, err
		}
		out[sid] = append(out[sid], map[string]any{"status": status, "checked_at": ts.String})
	}
	return out, nil
}

// --- SSL certificates ---

type SSLCert struct {
	ID                    int64   `json:"id"`
	SiteID                int64   `json:"site_id"`
	SiteName              string  `json:"site_name"`
	SiteURL               string  `json:"site_url"`
	Hostname              string  `json:"hostname"`
	Issuer                string  `json:"issuer"`
	Subject               string  `json:"subject"`
	StartDate             string  `json:"start_date"`
	ExpireDate            string  `json:"expire_date"`
	DaysUntilExpire       int     `json:"days_until_expire"`
	IsValid               bool    `json:"is_valid"`
	LastChecked           string  `json:"last_checked"`
	LastNotified          *string `json:"last_notified"`
	SSLNotifiedThresholds []int   `json:"ssl_notified_thresholds"`
}

func (st *Store) GetSSLCertificates() ([]SSLCert, error) {
	rows, err := st.DB.Query(`SELECT c.*, s.name as site_name, s.url as site_url FROM ssl_certificates c
	  JOIN sites s ON c.site_id = s.id WHERE s.is_active = 1 ORDER BY c.days_until_expire ASC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []SSLCert
	for rows.Next() {
		var c SSLCert
		var valid int
		var thresholds sql.NullString
		var lastNotified sql.NullString
		if err := rows.Scan(&c.ID, &c.SiteID, &c.Hostname, &c.Issuer, &c.Subject, &c.StartDate,
			&c.ExpireDate, &c.DaysUntilExpire, &valid, &c.LastChecked, &lastNotified, &thresholds,
			&c.SiteName, &c.SiteURL); err != nil {
			return nil, err
		}
		c.IsValid = valid == 1
		c.LastNotified = nullStrPtr(lastNotified)
		if thresholds.Valid && thresholds.String != "" {
			_ = json.Unmarshal([]byte(thresholds.String), &c.SSLNotifiedThresholds)
		}
		out = append(out, c)
	}
	return out, rows.Err()
}

// SaveSSLCertificate upserts the certificate row for a site in a single
// statement. Previously this was a read-then-write (SELECT COUNT then INSERT
// or UPDATE); if two SSL check cycles for the same site overlapped (e.g. a
// slow check plus a retry), both could see exists=0 and both attempt INSERT,
// and the second would fail on the ssl_certificates.site_id UNIQUE
// constraint. ON CONFLICT makes the whole operation atomic from SQLite's
// point of view, so a concurrent second writer updates instead of erroring.
func (st *Store) SaveSSLCertificate(siteID int64, cert map[string]any) error {
	_, err := st.DB.Exec(`INSERT INTO ssl_certificates (site_id, hostname, issuer, subject, start_date, expire_date, days_until_expire, is_valid, last_checked)
	  VALUES (?,?,?,?,?,?,?,?,?)
	  ON CONFLICT(site_id) DO UPDATE SET
	    hostname=excluded.hostname, issuer=excluded.issuer, subject=excluded.subject,
	    start_date=excluded.start_date, expire_date=excluded.expire_date,
	    days_until_expire=excluded.days_until_expire, is_valid=excluded.is_valid,
	    last_checked=excluded.last_checked`,
		siteID, cert["hostname"], cert["issuer"], cert["subject"],
		cert["start_date"], cert["expire_date"], cert["days_until_expire"], cert["is_valid"], Now())
	return err
}

func (st *Store) UpdateSSLThresholds(siteID int64, thresholds []int, lastNotified string) error {
	b, _ := json.Marshal(thresholds)
	_, err := st.DB.Exec(`UPDATE ssl_certificates SET ssl_notified_thresholds = ?, last_notified = ? WHERE site_id = ?`,
		string(b), lastNotified, siteID)
	return err
}

// --- notify config / app settings ---

func (st *Store) LoadNotifyConfig() (string, error) {
	var cfg sql.NullString
	err := st.DB.QueryRow(`SELECT config FROM notify_config WHERE id = 1`).Scan(&cfg)
	if err != nil && err != sql.ErrNoRows {
		return "", err
	}
	return cfg.String, nil
}

func (st *Store) SaveNotifyConfig(config string) error {
	_, err := st.DB.Exec(`INSERT OR REPLACE INTO notify_config (id, config) VALUES (1, ?)`, config)
	return err
}

type AppSettings struct {
	ID               int64  `json:"id"`
	DisplayAddress   string `json:"display_address"`
	SiteTitle        string `json:"site_title"`
	LogoURL          string `json:"logo_url"`
	FooterText       string `json:"footer_text"`
	PrimaryColor     string `json:"primary_color"`
	BrandAccentColor string `json:"brand_accent_color"`
}

func (st *Store) GetAppSettings() AppSettings {
	var a AppSettings
	err := st.DB.QueryRow(`SELECT id, display_address, site_title, logo_url, footer_text, primary_color, brand_accent_color FROM app_settings WHERE id = 1`).
		Scan(&a.ID, &a.DisplayAddress, &a.SiteTitle, &a.LogoURL, &a.FooterText, &a.PrimaryColor, &a.BrandAccentColor)
	if err != nil {
		// sql.ErrNoRows just means settings were never saved yet - defaults are
		// the correct, expected behavior. Anything else (disk I/O error,
		// corrupted database, connection pool exhaustion) is a real problem
		// that must not be silently masked as "using defaults", or an
		// operator has no signal that the database itself is unhealthy.
		if err != sql.ErrNoRows {
			slog.Error("GetAppSettings: query failed, falling back to defaults", "error", err)
		}
		return AppSettings{ID: 1, SiteTitle: "Uptime Monitor", PrimaryColor: "#00ff88", BrandAccentColor: "#06b6d4"}
	}
	return a
}

func (st *Store) SaveAppSettings(a AppSettings) error {
	_, err := st.DB.Exec(`INSERT OR REPLACE INTO app_settings (id, display_address, site_title, logo_url, footer_text, primary_color, brand_accent_color)
	  VALUES (1,?,?,?,?,?,?)`, a.DisplayAddress, a.SiteTitle, a.LogoURL, a.FooterText, a.PrimaryColor, a.BrandAccentColor)
	return err
}

// --- notification history / audit / backups ---

func (st *Store) LogNotification(siteID int64, siteName, method, status, preview string) error {
	// site_id <= 0 is the sentinel used for notifications with no real site
	// behind them (e.g. the admin "send test notification" button). Store it
	// as NULL rather than the literal value: notification_history.site_id now
	// has a FOREIGN KEY on sites(id), and site id 0 never exists (AUTOINCREMENT
	// starts at 1), so inserting it literally would violate the constraint.
	var siteIDArg any
	if siteID > 0 {
		siteIDArg = siteID
	}
	_, err := st.DB.Exec(`INSERT INTO notification_history (site_id, site_name, method, status, message_preview, sent_at)
	  VALUES (?,?,?,?,?,?)`, siteIDArg, siteName, method, status, truncate(preview, 200), Now())
	return err
}

func (st *Store) NotificationHistory(limit int) ([]map[string]any, error) {
	rows, err := st.DB.Query(`SELECT * FROM notification_history ORDER BY id DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return rowsToMaps(rows)
}

func (st *Store) LogAudit(userID int64, username, action, targetType, targetID, details string) error {
	_, err := st.DB.Exec(`INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, created_at)
	  VALUES (?,?,?,?,?,?,?)`, userID, username, action, targetType, targetID, details, Now())
	return err
}

func (st *Store) AuditLog(limit int) ([]map[string]any, error) {
	rows, err := st.DB.Query(`SELECT * FROM audit_log ORDER BY id DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return rowsToMaps(rows)
}

func rowsToMaps(rows *sql.Rows) ([]map[string]any, error) {
	cols, err := rows.Columns()
	if err != nil {
		return nil, err
	}
	out := make([]map[string]any, 0)
	for rows.Next() {
		vals := make([]any, len(cols))
		ptrs := make([]any, len(cols))
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		if err := rows.Scan(ptrs...); err != nil {
			return nil, err
		}
		m := map[string]any{}
		for i, c := range cols {
			switch v := vals[i].(type) {
			case []byte:
				m[c] = string(v)
			case int64:
				m[c] = v
			case float64:
				m[c] = v
			case bool:
				m[c] = v
			case nil:
				m[c] = nil
			default:
				m[c] = v
			}
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func truncate(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

// --- backups ---

func (st *Store) CreateBackup(dir string) (map[string]any, error) {
	st.mu <- struct{}{}
	defer func() { <-st.mu }()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, err
	}
	filename := "backup_" + time.Now().Format("20060102_150405") + ".db"
	dst := filepath.Join(dir, filename)
	if _, err := st.DB.Exec(fmt.Sprintf("VACUUM INTO %q", filepath.ToSlash(dst))); err != nil {
		return nil, fmt.Errorf("backup: %w", err)
	}
	var siteCount int
	_ = st.DB.QueryRow(`SELECT COUNT(*) FROM sites`).Scan(&siteCount)
	info, err := os.Stat(dst)
	if err != nil {
		return nil, fmt.Errorf("stat backup file: %w", err)
	}
	if _, err := st.DB.Exec(`INSERT INTO backups (filename, filepath, size_bytes, site_count, created_at) VALUES (?,?,?,?,?)`,
		filename, dst, info.Size(), siteCount, Now()); err != nil {
		// Without this, a crash/error between VACUUM INTO succeeding and the
		// row insert would leave the file on disk forever: invisible to
		// Backups()/DeleteBackup (which only see rows in the table), so it
		// can never be cleaned up or count against max_backups rotation.
		_ = os.Remove(dst)
		return nil, fmt.Errorf("record backup: %w", err)
	}
	return map[string]any{"filename": filename, "path": dst, "site_count": siteCount}, nil
}

func (st *Store) Backups(limit int) ([]map[string]any, error) {
	rows, err := st.DB.Query(`SELECT * FROM backups ORDER BY id DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return rowsToMaps(rows)
}

// DeleteBackup removes a backup record and its file from disk.
func (st *Store) DeleteBackup(id int64) error {
	var fp string
	if err := st.DB.QueryRow(`SELECT filepath FROM backups WHERE id = ?`, id).Scan(&fp); err != nil {
		return err
	}
	// File first, DB row second: if removing the file fails (permissions,
	// still open elsewhere, etc.) the row must survive so the backup stays
	// visible in the UI and the delete can be retried. Doing it in the
	// other order (as before) meant a failed os.Remove left a file on disk
	// with no corresponding row - invisible to Backups(), impossible to
	// retry deleting through the app, and never rotated out.
	if err := os.Remove(fp); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("remove backup file: %w", err)
	}
	if _, err := st.DB.Exec(`DELETE FROM backups WHERE id = ?`, id); err != nil {
		return err
	}
	return nil
}

func (st *Store) RestoreBackup(id int64) (string, error) {
	st.mu <- struct{}{}
	defer func() { <-st.mu }()
	var filename, filepathS string
	err := st.DB.QueryRow(`SELECT filename, filepath FROM backups WHERE id = ?`, id).Scan(&filename, &filepathS)
	if err != nil {
		return "", fmt.Errorf("backup not found: %w", err)
	}
	return st.restoreFromPath(filepathS)
}

// RestoreBackupFile restores a backup by filename from the given directory.
func (st *Store) RestoreBackupFile(dir, filename string) (string, error) {
	if strings.Contains(filename, "..") || strings.ContainsAny(filename, `/\`) {
		return "", fmt.Errorf("invalid backup filename")
	}
	st.mu <- struct{}{}
	defer func() { <-st.mu }()
	return st.restoreFromPath(filepath.Join(dir, filename))
}

// restoreFromPath overwrites the live database file with a backup and
// reopens it. Every failure path returns a specific, actionable error
// instead of swallowing the cause - an operator running this during a
// database emergency needs to know exactly what went wrong (backup missing,
// permissions, disk full, etc.), not just "it didn't work". The final defer
// unconditionally attempts to reopen the database file, whatever ended up on
// disk: leaving st.DB closed after a failed step here would take down every
// subsequent query against this Store until the process restarts.
func (st *Store) restoreFromPath(src string) (result string, err error) {
	if _, statErr := os.Stat(src); statErr != nil {
		return "", fmt.Errorf("backup file not found: %w", statErr)
	}
	if closeErr := st.DB.Close(); closeErr != nil {
		return "", fmt.Errorf("close current database: %w", closeErr)
	}
	defer func() {
		newDB, abs, openErr := Open(st.DBPath)
		if openErr != nil {
			if err == nil {
				err = fmt.Errorf("reopen database after restore: %w", openErr)
			} else {
				err = fmt.Errorf("%w (additionally, reopening the database failed: %v)", err, openErr)
			}
			return
		}
		st.DB = newDB
		st.DBPath = abs
	}()
	for _, sidecar := range []string{st.DBPath + "-wal", st.DBPath + "-shm"} {
		_ = os.Remove(sidecar)
	}
	data, readErr := os.ReadFile(src)
	if readErr != nil {
		return "", fmt.Errorf("read backup file: %w", readErr)
	}
	if writeErr := os.WriteFile(st.DBPath, data, 0o644); writeErr != nil {
		return "", fmt.Errorf("write database file: %w", writeErr)
	}
	return src, nil
}

// --- maintenance windows ---

type MaintenanceWindow struct {
	ID              int64   `json:"id"`
	Name            string  `json:"name"`
	SiteID          *int64  `json:"site_id"`
	SiteName        *string `json:"site_name"`
	RuleType        string  `json:"rule_type"`
	StartTime       *string `json:"start_time"`
	EndTime         *string `json:"end_time"`
	DayOfWeek       *int    `json:"day_of_week"`
	StartHourMinute *string `json:"start_hour_minute"`
	DurationMinutes *int    `json:"duration_minutes"`
	IsActive        bool    `json:"is_active"`
}

func (st *Store) MaintenanceWindows() ([]MaintenanceWindow, error) {
	rows, err := st.DB.Query(`SELECT mw.*, s.name as site_name FROM maintenance_windows mw LEFT JOIN sites s ON mw.site_id = s.id ORDER BY mw.id DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]MaintenanceWindow, 0)
	for rows.Next() {
		var w MaintenanceWindow
		var siteID, siteName sql.NullString
		var startT, endT, dow, shm, dur sql.NullString
		var active int
		if err := rows.Scan(&w.ID, &w.Name, &siteID, &w.RuleType, &startT, &endT, &dow, &shm, &dur, &active, &siteName); err != nil {
			return nil, err
		}
		if siteID.Valid {
			id, _ := strconv.ParseInt(siteID.String, 10, 64)
			w.SiteID = &id
		}
		if siteName.Valid {
			v := siteName.String
			w.SiteName = &v
		}
		w.StartTime = nullStrPtr(startT)
		w.EndTime = nullStrPtr(endT)
		if dow.Valid {
			d, _ := strconv.Atoi(dow.String)
			w.DayOfWeek = &d
		}
		w.StartHourMinute = nullStrPtr(shm)
		if dur.Valid {
			d, _ := strconv.Atoi(dur.String)
			w.DurationMinutes = &d
		}
		w.IsActive = active == 1
		out = append(out, w)
	}
	return out, rows.Err()
}

func (st *Store) AddMaintenanceWindow(name string, siteID *int64, ruleType string, startTime, endTime *string, dow *int, startHM *string, duration *int) (int64, error) {
	res, err := st.DB.Exec(`INSERT INTO maintenance_windows (name, site_id, rule_type, start_time, end_time, day_of_week, start_hour_minute, duration_minutes, is_active)
	  VALUES (?,?,?,?,?,?,?,?,1)`, name, siteID, ruleType, startTime, endTime, dow, startHM, duration)
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func (st *Store) DeleteMaintenanceWindow(id int64) error {
	_, err := st.DB.Exec(`DELETE FROM maintenance_windows WHERE id = ?`, id)
	return err
}

func (st *Store) ToggleMaintenanceWindow(id int64, active bool) error {
	a := 0
	if active {
		a = 1
	}
	_, err := st.DB.Exec(`UPDATE maintenance_windows SET is_active = ? WHERE id = ?`, a, id)
	return err
}

func (st *Store) Tags() ([]string, error) {
	rows, err := st.DB.Query(`SELECT tags FROM sites WHERE tags IS NOT NULL AND tags != '[]'`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	set := map[string]bool{}
	for rows.Next() {
		var raw sql.NullString
		if err := rows.Scan(&raw); err != nil {
			continue
		}
		var list []string
		if json.Unmarshal([]byte(raw.String), &list) == nil {
			for _, t := range list {
				set[t] = true
			}
		}
	}
	var out []string
	for t := range set {
		out = append(out, t)
	}
	return out, nil
}
