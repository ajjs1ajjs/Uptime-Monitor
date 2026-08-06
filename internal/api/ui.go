package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/auth"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"
)

const sessionCookie = "session_id"

func (a *App) setSessionCookie(w http.ResponseWriter, sessionID string) {
	http.SetCookie(w, &http.Cookie{
		Name: sessionCookie, Value: sessionID, Path: "/",
		HttpOnly: true, SameSite: http.SameSiteLaxMode,
		MaxAge: 7 * 24 * 3600,
	})
}

func (a *App) clearSessionCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{Name: sessionCookie, Value: "", Path: "/", MaxAge: -1, HttpOnly: true})
}

// --- login ---

func (a *App) handleLoginPage(w http.ResponseWriter, r *http.Request) {
	// Redirect to "/" only when the session is actually VALID. Checking only
	// for the presence of the cookie caused ERR_TOO_MANY_REDIRECTS with a stale
	// cookie (e.g. after reset-admin deleted the session): "/" -> /login ->
	// (cookie exists) -> "/" -> ...
	if u := a.authenticate(r); u != nil {
		http.Redirect(w, r, "/", http.StatusFound)
		return
	}
	a.renderPage(w, "login.html", map[string]any{"error_message": r.URL.Query().Get("error")}, http.StatusOK)
}

func (a *App) handleLoginPost(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Redirect(w, r, "/login?error=bad_request", http.StatusFound)
		return
	}
	username := strings.TrimSpace(r.FormValue("username"))
	password := r.FormValue("password")
	u, err := a.Store.GetUserByUsername(username)
	if err != nil || u == nil || !auth.VerifyPassword(u.PasswordHash, password) {
		http.Redirect(w, r, "/login?error=invalid_credentials", http.StatusFound)
		return
	}
	sessionID := auth.SessionID()
	expires := time.Now().Add(7 * 24 * time.Hour)
	if err := a.Store.CreateSession(u.ID, sessionID, expires); err != nil {
		http.Redirect(w, r, "/login?error=session_error", http.StatusFound)
		return
	}
	_ = a.Store.UpdateUser(u.ID, map[string]any{"last_login": storage.Now()})
	a.setSessionCookie(w, sessionID)
	if u.MustChangePassword == 1 {
		http.Redirect(w, r, "/change-password", http.StatusFound)
		return
	}
	http.Redirect(w, r, "/", http.StatusFound)
}

func (a *App) handleLogout(w http.ResponseWriter, r *http.Request) {
	if c, err := r.Cookie(sessionCookie); err == nil {
		_ = a.Store.DeleteSession(c.Value)
	}
	a.clearSessionCookie(w)
	http.Redirect(w, r, "/login", http.StatusFound)
}

// --- change password ---

func (a *App) newCSRFToken(sessionID string) string {
	token := auth.RandomToken(16)
	_ = a.Store.CreateCSRFToken(sessionID, token)
	return token
}

func (a *App) currentSessionID(r *http.Request) string {
	if c, err := r.Cookie(sessionCookie); err == nil {
		return c.Value
	}
	return ""
}

func (a *App) handleChangePasswordPage(w http.ResponseWriter, r *http.Request) {
	sid := a.currentSessionID(r)
	if sid == "" {
		http.Redirect(w, r, "/login", http.StatusFound)
		return
	}
	u, _ := a.Store.GetSession(sid)
	forced := u != nil && u.MustChangePassword == 1
	a.renderPage(w, "change_password.html", map[string]any{
		"error_message": r.URL.Query().Get("error"),
		"csrf_token":    a.newCSRFToken(sid),
		"is_forced":     forced,
	}, http.StatusOK)
}

