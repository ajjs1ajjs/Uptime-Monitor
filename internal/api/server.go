package api

import (
	"embed"
	"encoding/json"
	"io"
	"io/fs"
	"net/http"
	"path"
	"strings"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/config"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/ha"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/monitor"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/notify"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"

	"github.com/flosch/pongo2/v6"
)

//go:embed all:web
var webFS embed.FS

type App struct {
	Cfg         *config.Config
	Store       *storage.Store
	Worker      *monitor.Worker
	Notify      *notify.Service
	Set         *pongo2.TemplateSet
	WS          *WSManager
	Start       time.Time
	Version     string
	Leader      *ha.Elector
	rateLimiter *rateLimitStore
}

// requireLeader refuses mutations on standby nodes (HA active-passive).
// Reads stay available everywhere; writers get 409 + X-Leader hint.
// A nil elector (tests, old call paths) means single-node mode: leader.
func (a *App) requireLeader(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if a.Leader != nil && !a.Leader.IsLeader() {
			if owner := a.Leader.Owner(); owner != "" {
				w.Header().Set("X-Leader", owner)
			}
			writeErr(w, http.StatusConflict, "Standby node — writes go to the leader")
			return
		}
		next(w, r)
	}
}

func (a *App) Handler() http.Handler {
	if a.rateLimiter == nil {
		a.rateLimiter = newRateLimitStore()
	}
	mux := http.NewServeMux()

	// health + metrics (public, rate limited)
	mux.HandleFunc("GET /health", a.withRecovery(a.withRateLimit("health", 30, 60, a.handleHealth)))
	mux.HandleFunc("GET /health/live", a.withRecovery(a.withRateLimit("health", 30, 60, a.handleLiveness)))
	mux.HandleFunc("GET /health/ready", a.withRecovery(a.withRateLimit("health", 30, 60, a.handleReadiness)))
	mux.HandleFunc("GET /metrics", a.withRecovery(a.withRateLimit("metrics", 30, 60, a.handlePrometheus)))

	// auth
	mux.HandleFunc("GET /login", a.withRecovery(a.handleLoginPage))
	// Login uses persistent (DB-backed) rate limiting for failed attempts only.
	// Successful logins reset the counter so legitimate users are never locked out.
	mux.HandleFunc("POST /login", a.withRecovery(a.withRateLimit("login_fail", 5, 900, a.handleLoginPost)))
	mux.HandleFunc("GET /logout", a.withRecovery(a.handleLogout))
	mux.Handle("POST /logout", a.withRecovery(a.withAuth(a.withCSRF(a.handleLogout))))
	mux.HandleFunc("GET /change-password", a.withRecovery(a.handleChangePasswordPage))
	mux.HandleFunc("POST /change-password", a.withRecovery(a.withRateLimit("change_password", 3, 900, a.handleChangePasswordPost)))
	mux.HandleFunc("GET /forgot-password", a.withRecovery(a.handleForgotPage))
	mux.HandleFunc("POST /forgot-password", a.withRecovery(a.withRateLimit("forgot_password", 3, 1800, a.handleForgotPost)))

	// pages
	mux.HandleFunc("GET /", a.withRecovery(a.handleDashboard))
	mux.HandleFunc("GET /users", a.withRecovery(a.handleUsersPage))
	mux.HandleFunc("GET /status", a.withRecovery(a.withRateLimit("public_status", 30, 60, a.handlePublicStatus)))
	mux.HandleFunc("GET /public-status", a.withRecovery(a.withRateLimit("public_status", 30, 60, a.handlePublicStatus)))
	mux.HandleFunc("GET /api/htmx/hero-stats", a.withRecovery(a.withAuth(a.handleHtmxHeroStats)))
	mux.HandleFunc("GET /api/htmx/monitors", a.withRecovery(a.withAuth(a.handleHtmxMonitors)))
	// /ws is reachable unauthenticated (it authenticates itself), so it gets
	// the same recovery + rate limit treatment as the other public endpoints.
	mux.HandleFunc("GET /ws", a.withRecovery(a.withRateLimit("ws", 60, 60, a.handleWS)))

	// --- JSON API ---
	//
	// Order matters: withAuth must run before withCSRF, because withCSRF
	// reads the principal to exempt API-key requests (not a browser CSRF
	// vector). With the wrappers the other way round the principal was always
	// nil at that point and the exemption was dead code.
	authed := func(h http.HandlerFunc) http.HandlerFunc {
		return a.withRecovery(a.withAuth(a.withCSRF(h)))
	}
	admin := func(h http.HandlerFunc) http.HandlerFunc {
		return a.withRecovery(a.withAuth(a.withCSRF(a.withAdmin(h))))
	}
	// adminWrite additionally requires HA leadership (standbys are read-only).
	adminWrite := func(h http.HandlerFunc) http.HandlerFunc {
		return a.withRecovery(a.withAuth(a.withCSRF(a.withAdmin(a.requireLeader(h)))))
	}

	mux.Handle("GET /api/sites", authed(a.handleListSites))
	mux.Handle("POST /api/sites", adminWrite(a.handleCreateSite))
	mux.Handle("PUT /api/sites/{site_id}", adminWrite(a.handleUpdateSite))
	mux.Handle("DELETE /api/sites/{site_id}", adminWrite(a.handleDeleteSite))
	mux.Handle("POST /api/sites/{site_id}/check", adminWrite(a.handleManualCheck))
	mux.Handle("GET /api/sites/history-all", authed(a.handleHistoryAll))
	mux.Handle("GET /api/sites/{site_id}/history", authed(a.handleSiteHistory))

	mux.HandleFunc("GET /api/server-time", a.withRecovery(a.handleServerTime))

	mux.Handle("GET /api/ssl-certificates", authed(a.handleListSSLCerts))
	mux.Handle("POST /api/ssl-certificates/check", adminWrite(a.handleSSLCheckAll))
	mux.Handle("GET /api/stats/response-time", authed(a.handleResponseTime))
	mux.Handle("GET /api/incidents", authed(a.handleIncidents))

	mux.Handle("POST /api/notify-settings", adminWrite(a.handleSaveNotify))
	mux.Handle("GET /api/app-settings", authed(a.handleGetAppSettings))
	mux.Handle("POST /api/app-settings", adminWrite(a.handleSaveAppSettings))
	mux.Handle("GET /api/alert-policy", authed(a.handleGetAlertPolicy))
	mux.Handle("POST /api/alert-policy", adminWrite(a.handleSaveAlertPolicy))

	mux.Handle("GET /api/user", authed(a.handleGetUser))
	mux.Handle("GET /api/users", admin(a.handleListUsersAPI))
	mux.Handle("POST /api/users", adminWrite(a.handleCreateUserAPI))
	mux.Handle("PUT /api/users/{username}", adminWrite(a.handleUpdateUserAPI))
	mux.Handle("DELETE /api/users/{username}", adminWrite(a.handleDeleteUserAPI))

	mux.Handle("GET /api/maintenance-windows", authed(a.handleListMaintenance))
	mux.Handle("POST /api/maintenance-windows", adminWrite(a.handleCreateMaintenance))
	mux.Handle("DELETE /api/maintenance-windows/{window_id}", adminWrite(a.handleDeleteMaintenance))
	mux.Handle("PUT /api/maintenance-windows/{window_id}/toggle", adminWrite(a.handleToggleMaintenance))

	mux.Handle("GET /api/reports/sla", authed(a.handleSLAResponse))
	mux.Handle("GET /api/reports/sla/export", authed(a.handleSLAExport))
	mux.Handle("GET /api/reports/sla/pdf", authed(a.handleSLAPDF))

	mux.Handle("POST /api/api-keys", adminWrite(a.handleCreateAPIKey))
	mux.Handle("GET /api/api-keys", admin(a.handleListAPIKeys))
	mux.Handle("DELETE /api/api-keys/{key_id}", adminWrite(a.handleRevokeAPIKey))

	mux.Handle("GET /api/audit-log", admin(a.handleAuditLog))
	mux.Handle("GET /api/notification-history", admin(a.handleNotificationHistory))
	mux.Handle("POST /api/test-notify", adminWrite(a.handleTestNotify))
	mux.Handle("POST /api/backup", adminWrite(a.handleBackupCreate))
	mux.Handle("GET /api/backups", admin(a.handleBackupList))
	mux.Handle("POST /api/backup/restore/{backup_id}", adminWrite(a.handleBackupRestore))
	mux.Handle("GET /api/tags", authed(a.handleTags))

	// static assets (embedded). The FS is rooted at internal/api/web, so the
	// request /static/... maps directly to static/... — no prefix stripping
	// (a lesson from the Monitoring port).
	web, _ := fs.Sub(webFS, "web")
	mux.Handle("GET /static/", staticHandler(web))

	return a.withSecurity(a.withLogging(mux))
}

