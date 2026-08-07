package api

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/auth"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/config"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/monitor"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/notify"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"
)

func newTestApp(t *testing.T) (*App, string, string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "sites.db")
	db, abs, err := storage.Open(path)
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	store := storage.NewStore(db, abs)
	t.Cleanup(func() { _ = store.DB.Close() })

	cfg := config.Default()
	hash, _ := auth.HashPassword("AdminPass123456")
	uid, _ := store.CreateUser("admin", hash, "admin")
	_ = store.UpdateUser(uid, map[string]any{"must_change_password": 1})
	_ = store.SaveNotifyConfig(`{}`)

	ws := NewWSManager()
	notifySvc := notify.New(store)
	worker := monitor.New(cfg, store, ws, notifySvc)
	app := &App{
		Cfg: cfg, Store: store, Worker: worker, Notify: notifySvc, WS: ws,
		Set: NewTemplateSet(), Start: time.Now(), Version: "test",
	}
	srv := httptest.NewServer(app.Handler())
	t.Cleanup(srv.Close)
	return app, srv.URL, "AdminPass123456"
}

// noRedirectClient never follows redirects.
var noRedirectClient = &http.Client{
	CheckRedirect: func(req *http.Request, via []*http.Request) error { return http.ErrUseLastResponse },
}