func (a *App) handleChangePasswordPost(w http.ResponseWriter, r *http.Request) {
	sid := a.currentSessionID(r)
	if sid == "" {
		http.Redirect(w, r, "/login", http.StatusFound)
		return
	}
	if err := r.ParseForm(); err != nil || !a.Store.ConsumeCSRFToken(sid, r.FormValue("csrf_token")) {
		http.Redirect(w, r, "/change-password?error=csrf", http.StatusFound)
		return
	}
	u, err := a.Store.GetSession(sid)
	if err != nil || u == nil {
		http.Redirect(w, r, "/login", http.StatusFound)
		return
	}
	current := r.FormValue("current_password")
	np := r.FormValue("new_password")
	confirm := r.FormValue("confirm_password")
	if np != confirm {
		http.Redirect(w, r, "/change-password?error=Passwords do not match", http.StatusFound)
		return
	}
	if ok, msg := auth.CheckPasswordPolicy(np); !ok {
		http.Redirect(w, r, "/change-password?error="+url.QueryEscape(msg), http.StatusFound)
		return
	}
	// For a forced password change (must_change_password=1) the user has just
	// authenticated with the current password, so re-checking it here is
	// redundant and only causes "Invalid current password" confusion.
	if u.MustChangePassword != 1 && !auth.VerifyPassword(u.PasswordHash, current) {
		http.Redirect(w, r, "/change-password?error=Invalid current password", http.StatusFound)
		return
	}
	hash, err := auth.HashPassword(np)
	if err != nil {
		http.Redirect(w, r, "/change-password?error=error", http.StatusFound)
		return
	}
	_ = a.Store.UpdateUser(u.ID, map[string]any{"password_hash": hash, "must_change_password": 0})
	_ = a.Store.DeleteUserSessions(u.ID)
	// mint a fresh session for the actor
	newSid := auth.SessionID()
	_ = a.Store.CreateSession(u.ID, newSid, time.Now().Add(7*24*time.Hour))
	a.setSessionCookie(w, newSid)
	http.Redirect(w, r, "/", http.StatusFound)
}

// --- forgot password (admin-assisted) ---

func (a *App) handleForgotPage(w http.ResponseWriter, r *http.Request) {
	sid := a.currentSessionID(r)
	csrf := ""
	if sid != "" {
		csrf = a.newCSRFToken(sid)
	}
	a.renderPage(w, "forgot_password.html", map[string]any{
		"error_message":   r.URL.Query().Get("error"),
		"success_message": r.URL.Query().Get("success"),
		"csrf_token":      csrf,
	}, http.StatusOK)
}

func (a *App) handleForgotPost(w http.ResponseWriter, r *http.Request) {
	sid := a.currentSessionID(r)
	if sid == "" || !a.Store.ConsumeCSRFToken(sid, r.FormValue("csrf_token")) {
		http.Redirect(w, r, "/forgot-password?error=csrf", http.StatusFound)
		return
	}
	u, err := a.Store.GetSession(sid)
	if err != nil || u == nil {
		http.Redirect(w, r, "/forgot-password?error=auth", http.StatusFound)
		return
	}
	if u.Role != "admin" {
		http.Redirect(w, r, "/forgot-password?error=admin_only", http.StatusFound)
		return
	}
	if err := r.ParseForm(); err != nil {
		http.Redirect(w, r, "/forgot-password?error=bad_request", http.StatusFound)
		return
	}
	target := strings.TrimSpace(r.FormValue("username"))
	tu, err := a.Store.GetUserByUsername(target)
	if err != nil || tu == nil {
		http.Redirect(w, r, "/forgot-password?error=not_found", http.StatusFound)
		return
	}
	tempPW := auth.RandomToken(12)
	hash, _ := auth.HashPassword(tempPW)
	_ = a.Store.UpdateUser(tu.ID, map[string]any{"password_hash": hash, "must_change_password": 1})
	_ = a.Store.DeleteUserSessions(tu.ID)
	msg := "Тимчасовий пароль для " + target + ": " + tempPW + " (змініть при вході)"
	http.Redirect(w, r, "/forgot-password?success="+url.QueryEscape(msg), http.StatusFound)
}

// --- dashboard / users / public status ---

