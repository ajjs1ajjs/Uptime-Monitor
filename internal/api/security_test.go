package api

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/config"
)

func TestClientIPIgnoresSpoofedXFF(t *testing.T) {
	a := &App{Cfg: config.Default()}
	r := httptest.NewRequest(http.MethodGet, "/health", nil)
	r.RemoteAddr = "203.0.113.7:55555"
	r.Header.Set("X-Forwarded-For", "6.6.6.6")
	if got := a.clientIP(r); got != "203.0.113.7" {
		t.Fatalf("clientIP = %q, want untrusted RemoteAddr", got)
	}
}

func TestClientIPTrustsXFFFromTrustedProxy(t *testing.T) {
	cfg := config.Default()
	cfg.Server.TrustedProxies = []string{"127.0.0.0/8", "10.0.0.0/8"}
	a := &App{Cfg: cfg}
	r := httptest.NewRequest(http.MethodGet, "/health", nil)
	r.RemoteAddr = "10.0.0.2:8080"
	r.Header.Set("X-Forwarded-For", "198.51.100.9, 10.0.0.1")
	if got := a.clientIP(r); got != "198.51.100.9" {
		t.Fatalf("clientIP = %q, want first XFF value", got)
	}
	// an untrusted peer must NOT have its XFF honored
	r.RemoteAddr = "198.51.100.9:8080"
	if got := a.clientIP(r); got != "198.51.100.9" {
		t.Fatalf("clientIP = %q, want RemoteAddr for untrusted peer", got)
	}
}

func TestCSVSafe(t *testing.T) {
	cases := map[string]string{
		"normal": "normal",
		"":       "",
		"=cmd":   "'=cmd",
		"+1":     "'+1",
		"-2":     "'-2",
		"@sum":   "'@sum",
		"\ttab":  "'\ttab",
	}
	for in, want := range cases {
		if got := csvSafe(in); got != want {
			t.Fatalf("csvSafe(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestResolvesBlockedLocalhost(t *testing.T) {
	cfg := config.Default()
	cfg.Server.AllowLocalhost = false
	a := &App{Cfg: cfg}
	if !a.resolvesBlocked("localhost") {
		t.Fatalf("localhost should be blocked by default")
	}
	cfg.Server.AllowLocalhost = true
	if a.resolvesBlocked("localhost") {
		t.Fatalf("localhost should be allowed when server.allow_localhost is enabled")
	}
	// numeric loopback must always be blocked regardless of the flag
	if !a.resolvesBlocked("127.0.0.1") {
		t.Fatalf("loopback IP must always be blocked")
	}
}

func TestCheckOrigin(t *testing.T) {
	r := httptest.NewRequest(http.MethodGet, "/ws", nil)
	r.Host = "uptime.example.com"
	r.Header.Set("Origin", "https://uptime.example.com")
	if !checkOrigin(r) {
		t.Fatalf("same-origin request rejected")
	}
	r.Header.Set("Origin", "https://evil.example.com")
	if checkOrigin(r) {
		t.Fatalf("cross-origin request accepted")
	}
	r.Header.Set("Origin", "")
	if !checkOrigin(r) {
		t.Fatalf("no-origin (non-browser) request rejected")
	}
}

func TestRateLimitBlocksAfterMax(t *testing.T) {
	rl := newRateLimitStore()
	key := "login|1.2.3.4"
	if !rl.allow(key, 2, time.Minute) {
		t.Fatalf("first request should be allowed")
	}
	if !rl.allow(key, 2, time.Minute) {
		t.Fatalf("second request should be allowed")
	}
	if rl.allow(key, 2, time.Minute) {
		t.Fatalf("third request should be blocked")
	}
}

func TestBodySizeLimit(t *testing.T) {
	_, base, pw := newTestApp(t)
	jar := map[string]string{}
	login(base, pw, "NewStrongPass123", jar)
	postForm(base, "/login", map[string]string{"username": "admin", "password": "NewStrongPass123"}, jar)

	big := strings.Repeat("A", 2<<20) // 2 MiB > 1 MiB limit
	payload := `{"name":"` + big + `","url":"https://example.com","monitor_type":"http","check_interval":60}`
	req, _ := http.NewRequest(http.MethodPost, base+"/api/sites", strings.NewReader(payload))
	req.AddCookie(&http.Cookie{Name: "session_id", Value: jar["session_id"]})
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Origin", base)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("req: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("oversized body = %d, want 400", resp.StatusCode)
	}
}
