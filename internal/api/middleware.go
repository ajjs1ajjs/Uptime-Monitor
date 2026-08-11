package api

import (
	"bufio"
	"context"
	"errors"
	"io"
	"log/slog"
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
// requests (API-key requests are exempt).
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

// --- rate limiting (in-memory fixed window) ---
//
// A process-local limiter is used instead of the DB-backed one: SQLite
// serializes writes, so a DB write on every request becomes a bottleneck and a
// DoS vector under load. The single-instance deployment means the in-memory
// state is authoritative; expired entries are pruned lazily to bound memory.

type rateBucket struct {
	count   int
	resetAt time.Time
}

type rateLimitStore struct {
	mu      sync.Mutex
	buckets map[string]rateBucket // key: endpoint+"|"+ip
}

func newRateLimitStore() *rateLimitStore {
	return &rateLimitStore{buckets: map[string]rateBucket{}}
}

func (r *rateLimitStore) allow(key string, max int, window time.Duration) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	now := time.Now()
	b, ok := r.buckets[key]
	if !ok || now.After(b.resetAt) {
		if len(r.buckets) > 10000 {
			for k, v := range r.buckets {
				if now.After(v.resetAt) {
					delete(r.buckets, k)
				}
			}
		}
		r.buckets[key] = rateBucket{count: 1, resetAt: now.Add(window)}
		return true
	}
	if b.count < max {
		b.count++
		r.buckets[key] = b
		return true
	}
	return false
}

func (a *App) withRateLimit(endpoint string, max int, window int, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ip := a.clientIP(r)
		if !a.rateLimiter.allow(endpoint+"|"+ip, max, time.Duration(window)*time.Second) {
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
				slog.Error("panic recovered", "request_id", requestID(r), "path", r.URL.Path, "value", rec)
				writeErr(w, http.StatusInternalServerError, "Internal server error")
			}
		}()
		next(w, r)
	}
}

// --- security headers ---

// securityCSP: all frontend assets are self-hosted and all scripts are loaded
// from files (inline <script> blocks and event-attribute handlers were
// extracted to /static/*.js), so no 'unsafe-inline'/'unsafe-eval' is needed for
// scripts. style-src keeps 'unsafe-inline' for the remaining inline <style>
// blocks and style="" attributes.
const securityCSP = "default-src 'self'; " +
	"script-src 'self'; " +
	"style-src 'self' 'unsafe-inline'; " +
	"img-src 'self' data: blob: https:; " +
	"font-src 'self' data: https:; " +
	"connect-src 'self' ws: wss:; " +
	"frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"

func (a *App) withSecurity(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("X-XSS-Protection", "1; mode=block")
		w.Header().Set("Content-Security-Policy", securityCSP)
		next.ServeHTTP(w, r)
	})
}

// --- logging + hijackable writer ---

// reqIDKey carries a per-request correlation ID through the context so log
// entries from a single request can be grouped.
type reqIDKey struct{}

func (a *App) withLogging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/static/") || r.URL.Path == "/health" || r.URL.Path == "/metrics" || r.URL.Path == "/favicon" {
			next.ServeHTTP(w, r)
			return
		}
		start := time.Now()
		reqID := auth.RandomToken(8)
		w.Header().Set("X-Request-ID", reqID)
		ctx := context.WithValue(r.Context(), reqIDKey{}, reqID)
		sw := &statusWriter{ResponseWriter: w, status: 200}
		next.ServeHTTP(sw, r.WithContext(ctx))
		slog.Info("http",
			"request_id", reqID,
			"method", r.Method,
			"path", r.URL.Path,
			"status", sw.status,
			"duration_ms", time.Since(start).Milliseconds(),
			"ip", a.clientIP(r),
		)
	})
}

// requestID returns the correlation ID previously attached by withLogging, or
// an empty string.
func requestID(r *http.Request) string {
	if id, ok := r.Context().Value(reqIDKey{}).(string); ok {
		return id
	}
	return ""
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
