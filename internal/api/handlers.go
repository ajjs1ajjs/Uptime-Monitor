package api

import (
	"context"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/auth"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/config"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/notify"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"
)

var hexColorRe = regexp.MustCompile(`^#[0-9a-fA-F]{6}$`)

// --- health / metrics ---

func (a *App) handleHealth(w http.ResponseWriter, r *http.Request) {
	status := "healthy"
	if _, err := a.Store.DB.Exec(`SELECT 1`); err != nil {
		status = "degraded"
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status": status, "timestamp": time.Now().UTC().Format(time.RFC3339),
		"checks":  map[string]any{"database": "ok", "monitor_thread": "ok"},
		"version": a.Version,
	})
}

func (a *App) handlePrometheus(w http.ResponseWriter, r *http.Request) {
	var sb strings.Builder
	sites, _ := a.Store.GetSites()
	var up, down, maint, paused int
	for _, s := range sites {
		switch s.Status {
		case "up":
			up++
		case "down":
			down++
		case "maintenance":
			maint++
		case "paused":
			paused++
		}
	}
	fmt.Fprintf(&sb, "# HELP uptime_monitor_sites_total Total monitors\n# TYPE uptime_monitor_sites_total gauge\nuptime_monitor_sites_total %d\n", len(sites))
	fmt.Fprintf(&sb, "uptime_monitor_sites_up %d\n", up)
	fmt.Fprintf(&sb, "uptime_monitor_sites_down %d\n", down)
	fmt.Fprintf(&sb, "uptime_monitor_sites_maintenance %d\n", maint)
	fmt.Fprintf(&sb, "uptime_monitor_sites_paused %d\n", paused)
	fmt.Fprintf(&sb, "# HELP uptime_monitor_info Version info\n# TYPE uptime_monitor_info gauge\nuptime_monitor_info{version=%q} 1\n", a.Version)
	w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
	_, _ = w.Write([]byte(sb.String()))
}

// --- sites ---

func siteToMap(s storage.Site) map[string]any {
	nm := []any{}
	if err := json.Unmarshal([]byte(s.NotifyMethods), &nm); err != nil {
		nm = []any{}
	}
	if nm == nil {
		nm = []any{}
	}
	tags := []any{}
	if err := json.Unmarshal([]byte(s.Tags), &tags); err != nil {
		tags = []any{}
	}
	if tags == nil {
		tags = []any{}
	}
	return map[string]any{
		"id": s.ID, "name": s.Name, "url": s.URL, "check_interval": s.CheckInterval,
		"is_active": s.IsActive, "last_notification": s.LastNotification,
		"notify_methods": nm, "status": s.Status, "status_code": s.StatusCode,
		"response_time": s.ResponseTime, "error_message": s.ErrorMessage,
		"monitor_type": s.MonitorType, "failed_attempts": s.FailedAttempts,
		"success_attempts": s.SuccessAttempts, "last_down_alert": s.LastDownAlert,
		"first_failure_at": s.FirstFailureAt, "keyword": s.Keyword, "tags": tags,
		"silenced_until": s.SilencedUntil, "acknowledged": s.Acknowledged, "uptime": s.Uptime,
	}
}