func postForm(base, path string, form map[string]string, jar map[string]string) *http.Response {
	vals := url.Values{}
	for k, v := range form {
		vals.Set(k, v)
	}
	req, _ := http.NewRequest(http.MethodPost, base+path, strings.NewReader(vals.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if c, ok := jar["session_id"]; ok {
		req.AddCookie(&http.Cookie{Name: "session_id", Value: c})
	}
	resp, err := noRedirectClient.Do(req)
	if err != nil {
		return &http.Response{StatusCode: 0, Header: http.Header{}}
	}
	for _, c := range resp.Cookies() {
		jar[c.Name] = c.Value
	}
	return resp
}

func getPage(base, path string, jar map[string]string) string {
	req, _ := http.NewRequest(http.MethodGet, base+path, nil)
	if c, ok := jar["session_id"]; ok {
		req.AddCookie(&http.Cookie{Name: "session_id", Value: c})
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	return string(b)
}

// login changes the initial (must-change) password and returns a logged-in jar.
func login(base string, oldPW, newPW string, jar map[string]string) {
	resp := postForm(base, "/login", map[string]string{"username": "admin", "password": oldPW}, jar)
	if resp.Header.Get("Location") != "/change-password" {
		return
	}
	html := getPage(base, "/change-password", jar)
	m := regexp.MustCompile(`name="csrf_token" value="([^"]+)"`).FindStringSubmatch(html)
	if len(m) < 2 {
		return
	}
	postForm(base, "/change-password", map[string]string{
		"current_password": oldPW, "new_password": newPW,
		"confirm_password": newPW, "csrf_token": m[1],
	}, jar)
}

func authedGet(base, path string, jar map[string]string) (*http.Response, []byte) {
	req, _ := http.NewRequest(http.MethodGet, base+path, nil)
	if c, ok := jar["session_id"]; ok {
		req.AddCookie(&http.Cookie{Name: "session_id", Value: c})
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return resp, nil
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	return resp, b
}

func TestHealthPagesAndStatic(t *testing.T) {
	_, base, _ := newTestApp(t)
	resp, _ := http.Get(base + "/health")
	if resp.StatusCode != 200 {
		t.Fatalf("health = %d", resp.StatusCode)
	}
	resp, _ = http.Get(base + "/login")
	if resp.StatusCode != 200 {
		t.Fatalf("login page = %d", resp.StatusCode)
	}
	resp, _ = http.Get(base + "/static/app.css")
	if resp.StatusCode != 200 {
		t.Fatalf("static css = %d", resp.StatusCode)
	}
	if ct := resp.Header.Get("Content-Type"); !strings.HasPrefix(ct, "text/css") {
		t.Fatalf("static css content-type = %q", ct)
	}
	resp, _ = http.Get(base + "/status")
	if resp.StatusCode != 200 {
		t.Fatalf("status page = %d", resp.StatusCode)
	}
	// unauthenticated dashboard -> redirect to login
	req, _ := http.NewRequest(http.MethodGet, base+"/", nil)
	resp, _ = noRedirectClient.Do(req)
	if resp.StatusCode != 302 || resp.Header.Get("Location") != "/login" {
		t.Fatalf("dashboard redirect = %d -> %s", resp.StatusCode, resp.Header.Get("Location"))
	}
}

func TestLoginChangePasswordAndDashboard(t *testing.T) {
	_, base, pw := newTestApp(t)
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)

	resp := postForm(base, "/login", map[string]string{"username": "admin", "password": "NewStrongPass123"}, jar)
	if resp.Header.Get("Location") != "/" {
		t.Fatalf("login after change redirect = %s", resp.Header.Get("Location"))
	}
	body := getPage(base, "/", jar)
	if !strings.Contains(body, "Uptime Monitor") {
		t.Fatalf("dashboard content missing")
	}
	if resp.StatusCode != 302 {
		t.Fatalf("login status = %d", resp.StatusCode)
	}
}

// TestDashboardScriptNotHtmlEscaped guards against the production bug where
// pongo2 autoescape turned the tojson output into HTML entities
// ({&quot;...&quot;}), producing a JS SyntaxError that killed the whole
// dashboard script block (switchTab / sitesData not defined).
func TestDashboardScriptNotHtmlEscaped(t *testing.T) {
	app, base, pw := newTestApp(t)
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)
	postForm(base, "/login", map[string]string{"username": "admin", "password": "NewStrongPass123"}, jar)

	// Save a notify config whose JSON contains characters pongo2 would escape.
	_ = app.Store.SaveNotifyConfig(`{"telegram":{"enabled":true,"channels":[{"id":"c1","name":"A & B","token":"x&y"}]},"webhook":{"enabled":true,"channels":[{"id":"w1","name":"Hook","url":"https://example.com/?a=1&b=2"}]}}`)

	body := getPage(base, "/", jar)
	if !strings.Contains(body, "Uptime Monitor") {
		t.Fatalf("dashboard content missing")
	}

	m := regexp.MustCompile(`var notifyConfig = (.*?);`).FindStringSubmatch(body)
	if len(m) < 2 {
		t.Fatalf("var notifyConfig not found in dashboard")
	}
	jsonLine := m[1]
	for _, bad := range []string{"&quot;", "&amp;", "&#34;", "&lt;", "&gt;", "&#39;"} {
		if strings.Contains(jsonLine, bad) {
			t.Fatalf("notifyConfig JSON contains HTML-escaped %q (broken JS): %s", bad, jsonLine)
		}
	}
	if !json.Valid([]byte(jsonLine)) {
		t.Fatalf("notifyConfig is not valid JSON: %s", jsonLine)
	}
	// the script tag must not be terminated early by a raw </ in the JSON
	if strings.Contains(jsonLine, "</script") {
		t.Fatalf("notifyConfig contains raw </script: %s", jsonLine)
	}
}

func TestPublicStatusRendersSiteFields(t *testing.T) {
	_, base, pw := newTestApp(t)
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)
	postForm(base, "/login", map[string]string{"username": "admin", "password": "NewStrongPass123"}, jar)

	// create a site via API
	payload := `{"name":"ExampleSite","url":"https://example.com","monitor_type":"http","check_interval":60}`
	req, _ := http.NewRequest(http.MethodPost, base+"/api/sites", strings.NewReader(payload))
	req.AddCookie(&http.Cookie{Name: "session_id", Value: jar["session_id"]})
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Origin", base)
	resp, err := http.DefaultClient.Do(req)
	if err != nil || resp.StatusCode != 200 {
		t.Fatalf("create site = %v (%v)", resp, err)
	}
	resp.Body.Close()

	body := getPage(base, "/status", jar)
	for _, want := range []string{"ExampleSite", "https://example.com", "Uptime"} {
		if !strings.Contains(body, want) {
			t.Fatalf("public status page missing %q", want)
		}
	}
	if !strings.Contains(body, `status-dot`) {
		t.Fatalf("public status page missing site cards")
	}
}

func TestEmptyListsAreArrays(t *testing.T) {
	_, base, pw := newTestApp(t)
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)
	postForm(base, "/login", map[string]string{"username": "admin", "password": "NewStrongPass123"}, jar)

	for _, path := range []string{
		"/api/sites", "/api/ssl-certificates", "/api/users",
		"/api/audit-log", "/api/notification-history", "/api/backups", "/api/tags",
		"/api/maintenance-windows",
	} {
		resp, b := authedGet(base, path, jar)
		if resp == nil || resp.StatusCode != 200 {
			t.Errorf("%s = %v", path, resp)
			continue
		}
		trimmed := strings.TrimSpace(string(b))
		if strings.HasPrefix(trimmed, "null") {
			t.Errorf("%s returned null (want [])", path)
		}
	}
}

