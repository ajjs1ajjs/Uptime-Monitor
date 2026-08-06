package api

import (
	"bufio"
	"context"
	"errors"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/auth"
)

type principal struct {
	UserID     int64
	Username   string
	Role       string
	IsAdmin    bool
	AuthMethod string // "session" | "api_key"
	MustChange bool
}

type ctxKey int

const principalKey ctxKey = 0

// authenticate resolves the principal from an API key or session cookie.
// Returns nil if unauthenticated.
func (a *App) authenticate(r *http.Request) *principal {
	apiKey := r.Header.Get("X-API-Key")
	if apiKey != "" {
		hash := auth.HashAPIKey(apiKey)
		key, err := a.Store.GetAPIKeyByHash(hash)
		if err != nil || key == nil || !key.IsActive {
			return nil
		}
		a.Store.TouchAPIKey(key.KeyID)
		return &principal{UserID: key.UserID, Role: "viewer", IsAdmin: false, AuthMethod: "api_key"}
	}
	cookie, err := r.Cookie(sessionCookie)
	if err != nil {
		return nil
	}
	u, err := a.Store.GetSession(cookie.Value)
	if err != nil || u == nil {
		return nil
	}
	return &principal{
		UserID: u.ID, Username: u.Username, Role: u.Role,
		IsAdmin: u.Role == "admin", AuthMethod: "session",
		MustChange: u.MustChangePassword == 1,
	}
}

// withAuth rejects unauthenticated and must-change-password requests on JSON
// API endpoints (fresh DB state, like the original).
func (a *App) withAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		p := a.authenticate(r)
		if p == nil {
			writeErr(w, http.StatusUnauthorized, "Not authenticated")
			return
		}
		if p.MustChange &&
			r.URL.Path != "/api/user" &&
			r.URL.Path != "/api/alert-policy" &&
			!strings.HasSuffix(r.URL.Path, "/change-password") {
			writeJSON(w, http.StatusForbidden, map[string]any{
				"detail": "You must change your password before continuing",
			})
			return
		}
		next(w, r.WithContext(context.WithValue(r.Context(), principalKey, p)))
	}
}

func (a *App) withAdmin(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		p := a.principal(r)
		if p == nil || !p.IsAdmin || p.AuthMethod == "api_key" {
			writeErr(w, http.StatusForbidden, "Admin access required")
			return
		}
		next(w, r)
	}
}

func (a *App) principal(r *http.Request) *principal {
	if v, ok := r.Context().Value(principalKey).(*principal); ok {
		return v
	}
	return nil
}

// withCSRF enforces same-origin for cookie-authenticated state-changing API
// requests (API-key requests are exempt). Mirrors the Python fail-closed check.
func (a *App) withCSRF(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet || r.Method == http.MethodHead || r.Method == http.MethodOptions {
			next(w, r)
			return
		}
		p := a.principal(r)
		if p != nil && p.AuthMethod == "api_key" {
			next(w, r) // API keys are not a browser CSRF vector
			return
		}
		origin := r.Header.Get("Origin")
		referer := r.Header.Get("Referer")
		host := r.Host
		valid := false
		if origin != "" {
			if u, err := url.Parse(origin); err == nil && u.Hostname() == hostnameOnly(host) {
				valid = true
			}
		} else if referer != "" {
			if u, err := url.Parse(referer); err == nil && u.Hostname() == hostnameOnly(host) {
				valid = true
			}
		}
		if !valid {
			writeErr(w, http.StatusForbidden, "CSRF: missing or mismatched Origin/Referer")
			return
		}
		next(w, r)
	}
}

func hostnameOnly(host string) string {
	if h, _, err := net.SplitHostPort(host); err == nil {
		return h
	}
	return host
}

// --- rate limiting (DB-backed, mirrors Python) ---

func (a *App) withRateLimit(endpoint string, max int, window int, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ip := clientIP(r)
		if !a.Store.RateLimitOK(endpoint, ip, max, window) {
			writeErr(w, http.StatusTooManyRequests, "Too many requests. Try again later.")
			return
		}
		next(w, r)
	}
}

// --- recovery ---

func (a *App) withRecovery(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				log.Printf("panic: %v", rec)
				writeErr(w, http.StatusInternalServerError, "Internal server error")
			}
		}()
		next(w, r)
	}
}

// --- security headers ---

func (a *App) withSecurity(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("X-XSS-Protection", "1; mode=block")
		next.ServeHTTP(w, r)
	})
}

// --- logging + hijackable writer ---

func (a *App) withLogging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/static/") || r.URL.Path == "/health" || r.URL.Path == "/metrics" || r.URL.Path == "/favicon" {
			next.ServeHTTP(w, r)
			return
		}
		start := time.Now()
		sw := &statusWriter{ResponseWriter: w, status: 200}
		next.ServeHTTP(sw, r)
		log.Printf("%s %s -> %d (%s)", r.Method, r.URL.Path, sw.status, time.Since(start).Round(time.Millisecond))
	})
}

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (w *statusWriter) WriteHeader(code int) {
	w.status = code
	w.ResponseWriter.WriteHeader(code)
}

// Hijack lets gorilla/websocket upgrade through the logging wrapper
// (a lesson from the Monitoring port).
func (w *statusWriter) Hijack() (net.Conn, *bufio.ReadWriter, error) {
	hj, ok := w.ResponseWriter.(http.Hijacker)
	if !ok {
		return nil, nil, errors.New("response writer does not support hijacking")
	}
	return hj.Hijack()
}

func (w *statusWriter) Flush() {
	if f, ok := w.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

func (w *statusWriter) ReadFrom(r io.Reader) (int64, error) {
	if rf, ok := w.ResponseWriter.(io.ReaderFrom); ok {
		return rf.ReadFrom(r)
	}
	return io.Copy(w.ResponseWriter, r)
}

var _ = sync.Mutex{}