func (a *App) handleListSites(w http.ResponseWriter, r *http.Request) {
	sites, err := a.Store.GetSites()
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	out := make([]map[string]any, 0, len(sites))
	for _, s := range sites {
		out = append(out, siteToMap(s))
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *App) handleCreateSite(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Name          string   `json:"name"`
		URL           string   `json:"url"`
		CheckInterval int      `json:"check_interval"`
		IsActive      *bool    `json:"is_active"`
		NotifyMethods []any    `json:"notify_methods"`
		MonitorType   string   `json:"monitor_type"`
		Keyword       *string  `json:"keyword"`
		Tags          []string `json:"tags"`
	}
	if err := decodeJSON(w, r, &body); err != nil {
		writeErr(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	mType := strings.ToLower(body.MonitorType)
	if mType == "" {
		mType = "http"
	}
	rawURL, err := a.normalizeURL(body.URL, mType)
	if err != nil {
		writeErr(w, http.StatusBadRequest, err.Error())
		return
	}
	interval := body.CheckInterval
	if interval == 0 {
		interval = 60
	}
	if interval < 5 || interval > 86400 {
		writeErr(w, http.StatusBadRequest, "check_interval must be 5..86400")
		return
	}
	active := true
	if body.IsActive != nil {
		active = *body.IsActive
	}
	nmJSON, _ := json.Marshal(body.NotifyMethods)
	if string(nmJSON) == "null" {
		nmJSON = []byte("[]")
	}
	tagsJSON, _ := json.Marshal(body.Tags)
	if string(tagsJSON) == "null" {
		tagsJSON = []byte("[]")
	}
	kw := ""
	if body.Keyword != nil {
		kw = *body.Keyword
	}
	id, err := a.Store.CreateSite(body.Name, rawURL, interval, active, string(nmJSON), mType, kw, string(tagsJSON))
	if err != nil {
		if strings.Contains(err.Error(), "UNIQUE") {
			writeErr(w, http.StatusBadRequest, "Monitor with this URL already exists")
			return
		}
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	p := a.principal(r)
	_ = a.Store.LogAudit(p.UserID, p.Username, "site_created", "site", strconv.FormatInt(id, 10), "name="+body.Name+", url="+rawURL)
	writeJSON(w, http.StatusOK, map[string]any{"id": id, "message": "Site added"})
}

func (a *App) handleUpdateSite(w http.ResponseWriter, r *http.Request) {
	id, _ := pathInt(r, "site_id")
	s, err := a.Store.GetSite(id)
	if err != nil || s == nil {
		writeErr(w, http.StatusNotFound, "Site not found")
		return
	}
	var body map[string]any
	if err := decodeJSON(w, r, &body); err != nil {
		writeErr(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	fields := map[string]any{}
	monitorType := s.MonitorType
	if v, ok := body["monitor_type"].(string); ok && v != "" {
		monitorType = strings.ToLower(v)
		fields["monitor_type"] = monitorType
	}
	if v, ok := body["name"].(string); ok {
		fields["name"] = v
	}
	if v, ok := body["url"].(string); ok {
		u, err := a.normalizeURL(v, monitorType)
		if err != nil {
			writeErr(w, http.StatusBadRequest, err.Error())
			return
		}
		fields["url"] = u
	}
	if v, ok := body["check_interval"].(float64); ok {
		fields["check_interval"] = int(v)
	}
	if v, ok := body["is_active"].(bool); ok {
		fields["is_active"] = v
	}
	if v, ok := body["notify_methods"]; ok {
		b, _ := json.Marshal(v)
		fields["notify_methods"] = string(b)
	}
	if v, ok := body["monitor_type"]; ok {
		_ = v
	}
	if v, ok := body["keyword"]; ok {
		if vs, isStr := v.(string); isStr {
			fields["keyword"] = &vs
		} else {
			fields["keyword"] = nil
		}
	}
	if v, ok := body["tags"]; ok {
		b, _ := json.Marshal(v)
		fields["tags"] = string(b)
	}
	if err := a.Store.UpdateSite(id, fields); err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"message": "Updated"})
}

func (a *App) handleDeleteSite(w http.ResponseWriter, r *http.Request) {
	id, _ := pathInt(r, "site_id")
	before, _ := a.Store.GetSite(id)
	if err := a.Store.DeleteSite(id); err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	if before != nil {
		p := a.principal(r)
		_ = a.Store.LogAudit(p.UserID, p.Username, "site_deleted", "site", strconv.FormatInt(id, 10), "")
	}
	writeJSON(w, http.StatusOK, map[string]any{"message": "Deleted"})
}

func (a *App) handleManualCheck(w http.ResponseWriter, r *http.Request) {
	id, _ := pathInt(r, "site_id")
	s, err := a.Store.GetSite(id)
	if err != nil || s == nil {
		writeErr(w, http.StatusNotFound, "Site not found")
		return
	}
	if a.Worker != nil {
		a.Worker.CheckSite(r.Context(), s)
	}
	writeJSON(w, http.StatusOK, map[string]any{"message": "Check triggered"})
}

func (a *App) handleHistoryAll(w http.ResponseWriter, r *http.Request) {
	hist, err := a.Store.HistoryAll()
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	// ensure non-nil arrays
	for k, v := range hist {
		if v == nil {
			hist[k] = []map[string]any{}
		}
	}
	writeJSON(w, http.StatusOK, hist)
}

func (a *App) handleSiteHistory(w http.ResponseWriter, r *http.Request) {
	id, _ := pathInt(r, "site_id")
	limit := 50
	if v := r.URL.Query().Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 && n <= 500 {
			limit = n
		}
	}
	hist, err := a.Store.SiteHistory(id, limit)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	writeJSON(w, http.StatusOK, hist)
}

func (a *App) handleServerTime(w http.ResponseWriter, r *http.Request) {
	now := time.Now().UTC()
	writeJSON(w, http.StatusOK, map[string]any{
		"timestamp": now.Unix(), "iso": now.Format("2006-01-02T15:04:05.000000+00:00"), "timezone": "UTC",
	})
}

// --- SSL ---

func (a *App) handleListSSLCerts(w http.ResponseWriter, r *http.Request) {
	certs, err := a.Store.GetSSLCertificates()
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	out := make([]storage.SSLCert, 0, len(certs))
	out = append(out, certs...)
	writeJSON(w, http.StatusOK, out)
}

func (a *App) handleSSLCheckAll(w http.ResponseWriter, r *http.Request) {
	if a.Worker != nil {
		a.Worker.CheckAllCertificates()
	}
	writeJSON(w, http.StatusOK, map[string]any{"message": "SSL check triggered"})
}

// --- stats / incidents ---

func (a *App) handleResponseTime(w http.ResponseWriter, r *http.Request) {
	rows, err := a.Store.DB.Query(`SELECT site_id, s.name, AVG(sh.response_time), MIN(sh.response_time), MAX(sh.response_time), COUNT(*)
	  FROM status_history sh JOIN sites s ON sh.site_id = s.id
	  WHERE sh.checked_at >= datetime('now','-24 hours') AND sh.response_time IS NOT NULL
	  GROUP BY site_id ORDER BY 3 ASC`)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	defer rows.Close()
	out := make([]map[string]any, 0)
	for rows.Next() {
		var sid int64
		var name string
		var avg, mn, mx sqlNullFloat
		var checks int
		if err := rows.Scan(&sid, &name, &avg, &mn, &mx, &checks); err != nil {
			continue
		}
		out = append(out, map[string]any{
			"site_id": sid, "site_name": name,
			"avg_time": round1(avg.f), "min_time": round1(mn.f),
			"max_time": round1(mx.f), "checks": checks,
		})
	}
	writeJSON(w, http.StatusOK, out)
}

type sqlNullFloat struct {
	f     float64
	valid bool
}

func (n *sqlNullFloat) Scan(v any) error {
	if v == nil {
		n.valid = false
		n.f = 0
		return nil
	}
	switch x := v.(type) {
	case float64:
		n.f = x
	case int64:
		n.f = float64(x)
	case []byte:
		n.f, _ = strconv.ParseFloat(string(x), 64)
	default:
		n.f = 0
	}
	n.valid = true
	return nil
}

func round1(f float64) float64 { return float64(int(f*10+0.5)) / 10 }

func (a *App) handleIncidents(w http.ResponseWriter, r *http.Request) {
	// Group consecutive down/slow checks into one incident per outage:
	// an incident starts when a check differs from the previous check's status
	// and ends when the status returns to up. Rows are compared in time order.
	rows, err := a.Store.DB.Query(`
	  WITH seq AS (
	    SELECT sh.id, sh.site_id, s.name, s.url, sh.status, sh.status_code,
	           sh.response_time, sh.error_message, sh.checked_at,
	           LAG(sh.status) OVER (PARTITION BY sh.site_id ORDER BY sh.checked_at, sh.id) AS prev_status
	    FROM status_history sh JOIN sites s ON sh.site_id = s.id
	    WHERE sh.checked_at >= datetime('now','-7 days')
	  )
	  SELECT id, site_id, name, url, status, status_code, response_time,
	         error_message, checked_at, prev_status
	  FROM seq
	  WHERE status IN ('down','slow')
	  ORDER BY checked_at DESC, id DESC
	  LIMIT 200`)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	defer rows.Close()
	out := make([]map[string]any, 0)
	for rows.Next() {
		var id, sid int64
		var name, siteURL, status string
		var code sqlNullInt
		var rt sqlNullFloat
		var errMsg sqlNullString
		var checkedAt string
		var prev sqlNullString
		if err := rows.Scan(&id, &sid, &name, &siteURL, &status, &code, &rt, &errMsg, &checkedAt, &prev); err != nil {
			continue
		}
		// only the first check of an outage is a new incident
		if prev.s == status {
			continue
		}
		out = append(out, map[string]any{
			"id": id, "site_id": sid, "site_name": name, "site_url": siteURL,
			"status": status, "status_code": code.v, "response_time": rt.f,
			"error_message": errMsg.s, "checked_at": checkedAt,
			"prev_status": prev.s, "duration": nil,
		})
		if len(out) >= 100 {
			break
		}
	}
	writeJSON(w, http.StatusOK, out)
}

type sqlNullInt struct {
	v     any
	valid bool
}

func (n *sqlNullInt) Scan(v any) error {
	if v == nil {
		n.v = nil
		n.valid = false
		return nil
	}
	switch x := v.(type) {
	case int64:
		n.v = x
	case float64:
		n.v = int64(x)
	case []byte:
		n.v, _ = strconv.ParseInt(string(x), 10, 64)
	default:
		n.v = nil
	}
	n.valid = true
	return nil
}

type sqlNullString struct {
	s string
}

func (n *sqlNullString) Scan(v any) error {
	if v == nil {
		n.s = ""
		return nil
	}
	switch x := v.(type) {
	case []byte:
		n.s = string(x)
	case string:
		n.s = x
	default:
		n.s = ""
	}
	return nil
}

// --- notify / app settings ---

func (a *App) handleSaveNotify(w http.ResponseWriter, r *http.Request) {
	var body map[string]any
	if err := decodeJSON(w, r, &body); err != nil {
		writeErr(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	existing := a.Notify.LoadSettings()
	for k, v := range body {
		if v != nil {
			existing[k] = v
		}
	}
	enc := notify.EncryptSecrets(existing)
	b, _ := json.Marshal(enc)
	if err := a.Store.SaveNotifyConfig(string(b)); err != nil {
		writeErr(w, http.StatusServiceUnavailable, "Could not save settings (encryption unavailable)")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"message": "Saved"})
}

func (a *App) handleGetAppSettings(w http.ResponseWriter, r *http.Request) {
	s := a.Store.GetAppSettings()
	writeJSON(w, http.StatusOK, map[string]any{
		"display_address": s.DisplayAddress, "site_title": s.SiteTitle,
		"logo_url": s.LogoURL, "footer_text": s.FooterText,
		"primary_color": s.PrimaryColor, "brand_accent_color": s.BrandAccentColor,
	})
}

func (a *App) handleSaveAppSettings(w http.ResponseWriter, r *http.Request) {
	var body map[string]any
	if err := decodeJSON(w, r, &body); err != nil {
		writeErr(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	cur := a.Store.GetAppSettings()
	if v, ok := body["display_address"].(string); ok {
		cur.DisplayAddress = clip(v, 500)
	}
	if v, ok := body["site_title"].(string); ok {
		cur.SiteTitle = clipDefault(v, "Uptime Monitor", 120)
	}
	if v, ok := body["logo_url"].(string); ok {
		cur.LogoURL = safeLogoURL(v)
	}
	if v, ok := body["footer_text"].(string); ok {
		cur.FooterText = clip(v, 500)
	}
	if v, ok := body["primary_color"].(string); ok {
		cur.PrimaryColor = safeColor(v, "#00ff88")
	}
	if v, ok := body["brand_accent_color"].(string); ok {
		cur.BrandAccentColor = safeColor(v, "#06b6d4")
	}
	if err := a.Store.SaveAppSettings(cur); err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"message": "Saved"})
}

func (a *App) handleGetAlertPolicy(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, alertPolicyToMap(a.Cfg.AlertPolicy))
}

func (a *App) handleSaveAlertPolicy(w http.ResponseWriter, r *http.Request) {
	var body map[string]any
	if err := decodeJSON(w, r, &body); err != nil {
		writeErr(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	ap := &a.Cfg.AlertPolicy
	if v, ok := body["request_timeout_seconds"].(float64); ok {
		ap.RequestTimeoutSeconds = clamp(int(v), 1, 300)
	}
	if v, ok := body["grace_period_seconds"].(float64); ok {
		ap.GracePeriodSeconds = clamp(int(v), 0, 3600)
	}
	if v, ok := body["up_success_threshold"].(float64); ok {
		ap.UpSuccessThreshold = clamp(int(v), 1, 20)
	}
	if v, ok := body["still_down_repeat_seconds"].(float64); ok {
		ap.StillDownRepeatSeconds = clamp(int(v), 60, 86400)
	}
	if v, ok := body["treat_4xx_as_down"].(bool); ok {
		ap.Treat4xxAsDown = v
	}
	if v, ok := body["verify_ssl"].(bool); ok {
		ap.VerifySSL = v
	}
	if v, ok := body["ssl_notification_days"].([]any); ok {
		var days []int
		for _, d := range v {
			if f, ok := d.(float64); ok {
				days = append(days, int(f))
			}
		}
		sort.Sort(sort.Reverse(sort.IntSlice(days)))
		ap.SSLNotificationDays = days
	}
	if v, ok := body["ssl_notification_cooldown_seconds"].(float64); ok {
		ap.SSLNotificationCooldown = clamp(int(v), 300, 86400)
	}
	if v, ok := body["ssl_check_interval_hours"].(float64); ok {
		ap.SSLCheckIntervalHours = clamp(int(v), 1, 168)
	}
	if v, ok := body["max_retries"].(float64); ok {
		ap.MaxRetries = clamp(int(v), 0, 10)
	}
	if v, ok := body["retry_delays"].([]any); ok {
		var delays []int
		for _, d := range v {
			if f, ok := d.(float64); ok {
				delays = append(delays, int(f))
			}
		}
		ap.RetryDelays = delays
	}
	if err := a.Cfg.Save(); err != nil {
		writeErr(w, http.StatusInternalServerError, "Could not persist alert policy: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"message": "Saved"})
}

func alertPolicyToMap(ap config.AlertPolicy) map[string]any {
	return map[string]any{
		"request_timeout_seconds":           ap.RequestTimeoutSeconds,
		"grace_period_seconds":              ap.GracePeriodSeconds,
		"up_success_threshold":              ap.UpSuccessThreshold,
		"still_down_repeat_seconds":         ap.StillDownRepeatSeconds,
		"treat_4xx_as_down":                 ap.Treat4xxAsDown,
		"verify_ssl":                        ap.VerifySSL,
		"ssl_notification_days":             ap.SSLNotificationDays,
		"ssl_notification_cooldown_seconds": ap.SSLNotificationCooldown,
		"ssl_check_interval_hours":          ap.SSLCheckIntervalHours,
		"retry_delays":                      ap.RetryDelays,
		"max_retries":                       ap.MaxRetries,
	}
}

func clip(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

func clipDefault(s, def string, n int) string {
	s = strings.TrimSpace(s)
	if s == "" {
		return def
	}
	return clip(s, n)
}

func safeColor(v, def string) string {
	if hexColorRe.MatchString(strings.TrimSpace(v)) {
		return strings.TrimSpace(v)
	}
	return def
}

func safeLogoURL(v string) string {
	v = strings.TrimSpace(v)
	if v == "" {
		return ""
	}
	u, err := url.Parse(v)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
		return ""
	}
	return v
}

func clamp(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

// --- users (API) ---

func (a *App) handleGetUser(w http.ResponseWriter, r *http.Request) {
	p := a.principal(r)
	u, err := a.Store.GetUserByID(p.UserID)
	if err != nil || u == nil {
		writeErr(w, http.StatusUnauthorized, "User not found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"username": u.Username, "role": u.Role, "is_admin": u.Role == "admin",
	})
}

func (a *App) handleListUsersAPI(w http.ResponseWriter, r *http.Request) {
	users, err := a.Store.ListUsers()
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	out := make([]map[string]any, 0, len(users))
	for _, u := range users {
		out = append(out, map[string]any{
			"id": u.ID, "username": u.Username, "role": u.Role,
			"created_at": u.CreatedAt, "last_login": u.LastLogin,
		})
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *App) handleCreateUserAPI(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Username string `json:"username"`
		Password string `json:"password"`
		Role     string `json:"role"`
	}
	if err := decodeJSON(w, r, &body); err != nil {
		writeErr(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	if body.Role != "admin" && body.Role != "viewer" {
		writeErr(w, http.StatusBadRequest, "Invalid role. Must be 'admin' or 'viewer'")
		return
	}
	if ok, msg := auth.CheckPasswordPolicy(body.Password); !ok {
		writeErr(w, http.StatusBadRequest, msg)
		return
	}
	username := strings.TrimSpace(body.Username)
	if username == "" {
		writeErr(w, http.StatusBadRequest, "Username required")
		return
	}
	hash, err := auth.HashPassword(body.Password)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Hashing failed")
		return
	}
	if _, err := a.Store.CreateUser(username, hash, body.Role); err != nil {
		if strings.Contains(err.Error(), "UNIQUE") {
			writeErr(w, http.StatusBadRequest, "Username already exists")
			return
		}
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	p := a.principal(r)
	_ = a.Store.LogAudit(p.UserID, p.Username, "user_created", "user", username, "role="+body.Role)
	writeJSON(w, http.StatusOK, map[string]any{"message": "User '" + username + "' created with role '" + body.Role + "'"})
}

func (a *App) handleUpdateUserAPI(w http.ResponseWriter, r *http.Request) {
	username := r.PathValue("username")
	var body struct {
		Role     string `json:"role"`
		Password string `json:"password"`
	}
	if err := decodeJSON(w, r, &body); err != nil {
		writeErr(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	u, err := a.Store.GetUserByUsername(username)
	if err != nil || u == nil {
		writeErr(w, http.StatusNotFound, "User not found")
		return
	}
	p := a.principal(r)
	if body.Role != "" {
		if body.Role != "admin" && body.Role != "viewer" {
			writeErr(w, http.StatusBadRequest, "Invalid role")
			return
		}
		if body.Role == "viewer" && u.Role == "admin" {
			n, _ := a.Store.CountAdmins()
			if n <= 1 {
				writeErr(w, http.StatusBadRequest, "Cannot demote the last admin")
				return
			}
		}
		_ = a.Store.UpdateUser(u.ID, map[string]any{"role": body.Role})
		_ = a.Store.LogAudit(p.UserID, p.Username, "user_role_updated", "user", username, "new_role="+body.Role)
		writeJSON(w, http.StatusOK, map[string]any{"message": "User '" + username + "' role updated to '" + body.Role + "'"})
		return
	}
	if body.Password != "" {
		if ok, msg := auth.CheckPasswordPolicy(body.Password); !ok {
			writeErr(w, http.StatusBadRequest, msg)
			return
		}
		hash, err := auth.HashPassword(body.Password)
		if err != nil {
			writeErr(w, http.StatusInternalServerError, "Hashing failed")
			return
		}
		_ = a.Store.UpdateUser(u.ID, map[string]any{"password_hash": hash, "must_change_password": 1})
		_ = a.Store.DeleteUserSessions(u.ID)
		_ = a.Store.LogAudit(p.UserID, p.Username, "user_password_reset", "user", username, "")
		writeJSON(w, http.StatusOK, map[string]any{"message": "Password updated for user '" + username + "'"})
		return
	}
	writeErr(w, http.StatusBadRequest, "No updates provided")
}

func (a *App) handleDeleteUserAPI(w http.ResponseWriter, r *http.Request) {
	username := r.PathValue("username")
	p := a.principal(r)
	if username == p.Username {
		writeErr(w, http.StatusBadRequest, "Cannot delete yourself")
		return
	}
	u, err := a.Store.GetUserByUsername(username)
	if err != nil || u == nil {
		writeErr(w, http.StatusBadRequest, "User not found")
		return
	}
	if u.Role == "admin" {
		n, _ := a.Store.CountAdmins()
		if n <= 1 {
			writeErr(w, http.StatusBadRequest, "Cannot delete the last admin")
			return
		}
	}
	if err := a.Store.DeleteUser(u.ID); err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	_ = a.Store.LogAudit(p.UserID, p.Username, "user_deleted", "user", username, "")
	writeJSON(w, http.StatusOK, map[string]any{"message": "User '" + username + "' deleted"})
}

// --- maintenance windows ---

func (a *App) handleListMaintenance(w http.ResponseWriter, r *http.Request) {
	windows, err := a.Store.MaintenanceWindows()
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	writeJSON(w, http.StatusOK, windows)
}

func (a *App) handleCreateMaintenance(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Name            string  `json:"name"`
		SiteID          *int64  `json:"site_id"`
		RuleType        string  `json:"rule_type"`
		StartTime       *string `json:"start_time"`
		EndTime         *string `json:"end_time"`
		DayOfWeek       *int    `json:"day_of_week"`
		StartHourMinute *string `json:"start_hour_minute"`
		DurationMinutes *int    `json:"duration_minutes"`
	}
	if err := decodeJSON(w, r, &body); err != nil {
		writeErr(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	if body.RuleType == "" {
		body.RuleType = "one_off"
	}
	id, err := a.Store.AddMaintenanceWindow(body.Name, body.SiteID, body.RuleType,
		body.StartTime, body.EndTime, body.DayOfWeek, body.StartHourMinute, body.DurationMinutes)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"id": id, "message": "Maintenance window added"})
}

func (a *App) handleDeleteMaintenance(w http.ResponseWriter, r *http.Request) {
	id, _ := pathInt(r, "window_id")
	if err := a.Store.DeleteMaintenanceWindow(id); err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"message": "Maintenance window deleted"})
}

func (a *App) handleToggleMaintenance(w http.ResponseWriter, r *http.Request) {
	id, _ := pathInt(r, "window_id")
	var body struct {
		IsActive bool `json:"is_active"`
	}
	if err := decodeJSON(w, r, &body); err != nil {
		writeErr(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	if err := a.Store.ToggleMaintenanceWindow(id, body.IsActive); err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"message": "Toggled"})
}

// --- SLA reports ---

func (a *App) slaReport(days int) ([]map[string]any, error) {
	sites, err := a.Store.GetSites()
	if err != nil {
		return nil, err
	}
	mod := fmt.Sprintf("-%d days", days)
	rows, err := a.Store.DB.Query(`SELECT site_id, COUNT(*), SUM(CASE WHEN status='up' THEN 1 ELSE 0 END),
	  SUM(CASE WHEN status IN ('down','slow') THEN 1 ELSE 0 END), AVG(response_time)
	  FROM status_history WHERE checked_at >= datetime('now', ?) GROUP BY site_id`, mod)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	stats := map[int64][4]float64{}
	for rows.Next() {
		var sid int64
		var total, upc, inc sqlNullFloat
		var avg sqlNullFloat
		if err := rows.Scan(&sid, &total, &upc, &inc, &avg); err != nil {
			continue
		}
		stats[sid] = [4]float64{total.f, upc.f, inc.f, avg.f}
	}
	out := make([]map[string]any, 0, len(sites))
	for _, s := range sites {
		st := stats[s.ID]
		uptime := 100.0
		if st[0] > 0 {
			uptime = st[1] / st[0] * 100
		}
		out = append(out, map[string]any{
			"id": s.ID, "name": s.Name, "url": s.URL,
			"uptime":            float64(int(uptime*100+0.5)) / 100,
			"avg_response_time": round1(st[3]),
			"total_checks":      int(st[0]), "incidents": int(st[2]),
		})
	}
	return out, nil
}

func (a *App) handleSLAResponse(w http.ResponseWriter, r *http.Request) {
	days := 7
	if v := r.URL.Query().Get("days"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			days = n
		}
	}
	rep, err := a.slaReport(days)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	writeJSON(w, http.StatusOK, rep)
}

func (a *App) handleSLAExport(w http.ResponseWriter, r *http.Request) {
	days := 7
	if v := r.URL.Query().Get("days"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			days = n
		}
	}
	rep, err := a.slaReport(days)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=sla_report_%ddays.csv", days))
	cw := csv.NewWriter(w)
	_ = cw.Write([]string{"ID", "Name", "URL", "Uptime %", "Avg Response Time (ms)", "Total Checks", "Incidents"})
	for _, item := range rep {
		_ = cw.Write([]string{
			fmt.Sprintf("%v", item["id"]),
			csvSafe(fmt.Sprintf("%v", item["name"])),
			csvSafe(fmt.Sprintf("%v", item["url"])),
			fmt.Sprintf("%v%%", item["uptime"]), fmt.Sprintf("%v", item["avg_response_time"]),
			fmt.Sprintf("%v", item["total_checks"]), fmt.Sprintf("%v", item["incidents"]),
		})
	}
	cw.Flush()
}

// csvSafe neutralizes spreadsheet formula injection: cells that begin with
// =, +, -, @ (or a tab/CR) are prefixed with a single quote so Excel and
// Google Sheets render them as text instead of executing a formula.
func csvSafe(v string) string {
	if v == "" {
		return v
	}
	switch v[0] {
	case '=', '+', '-', '@', '\t', '\r':
		return "'" + v
	}
	return v
}

func (a *App) handleSLAPDF(w http.ResponseWriter, r *http.Request) {
	days := 30
	if v := r.URL.Query().Get("days"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			days = n
		}
	}
	rep, err := a.slaReport(days)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	// HTML report that the browser can print to PDF (no weasyprint dependency).
	ctx := map[string]any{
		"days": days, "report": rep,
		"generated": time.Now().Format("2006-01-02 15:04"),
	}
	html, err := a.render("sla_report_pdf.html", ctx)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "PDF generation failed")
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=sla_report_%ddays.html", days))
	_, _ = w.Write([]byte(html))
}

// --- API keys ---

func (a *App) handleCreateAPIKey(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	p := a.principal(r)
	keyID, raw := auth.NewAPIKey()
	hash := auth.HashAPIKey(raw)
	if err := a.Store.CreateAPIKey(0, p.UserID, name, keyID, hash); err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	_ = a.Store.LogAudit(p.UserID, p.Username, "api_key_created", "api_key", keyID, "name="+name)
	writeJSON(w, http.StatusOK, map[string]any{"key_id": keyID, "api_key": raw, "name": name})
}

func (a *App) handleListAPIKeys(w http.ResponseWriter, r *http.Request) {
	keys, err := a.Store.ListAPIKeys()
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	writeJSON(w, http.StatusOK, keys)
}

func (a *App) handleRevokeAPIKey(w http.ResponseWriter, r *http.Request) {
	keyID := r.PathValue("key_id")
	p := a.principal(r)
	if err := a.Store.RevokeAPIKey(keyID); err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	_ = a.Store.LogAudit(p.UserID, p.Username, "api_key_revoked", "api_key", keyID, "")
	writeJSON(w, http.StatusOK, map[string]any{"status": "revoked"})
}

// --- audit / notification history / backups / tags ---

func (a *App) handleAuditLog(w http.ResponseWriter, r *http.Request) {
	limit := 200
	if v := r.URL.Query().Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			limit = n
		}
	}
	logs, err := a.Store.AuditLog(limit)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	writeJSON(w, http.StatusOK, logs)
}

func (a *App) handleNotificationHistory(w http.ResponseWriter, r *http.Request) {
	limit := 100
	if v := r.URL.Query().Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			limit = n
		}
	}
	hist, err := a.Store.NotificationHistory(limit)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	writeJSON(w, http.StatusOK, hist)
}