func TestSiteLifecycleWithCSRF(t *testing.T) {
	_, base, pw := newTestApp(t)
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)
	postForm(base, "/login", map[string]string{"username": "admin", "password": "NewStrongPass123"}, jar)

	// create site with Origin header (CSRF satisfied)
	payload := `{"name":"Example","url":"https://example.com","monitor_type":"http","check_interval":60}`
	req, _ := http.NewRequest(http.MethodPost, base+"/api/sites", strings.NewReader(payload))
	req.AddCookie(&http.Cookie{Name: "session_id", Value: jar["session_id"]})
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Origin", base)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	var res map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&res)
	resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Fatalf("create = %d: %v", resp.StatusCode, res)
	}

	// list: notify_methods/tags must be [] not null
	_, b := authedGet(base, "/api/sites", jar)
	if strings.Contains(string(b), `"notify_methods":null`) || strings.Contains(string(b), `"tags":null`) {
		t.Fatalf("sites has null arrays: %s", string(b))
	}
	if !strings.Contains(string(b), `"notify_methods":[]`) {
		t.Fatalf("sites notify_methods not []: %s", string(b))
	}
}

func TestCSRFRejectsMissingOrigin(t *testing.T) {
	_, base, pw := newTestApp(t)
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)
	postForm(base, "/login", map[string]string{"username": "admin", "password": "NewStrongPass123"}, jar)

	payload := `{"name":"X","url":"https://example.org","monitor_type":"http","check_interval":60}`
	req, _ := http.NewRequest(http.MethodPost, base+"/api/sites", strings.NewReader(payload))
	req.AddCookie(&http.Cookie{Name: "session_id", Value: jar["session_id"]})
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("req: %v", err)
	}
	if resp.StatusCode != 403 {
		t.Fatalf("missing origin = %d, want 403", resp.StatusCode)
	}
}

func TestErrorUsesDetailField(t *testing.T) {
	_, base, _ := newTestApp(t)
	resp, err := http.Get(base + "/api/sites")
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 401 {
		t.Fatalf("unauth sites = %d", resp.StatusCode)
	}
	b, _ := io.ReadAll(resp.Body)
	if !strings.Contains(string(b), `"detail"`) {
		t.Fatalf("error body missing detail: %s", string(b))
	}
}

func TestForcedChangeNoCurrentPassword(t *testing.T) {
	_, base, pw := newTestApp(t)
	jar := map[string]string{}
	resp := postForm(base, "/login", map[string]string{"username": "admin", "password": pw}, jar)
	if resp.Header.Get("Location") != "/change-password" {
		t.Fatalf("login should force change, got %s", resp.Header.Get("Location"))
	}
	html := getPage(base, "/change-password", jar)
	m := regexp.MustCompile(`name="csrf_token" value="([^"]+)"`).FindStringSubmatch(html)
	if len(m) < 2 {
		t.Fatalf("no csrf token in change-password page")
	}
	// forced change: current_password is optional / ignored
	resp = postForm(base, "/change-password", map[string]string{
		"current_password": "", "new_password": "BrandNewPass456",
		"confirm_password": "BrandNewPass456", "csrf_token": m[1],
	}, jar)
	if resp.Header.Get("Location") != "/" {
		t.Fatalf("forced change failed, got %s", resp.Header.Get("Location"))
	}
}

