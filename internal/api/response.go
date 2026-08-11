package api

import (
	"encoding/json"
	"net"
	"net/http"
	"strconv"
	"strings"
)

// maxBodyBytes caps the size of JSON/form request bodies (1 MiB) to prevent
// memory-exhaustion DoS from unbounded uploads.
const maxBodyBytes = 1 << 20

// decodeJSON decodes a JSON request body with a hard size limit. Returns the
// decoder error (e.g. "http: request body too large") for the handler to map
// to a 400 response.
func decodeJSON(w http.ResponseWriter, r *http.Request, dst any) error {
	r.Body = http.MaxBytesReader(w, r.Body, maxBodyBytes)
	return json.NewDecoder(r.Body).Decode(dst)
}

// writeErr uses the "detail" field that the frontend reads everywhere.
func writeErr(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]any{"detail": msg})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func pathInt(r *http.Request, name string) (int64, error) {
	return strconv.ParseInt(r.PathValue(name), 10, 64)
}

// clientIP resolves the real client IP for rate limiting. X-Forwarded-For is
// honored ONLY when the immediate peer is one of the configured trusted
// proxies; otherwise it is ignored so a client cannot spoof its IP and bypass
// rate limits.
func (a *App) clientIP(r *http.Request) string {
	if isTrustedPeer(r, a.Cfg.Server.TrustedProxies) {
		if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
			if first := strings.TrimSpace(strings.SplitN(xff, ",", 2)[0]); first != "" {
				return first
			}
		}
	}
	host := r.RemoteAddr
	for i := len(host) - 1; i >= 0; i-- {
		if host[i] == ':' {
			return host[:i]
		}
	}
	return host
}

// isTrustedPeer reports whether the request's immediate peer is in the trusted
// proxy CIDR list. An empty list trusts nobody.
func isTrustedPeer(r *http.Request, trusted []string) bool {
	if len(trusted) == 0 {
		return false
	}
	peerIP := net.ParseIP(hostOnly(r.RemoteAddr))
	if peerIP == nil {
		return false
	}
	for _, cidr := range trusted {
		_, ipNet, err := net.ParseCIDR(strings.TrimSpace(cidr))
		if err != nil {
			continue
		}
		if ipNet.Contains(peerIP) {
			return true
		}
	}
	return false
}

func hostOnly(host string) string {
	if h, _, err := net.SplitHostPort(host); err == nil {
		return h
	}
	return host
}

// isHTTPS reports whether the request arrived over TLS, either directly or via
// a trusted reverse proxy advertising X-Forwarded-Proto.
func (a *App) isHTTPS(r *http.Request) bool {
	if r.TLS != nil {
		return true
	}
	if isTrustedPeer(r, a.Cfg.Server.TrustedProxies) {
		return strings.EqualFold(r.Header.Get("X-Forwarded-Proto"), "https")
	}
	return false
}