func (a *App) handleDashboard(w http.ResponseWriter, r *http.Request) {
	p := a.authenticate(r)
	if p == nil {
		http.Redirect(w, r, "/login", http.StatusFound)
		return
	}
	if p.MustChange {
		http.Redirect(w, r, "/change-password", http.StatusFound)
		return
	}
	sites, _ := a.Store.GetSites()
	var total, up, down int
	for _, s := range sites {
		total++
		switch s.Status {
		case "up":
			up++
		case "down":
			down++
		}
	}
	settings := a.Notify.LoadSettings()
	if !p.IsAdmin {
		settings = redactNotify(settings)
	}
	methods := buildNotifyMethods(settings)
	cards, err := a.render("partials/notification_cards.html", map[string]any{
		"notify_settings": settings,
		"methods":         methods,
	})
	if err != nil {
		cards = ""
	}
	cfgJSON, _ := json.Marshal(settings)
	a.renderPage(w, "dashboard.html", map[string]any{
		"total": total, "total_sites": total, "up_sites": up, "down_sites": down,
		"notification_cards": cards,
		"notify_config_json": strings.ReplaceAll(string(cfgJSON), "</", "<\\/"),
		"notify_settings":    settings,
	}, http.StatusOK)
}

// buildNotifyMethods prepares the channel cards data for the templates.
func buildNotifyMethods(settings map[string]any) []map[string]any {
	type meta struct{ key, icon, name, desc string }
	metas := []meta{
		{"telegram", "📱", "Telegram", "Миттєві сповіщення"},
		{"discord", "🎮", "Discord", "Геймерські спільноти"},
		{"teams", "🏢", "MS Teams", "Робочі групи"},
		{"email", "📧", "Email", "Електронна пошта"},
		{"webhook", "🔗", "Custom Webhooks", "Кастомні HTTP POST запити"},
	}
	out := make([]map[string]any, 0, len(metas))
	for _, mt := range metas {
		enabled := false
		channels := []map[string]any{}
		if sec, ok := settings[mt.key].(map[string]any); ok {
			if on, ok := sec["enabled"].(bool); ok {
				enabled = on
			}
			if chs, ok := sec["channels"].([]any); ok {
				for _, c := range chs {
					if cm, ok := c.(map[string]any); ok {
						id, _ := cm["id"].(string)
						name, _ := cm["name"].(string)
						if name == "" {
							name = "Channel"
						}
						channels = append(channels, map[string]any{"id": id, "name": name})
					}
				}
			}
		}
		out = append(out, map[string]any{
			"key": mt.key, "icon": mt.icon, "name": mt.name, "desc": mt.desc,
			"enabled": enabled, "channels": channels,
		})
	}
	return out
}

func redactNotify(s map[string]any) map[string]any {
	out := map[string]any{}
	for k, v := range s {
		out[k] = v
	}
	return out
}

func (a *App) handleUsersPage(w http.ResponseWriter, r *http.Request) {
	p := a.authenticate(r)
	if p == nil {
		http.Redirect(w, r, "/login", http.StatusFound)
		return
	}
	if !p.IsAdmin {
		http.Redirect(w, r, "/", http.StatusFound)
		return
	}
	a.renderPage(w, "users.html", map[string]any{}, http.StatusOK)
}