func TestStaleSessionNoRedirectLoop(t *testing.T) {
	app, base, pw := newTestApp(t)
	jar := map[string]string{}
	postForm(base, "/login", map[string]string{"username": "admin", "password": pw}, jar)
	sid := jar["session_id"]
	if sid == "" {
		t.Fatalf("no session after login")
	}
	// simulate reset-admin: delete all sessions for the admin user
	u, _ := app.Store.GetUserByUsername("admin")
	if u != nil {
		_ = app.Store.DeleteUserSessions(u.ID)
	}

	// / with a stale cookie must redirect to /login (no loop)
	req, _ := http.NewRequest(http.MethodGet, base+"/", nil)
	req.AddCookie(&http.Cookie{Name: "session_id", Value: sid})
	resp, err := noRedirectClient.Do(req)
	if err != nil {
		t.Fatalf("GET /: %v", err)
	}
	if resp.StatusCode != 302 || resp.Header.Get("Location") != "/login" {
		t.Fatalf("GET / with stale cookie = %d -> %s", resp.StatusCode, resp.Header.Get("Location"))
	}

	// /login with a stale cookie must render the login page (200), not redirect
	req, _ = http.NewRequest(http.MethodGet, base+"/login", nil)
	req.AddCookie(&http.Cookie{Name: "session_id", Value: sid})
	resp, err = http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("GET /login: %v", err)
	}
	if resp.StatusCode != 200 {
		t.Fatalf("GET /login with stale cookie = %d, want 200 (no redirect loop)", resp.StatusCode)
	}
}

func TestNonAdminForbidden(t *testing.T) {
	_, base, pw := newTestApp(t)
	// create a viewer user via API
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)
	postForm(base, "/login", map[string]string{"username": "admin", "password": "NewStrongPass123"}, jar)

	payload := `{"username":"viewer","password":"ViewerPass123456","role":"viewer"}`
	req, _ := http.NewRequest(http.MethodPost, base+"/api/users", strings.NewReader(payload))
	req.AddCookie(&http.Cookie{Name: "session_id", Value: jar["session_id"]})
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Origin", base)
	resp, _ := http.DefaultClient.Do(req)
	if resp.StatusCode != 200 {
		t.Fatalf("create viewer = %d", resp.StatusCode)
	}

	// viewer login
	vjar := map[string]string{}
	postForm(base, "/login", map[string]string{"username": "viewer", "password": "ViewerPass123456"}, vjar)
	// viewer can list sites
	resp, _ = authedGet(base, "/api/sites", vjar)
	if resp.StatusCode != 200 {
		t.Fatalf("viewer list = %d", resp.StatusCode)
	}
	// viewer cannot create users
	req, _ = http.NewRequest(http.MethodPost, base+"/api/users", strings.NewReader(payload))
	req.AddCookie(&http.Cookie{Name: "session_id", Value: vjar["session_id"]})
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Origin", base)
	resp, _ = http.DefaultClient.Do(req)
	if resp.StatusCode != 403 {
		t.Fatalf("viewer create user = %d, want 403", resp.StatusCode)
	}
}

func TestAlertPolicySavesRetryDelays(t *testing.T) {
	app, base, pw := newTestApp(t)
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)
	postForm(base, "/login", map[string]string{"username": "admin", "password": "NewStrongPass123"}, jar)

	payload := `{"grace_period_seconds":30,"max_retries":2,"retry_delays":[5,30],"ssl_notification_days":[30,14,7,3]}`
	req, _ := http.NewRequest(http.MethodPost, base+"/api/alert-policy", strings.NewReader(payload))
	req.AddCookie(&http.Cookie{Name: "session_id", Value: jar["session_id"]})
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Origin", base)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("save policy: %v", err)
	}
	resp.Body.Close()

	// verify via GET
	resp, b := authedGet(base, "/api/alert-policy", jar)
	if resp.StatusCode != 200 {
		t.Fatalf("get policy = %d", resp.StatusCode)
	}
	var pol map[string]any
	if err := json.Unmarshal(b, &pol); err != nil {
		t.Fatalf("policy not json: %v", err)
	}
	delays, _ := pol["retry_delays"].([]any)
	if len(delays) != 2 || int(delays[0].(float64)) != 5 || int(delays[1].(float64)) != 30 {
		t.Fatalf("retry_delays = %v, want [5 30]", pol["retry_delays"])
	}
	if int(pol["max_retries"].(float64)) != 2 {
		t.Fatalf("max_retries = %v, want 2", pol["max_retries"])
	}

	// confirm the in-memory config object was mutated (used by the worker)
	if app.Cfg.AlertPolicy.MaxRetries != 2 || len(app.Cfg.AlertPolicy.RetryDelays) != 2 {
		t.Fatalf("cfg not updated: %+v", app.Cfg.AlertPolicy)
	}
}

var _ = bytes.NewBuffer