// isLeader/nodeID keep handlers nil-safe (tests build App without an
// elector: single-node mode is always leader).
func (a *App) isLeader() bool {
	if a.Leader == nil {
		return true
	}
	return a.Leader.IsLeader()
}

func (a *App) nodeID() string {
	if a.Leader == nil {
		return "single"
	}
	return a.Leader.NodeID()
}

// staticHandler serves the embedded static FS, but forces no-cache on the
// service worker and manifest so a stale cached SW can't keep serving an old
// broken page.
func staticHandler(fsys fs.FS) http.Handler {
	fileServer := http.FileServer(http.FS(fsys))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "sw.js") || strings.HasSuffix(r.URL.Path, "manifest.json") {
			w.Header().Set("Cache-Control", "no-store")
		}
		fileServer.ServeHTTP(w, r)
	})
}

// --- template rendering (pongo2 over embedded templates) ---

type embedLoader struct {
	fs fs.FS
}

func (l *embedLoader) Abs(base, name string) string {
	if strings.HasPrefix(name, "/") {
		return strings.TrimPrefix(name, "/")
	}
	if base != "" {
		return path.Join(path.Dir(base), name)
	}
	return name
}

func (l *embedLoader) Get(name string) (io.Reader, error) {
	f, err := l.fs.Open(name)
	if err != nil {
		return nil, err
	}
	return f, nil
}