func (a *App) handlePublicStatus(w http.ResponseWriter, r *http.Request) {
	sites, _ := a.Store.GetSites()
	as := a.Store.GetAppSettings()

	type siteView struct {
		Name               string  `json:"name"`
		URL                string  `json:"url"`
		MonitorType        string  `json:"monitor_type"`
		Status             string  `json:"status"`
		ResponseTime       any     `json:"response_time"`
		UptimePct          float64 `json:"uptime_pct"`
		LatestResponseTime any     `json:"latest_response_time"`
		StatusClass        string  `json:"status_class"`
		StatusText         string  `json:"status_text"`
		DotColor           string  `json:"dot_color"`
	}
	views := make([]siteView, 0, len(sites))
	upCount, downCount := 0, 0
	uptimeSum := 0.0
	for _, s := range sites {
		if !s.IsActive {
			continue
		}
		sv := siteView{
			Name: s.Name, URL: s.URL, MonitorType: s.MonitorType,
			Status: s.Status, UptimePct: s.Uptime,
		}
		if s.ResponseTime != nil {
			sv.ResponseTime = round1(*s.ResponseTime)
			sv.LatestResponseTime = round1(*s.ResponseTime)
		}
		switch s.Status {
		case "up":
			upCount++
			sv.StatusClass, sv.StatusText, sv.DotColor = "up", "UP", "#00ff88"
		case "maintenance":
			sv.StatusClass, sv.StatusText, sv.DotColor = "maintenance", "MAINTENANCE", "#a855f7"
		case "paused":
			sv.StatusClass, sv.StatusText, sv.DotColor = "paused", "PAUSED", "#f59e0b"
		case "slow":
			sv.StatusClass, sv.StatusText, sv.DotColor = "paused", "SLOW", "#f59e0b"
		case "unknown":
			sv.StatusClass, sv.StatusText, sv.DotColor = "unknown", "UNKNOWN", "#94a3b8"
		default:
			downCount++
			sv.StatusClass, sv.StatusText, sv.DotColor = "down", "DOWN", "#ff4757"
		}
		uptimeSum += s.Uptime
		views = append(views, sv)
	}
	// sort: down -> slow -> unknown -> paused -> up
	sort.SliceStable(views, func(i, j int) bool {
		return statusRank(views[i].Status) < statusRank(views[j].Status)
	})
	thirtyDay := 100.0
	if len(views) > 0 {
		thirtyDay = float64(int(uptimeSum/float64(len(views))*100+0.5)) / 100
	}
	overallClass := "up"
	overallText := "All systems operational"
	if downCount > 0 {
		overallClass = "down"
		overallText = "Some issues detected"
	}

	// recent incidents (last 10)
	incidents := a.recentIncidents(5, 10)

	a.renderPage(w, "public_status.html", map[string]any{
		"overall_status_class": overallClass,
		"overall_status_text":  overallText,
		"total":                len(views),
		"up_count":             upCount,
		"down_count":           downCount,
		"sites":                views,
		"timestamp":            time.Now().UTC().Format("2006-01-02 15:04:05"),
		"site_title":           as.SiteTitle,
		"logo_url":             as.LogoURL,
		"footer_text":          as.FooterText,
		"primary_color":        as.PrimaryColor,
		"brand_accent_color":   as.BrandAccentColor,
		"display_address":      as.DisplayAddress,
		"thirty_day_uptime":    thirtyDay,
		"incidents":            incidents,
	}, http.StatusOK)
}

func statusRank(s string) int {
	switch s {
	case "down":
		return 0
	case "slow":
		return 1
	case "unknown":
		return 2
	case "paused":
		return 3
	}
	return 4
}

func (a *App) recentIncidents(perSite, totalLimit int) []map[string]any {
	rows, err := a.Store.DB.Query(`SELECT site_id, checked_at FROM status_history
	  WHERE status = 'down' AND checked_at >= datetime('now','-30 days')
	  ORDER BY checked_at DESC`)
	if err != nil {
		return []map[string]any{}
	}
	defer rows.Close()
	sites := map[int64]string{}
	if all, err := a.Store.GetSites(); err == nil {
		for _, s := range all {
			sites[s.ID] = s.Name
		}
	}
	seen := map[int64]int{}
	out := make([]map[string]any, 0, totalLimit)
	for rows.Next() {
		var sid int64
		var checked string
		if rows.Scan(&sid, &checked) != nil {
			continue
		}
		if seen[sid] >= perSite {
			continue
		}
		seen[sid]++
		out = append(out, map[string]any{
			"site_name": sites[sid],
			"time":      strings.Replace(strings.TrimPrefix(checked, "T"), "T", " ", 1),
		})
		if len(out) >= totalLimit {
			break
		}
	}
	return out
}

// --- htmx fragments ---

func (a *App) handleHtmxHeroStats(w http.ResponseWriter, r *http.Request) {
	if a.principal(r) == nil {
		_, _ = w.Write([]byte(""))
		return
	}
	sites, _ := a.Store.GetSites()
	var up, down, slow int
	for _, s := range sites {
		switch s.Status {
		case "up":
			up++
		case "down":
			down++
		case "slow":
			slow++
		}
	}
	card := func(label string, value int, color string) string {
		return fmt.Sprintf(`<div class="glass rounded-2xl p-6 text-center"><div class="text-4xl md:text-5xl font-bold %s mb-2">%d</div><div class="text-slate-400 text-xs md:text-sm uppercase tracking-wider">%s</div></div>`, color, value, label)
	}
	html := card("Monitors", len(sites), "text-accent") +
		card("Online", up, "text-emerald-400") +
		card("Offline", down, "text-red-400") +
		card("Incidents", down+slow, "text-amber-400")
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write([]byte(html))
}

