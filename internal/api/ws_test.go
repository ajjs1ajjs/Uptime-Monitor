package api

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// wsHandshakeRequest builds a request that looks like a real browser
// WebSocket handshake (gorilla rejects anything else before it ever looks at
// the session).
func wsHandshakeRequest(target string) *http.Request {
	r := httptest.NewRequest(http.MethodGet, target, nil)
	r.Header.Set("Connection", "Upgrade")
	r.Header.Set("Upgrade", "websocket")
	r.Header.Set("Sec-WebSocket-Version", "13")
	r.Header.Set("Sec-WebSocket-Key", "dGhlIHNhbXBsZSBub25jZQ==")
	return r
}

// Regression: closeWS used to call Upgrade(w, nil, nil), and gorilla
// dereferences r.Header inside Upgrade — so every unauthenticated handshake
// panicked. /ws is reachable without credentials, so that was a remote
// stack-trace-per-request log flood.
func TestWSUnauthenticatedDoesNotPanic(t *testing.T) {
	app, _, _ := newTestApp(t)
	for _, tc := range []struct {
		name    string
		prepare func(*http.Request)
	}{
		{"no cookie", func(*http.Request) {}},
		{"invalid session", func(r *http.Request) {
			r.AddCookie(&http.Cookie{Name: sessionCookie, Value: "nope"})
		}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			r := wsHandshakeRequest("/ws")
			tc.prepare(r)
			defer func() {
				if rec := recover(); rec != nil {
					t.Fatalf("handleWS panicked: %v", rec)
				}
			}()
			app.handleWS(httptest.NewRecorder(), r)
		})
	}
}

// A plain (non-WebSocket) GET /ws must answer with 401 rather than panic or
// hang: the upgrade can't be completed, so there is no close frame to send.
func TestWSPlainRequestGets401(t *testing.T) {
	app, _, _ := newTestApp(t)
	w := httptest.NewRecorder()
	app.handleWS(w, httptest.NewRequest(http.MethodGet, "/ws", nil))
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("plain GET /ws: status = %d, want 401", w.Code)
	}
}