// handleTestNotify sends a test alert through every enabled notification
// channel so the admin can verify delivery without waiting for an outage.
func (a *App) handleTestNotify(w http.ResponseWriter, r *http.Request) {
	settings := a.Notify.LoadSettings()
	methods := []any{}
	for name, sec := range settings {
		m, ok := sec.(map[string]any)
		if !ok {
			continue
		}
		if on, ok := m["enabled"].(bool); ok && on {
			methods = append(methods, name)
		}
	}
	payload := map[string]any{
		"alert_type":     "test",
		"site_id":        int64(0),
		"site_name":      "Тестове сповіщення",
		"url":            "",
		"status_code":    0,
		"error":          "Це тестове повідомлення з Uptime Monitor.",
		"response_time":  float64(0),
		"checked_at":     storage.Now(),
		"notify_methods": methods,
	}
	a.Notify.Dispatch("test", "🧪 Тестове сповіщення з Uptime Monitor — канали працюють!", payload)
	writeJSON(w, http.StatusOK, map[string]any{"message": "Test notification dispatched", "methods": methods})
}

func (a *App) handleBackupCreate(w http.ResponseWriter, r *http.Request) {
	dir := a.Cfg.BackupDir()
	res, err := a.Store.CreateBackup(dir)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Backup failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, res)
}