func (a *App) handleHtmxMonitors(w http.ResponseWriter, r *http.Request) {
	if a.principal(r) == nil {
		_, _ = w.Write([]byte(""))
		return
	}
	sites, err := a.Store.GetSites()
	if err != nil {
		_, _ = w.Write([]byte(""))
		return
	}
	search := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("search")))
	tag := r.URL.Query().Get("tag")
	sortBy := r.URL.Query().Get("sort")

	out := make([]storage.Site, 0, len(sites))
	for _, s := range sites {
		if search != "" && !strings.Contains(strings.ToLower(s.Name), search) && !strings.Contains(strings.ToLower(s.URL), search) {
			continue
		}
		if tag != "" && !strings.Contains(s.Tags, tag) {
			continue
		}
		out = append(out, s)
	}
	switch sortBy {
	case "name":
		sort.SliceStable(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	case "uptime":
		sort.SliceStable(out, func(i, j int) bool { return out[i].Uptime > out[j].Uptime })
	default:
		sort.SliceStable(out, func(i, j int) bool { return statusRank(out[i].Status) < statusRank(out[j].Status) })
	}

	var sb strings.Builder
	for _, s := range out {
		html, err := a.render("partials/monitor_card.html", monitorCardCtx(s))
		if err == nil {
			sb.WriteString(html)
		}
	}
	if sb.Len() == 0 {
		sb.WriteString(`<div class="col-span-full text-center py-10 text-slate-500">No monitors found.</div>`)
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write([]byte(sb.String()))
}

func monitorCardCtx(s storage.Site) map[string]any {
	status := s.Status
	scolor, border, stext := "#ef4444", "border-red-500", "UP"
	switch status {
	case "up":
		scolor, border, stext = "#10b981", "border-emerald-500", "UP"
	case "paused":
		scolor, border, stext = "#f59e0b", "border-amber-500", "PAUSED"
	case "maintenance":
		scolor, border, stext = "#a855f7", "border-purple-500", "MAINTENANCE"
	case "slow":
		scolor, border, stext = "#f59e0b", "border-amber-500", "SLOW"
	case "unknown":
		scolor, border, stext = "#94a3b8", "border-slate-500", "UNKNOWN"
	default:
		scolor, border, stext = "#ef4444", "border-red-500", "DOWN"
	}
	uptime := s.Uptime
	rt := "—"
	if s.ResponseTime != nil {
		rt = fmt.Sprintf("%.0f", *s.ResponseTime)
	}
	sc := "—"
	if s.StatusCode != nil {
		sc = fmt.Sprintf("%d", *s.StatusCode)
	}
	nameJSON, _ := json.Marshal(s.Name)
	urlJSON, _ := json.Marshal(s.URL)
	methodsJSON, _ := json.Marshal(json.RawMessage(s.NotifyMethods))
	kw := ""
	if s.Keyword != nil {
		kw = *s.Keyword
	}
	tagsJSON, _ := json.Marshal(json.RawMessage(s.Tags))
	return map[string]any{
		"name": s.Name, "url": s.URL,
		"escaped_name": string(nameJSON), "escaped_url": string(urlJSON),
		"escaped_methods": url.QueryEscape(string(methodsJSON)),
		"escaped_keyword": url.QueryEscape(kw),
		"escaped_tags":    url.QueryEscape(string(tagsJSON)),
		"keyword":         kw, "tags": json.RawMessage(s.Tags),
		"scolor": scolor, "border": border, "stext": stext,
		"mtype": s.MonitorType, "uptime": uptime, "rt": rt, "sc": sc,
		"sid": s.ID, "check_interval": s.CheckInterval,
	}
}
