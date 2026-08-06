package api

import (
	"encoding/json"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type WSManager struct {
	mu          sync.Mutex
	connections map[*websocket.Conn]struct{}
}

func NewWSManager() *WSManager {
	return &WSManager{connections: map[*websocket.Conn]struct{}{}}
}

// Broadcast satisfies monitor.Broadcaster.
func (m *WSManager) Broadcast(event map[string]any) {
	m.mu.Lock()
	conns := make([]*websocket.Conn, 0, len(m.connections))
	for c := range m.connections {
		conns = append(conns, c)
	}
	m.mu.Unlock()
	b, _ := json.Marshal(event)
	for _, c := range conns {
		if err := c.WriteMessage(websocket.TextMessage, b); err != nil {
			m.remove(c)
			_ = c.Close()
		}
	}
}

func (m *WSManager) add(c *websocket.Conn) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.connections[c] = struct{}{}
}

func (m *WSManager) remove(c *websocket.Conn) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.connections, c)
}

var wsUpgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     func(r *http.Request) bool { return true },
}

func (a *App) handleWS(w http.ResponseWriter, r *http.Request) {
	// Authenticate via session cookie (mirrors Python).
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
	a.WS.add(conn)
	defer a.WS.remove(conn)
	defer conn.Close()

	for {
		_ = conn.SetReadDeadline(time.Now().Add(120 * time.Second))
		_, msg, err := conn.ReadMessage()
		if err != nil {
			return
		}
		if string(msg) == "ping" {
			if err := conn.WriteMessage(websocket.TextMessage, []byte("pong")); err != nil {
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
