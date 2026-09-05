package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"strings"
	"testing"
)

// postJSON sends a JSON POST with a session cookie and a same-origin header so
// the CSRF middleware accepts it (mirrors a browser request).
func postJSON(base, path string, body map[string]any, jar map[string]string) *http.Response {
	b, _ := json.Marshal(body)
	req, _ := http.NewRequest(http.MethodPost, base+path, bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Origin", base)
	if c, ok := jar["session_id"]; ok {
		req.AddCookie(&http.Cookie{Name: "session_id", Value: c})
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return &http.Response{StatusCode: 0}
	}
	return resp
}

// TestViewerDashboardDoesNotLeakSecrets verifies the SEC-001 fix: a viewer
// must never receive notification channel secrets embedded in the dashboard.
func TestViewerDashboardDoesNotLeakSecrets(t *testing.T) {
	app, base, pw := newTestApp(t)

	// Store a notify config containing a secret token (plaintext is enough to
	// exercise the redaction path — LoadSettings passes it through).
	secret := "VIEWERMUSTNOTSEE123"
	if err := app.Store.SaveNotifyConfig(`{"telegram":{"enabled":true,"channels":[{"id":"ch1","name":"Main","token":"` + secret + `"}]}}`); err != nil {
		t.Fatalf("save notify config: %v", err)
	}

	// admin logs in and creates a viewer
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)
	resp := postJSON(base, "/api/users", map[string]any{
		"username": "viewer", "password": "ViewerPass123456", "role": "viewer",
	}, jar)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("create viewer = %d", resp.StatusCode)
	}
	resp.Body.Close()

	// viewer logs in and opens the dashboard
	vjar := map[string]string{}
	postForm(base, "/login", map[string]string{"username": "viewer", "password": "ViewerPass123456"}, vjar)
	body := getPage(base, "/", vjar)
	if strings.Contains(body, secret) {
		t.Fatalf("viewer dashboard leaked the notification secret token")
	}
	if !strings.Contains(body, "REDACTED") {
		t.Fatalf("viewer dashboard should show redacted secrets, got neither the token nor the marker")
	}
}

// TestCreateSiteRejectsInvalidMonitorType verifies arbitrary monitor_type values
// (a stored-XSS vector) are rejected server-side.
func TestCreateSiteRejectsInvalidMonitorType(t *testing.T) {
	_, base, pw := newTestApp(t)
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)
	resp := postJSON(base, "/api/sites", map[string]any{
		"name": "x", "url": "https://example.com",
		"monitor_type": `<img src=x onerror=alert(1)>`, "check_interval": 60,
	}, jar)
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("invalid monitor_type = %d, want 400", resp.StatusCode)
	}
}

// TestCreateSiteRejectsDangerousURLScheme verifies javascript:/file:/data:
// schemes are rejected for non-HTTP monitors (client-side XSS vector).
func TestCreateSiteRejectsDangerousURLScheme(t *testing.T) {
	_, base, pw := newTestApp(t)
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)
	for _, u := range []string{"javascript://alert(1)", "file:///etc/passwd", "data:text/html,<script>1</script>"} {
		resp := postJSON(base, "/api/sites", map[string]any{
			"name": "x", "url": u, "monitor_type": "port", "check_interval": 60,
		}, jar)
		if resp.StatusCode != http.StatusBadRequest {
			t.Fatalf("URL %q = %d, want 400", u, resp.StatusCode)
		}
		resp.Body.Close()
	}
}

// TestLoginRateLimitsFailedAttemptsOnly verifies the SEC-006 fix: only FAILED
// attempts count toward the lockout, and the 6th failure redirects to a
// rate_limited message.
func TestLoginRateLimitsFailedAttemptsOnly(t *testing.T) {
	_, base, _ := newTestApp(t)
	var last *http.Response
	for i := 0; i < 6; i++ {
		last = postForm(base, "/login", map[string]string{"username": "admin", "password": "WrongWrong1"}, map[string]string{})
	}
	if loc := last.Header.Get("Location"); loc != "/login?error=rate_limited" {
		t.Fatalf("6th failed login redirect = %q, want /login?error=rate_limited", loc)
	}
}
