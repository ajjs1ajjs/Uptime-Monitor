package api

import (
	"encoding/json"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// wsConn wraps a websocket connection with a write mutex. gorilla/websocket
// allows only one concurrent writer per connection; broadcasts from the worker
// goroutines and the ping/pong replies from the read loop can fire in parallel,
// so every write must be serialized per connection.
type wsConn struct {
	conn *websocket.Conn
	mu   sync.Mutex
}

type WSManager struct {
	mu          sync.Mutex
	connections map[*wsConn]struct{}
}

func NewWSManager() *WSManager {
	return &WSManager{connections: map[*wsConn]struct{}{}}
}

// Broadcast satisfies monitor.Broadcaster.
func (m *WSManager) Broadcast(event map[string]any) {
	m.mu.Lock()
	conns := make([]*wsConn, 0, len(m.connections))
	for c := range m.connections {
		conns = append(conns, c)
	}
	m.mu.Unlock()
	b, _ := json.Marshal(event)
	for _, c := range conns {
		c.mu.Lock()
		_ = c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
		err := c.conn.WriteMessage(websocket.TextMessage, b)
		c.mu.Unlock()
		if err != nil {
			m.remove(c)
			_ = c.conn.Close()
		}
	}
}

func (m *WSManager) add(c *wsConn) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.connections[c] = struct{}{}
}

func (m *WSManager) remove(c *wsConn) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.connections, c)
}

// checkOrigin allows a browser-initiated WebSocket only when the Origin
// matches this server's host. The session cookie is attached automatically to
// any cross-origin WebSocket handshake, so accepting every Origin would leak
// real-time monitoring data to any website the authenticated user visits
// (CSWSH). Non-browser clients that omit the Origin header are allowed.
func checkOrigin(r *http.Request) bool {
	origin := r.Header.Get("Origin")
	if origin == "" {
		return true
	}
	u, err := url.Parse(origin)
	if err != nil {
		return false
	}
	return strings.EqualFold(u.Hostname(), hostnameOnly(r.Host))
}

var wsUpgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     checkOrigin,
}

func (a *App) handleWS(w http.ResponseWriter, r *http.Request) {
	// Authenticate via session cookie.
	cookie, err := r.Cookie(sessionCookie)
	if err != nil {
		closeWS(w, 4001, "Authentication required")
		return
	}
	u, err := a.Store.GetSession(cookie.Value)
	if err != nil || u == nil {
		closeWS(w, 4001, "Invalid session")
		return
	}
	conn, err := wsUpgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	wc := &wsConn{conn: conn}
	a.WS.add(wc)
	defer a.WS.remove(wc)
	defer conn.Close()

	for {
		_ = conn.SetReadDeadline(time.Now().Add(120 * time.Second))
		_, msg, err := conn.ReadMessage()
		if err != nil {
			return
		}
		if string(msg) == "ping" {
			wc.mu.Lock()
			_ = conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			err = conn.WriteMessage(websocket.TextMessage, []byte("pong"))
			wc.mu.Unlock()
			if err != nil {
				return
			}
		}
	}
}

func closeWS(w http.ResponseWriter, code int, reason string) {
	conn, err := wsUpgrader.Upgrade(w, nil, nil)
	if err == nil {
		_ = conn.WriteControl(websocket.CloseMessage,
			websocket.FormatCloseMessage(code, reason), time.Now().Add(time.Second))
		_ = conn.Close()
	}
}