func (a *App) handleBackupList(w http.ResponseWriter, r *http.Request) {
	dir := a.Cfg.BackupDir()
	backups, err := a.Store.Backups(20)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	_ = dir
	writeJSON(w, http.StatusOK, backups)
}

func (a *App) handleBackupRestore(w http.ResponseWriter, r *http.Request) {
	// Restore swaps the live DB file, which is unsafe while the server is
	// running (concurrent API and monitor queries would race the swap). It is
	// available only through the CLI with the service stopped.
	writeErr(w, http.StatusBadRequest,
		"Restore must be run with the service stopped via the CLI: uptime-monitor restore --backup <filename>")
}

func (a *App) handleTags(w http.ResponseWriter, r *http.Request) {
	tags, err := a.Store.Tags()
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Database error")
		return
	}
	if tags == nil {
		tags = []string{}
	}
	writeJSON(w, http.StatusOK, tags)
}

// --- helpers ---

// URL normalization + SSRF guard at creation time.
func (a *App) normalizeURL(raw string, monitorType string) (string, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "", fmt.Errorf("URL required")
	}
	if !strings.Contains(raw, "://") {
		raw = "http://" + raw
	}
	u, err := url.Parse(raw)
	if err != nil {
		return "", fmt.Errorf("Invalid URL")
	}
	if monitorType == "http" {
		if u.Scheme != "http" && u.Scheme != "https" {
			return "", fmt.Errorf("HTTP URL must start with http:// or https://")
		}
		if u.Hostname() == "" {
			return "", fmt.Errorf("Invalid host in URL")
		}
		if a.resolvesBlocked(u.Hostname()) {
			return "", fmt.Errorf("Invalid host in URL")
		}
	} else {
		host := u.Hostname()
		if host == "" {
			host = strings.Split(strings.TrimPrefix(u.Path, "/"), "/")[0]
		}
		if a.resolvesBlocked(host) {
			return "", fmt.Errorf("Invalid host/IP")
		}
	}
	return raw, nil
}

// resolvesBlocked reports whether a monitor target host must be rejected. It
// blocks loopback, link-local, multicast and unspecified addresses, and the
// "localhost" hostname unless server.allow_localhost is enabled. DNS lookups
// are bounded by a timeout so user-controlled hosts cannot stall a handler.
func (a *App) resolvesBlocked(host string) bool {
	if strings.EqualFold(host, "localhost") {
		return !a.Cfg.Server.AllowLocalhost
	}
	if ip := net.ParseIP(strings.Trim(host, "[]")); ip != nil {
		return ip.IsLoopback() || ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() || ip.IsMulticast() || ip.IsUnspecified()
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	addrs, err := net.DefaultResolver.LookupHost(ctx, host)
	if err != nil {
		return false
	}
	for _, addr := range addrs {
		if ip := net.ParseIP(addr); ip != nil && (ip.IsLoopback() || ip.IsLinkLocalUnicast() || ip.IsMulticast() || ip.IsUnspecified()) {
			return true
		}
	}
	return false
}

var _ = time.Now