func NewTemplateSet() *pongo2.TemplateSet {
	web, _ := fs.Sub(webFS, "web")
	tplFS, _ := fs.Sub(web, "templates")
	set := pongo2.NewSet("uptime", &embedLoader{fs: tplFS})
	return set
}

func init() {
	// Register the Jinja2 tojson filter used by the templates.
	_ = pongo2.RegisterFilter("tojson", func(in *pongo2.Value, param *pongo2.Value) (*pongo2.Value, *pongo2.Error) {
		b, err := json.Marshal(in.Interface())
		if err != nil {
			return pongo2.AsSafeValue("null"), nil
		}
		// The output is embedded into inline <script> blocks, so it must be
		// safe (pongo2 would otherwise HTML-escape it and produce invalid JS)
		// and must not terminate the script tag prematurely.
		s := strings.ReplaceAll(string(b), "</", "<\\/")
		s = strings.ReplaceAll(s, "\u2028", `\u2028`)
		s = strings.ReplaceAll(s, "\u2029", `\u2029`)
		return pongo2.AsSafeValue(s), nil
	})
}

func (a *App) render(name string, ctx map[string]any) (string, error) {
	tpl, err := a.Set.FromFile(name)
	if err != nil {
		return "", err
	}
	return tpl.Execute(ctx)
}

func (a *App) renderPage(w http.ResponseWriter, name string, ctx map[string]any, status int) {
	html, err := a.render(name, ctx)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "Template error: "+err.Error())
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(status)
	_, _ = w.Write([]byte(html))
}
