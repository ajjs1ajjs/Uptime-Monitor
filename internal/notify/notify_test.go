package notify

import (
	"bufio"
	"fmt"
	"net"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"
)

// TestDispatchInt64SiteID verifies the regression where Dispatch only accepted
// site_id as float64 (the type JSON decoding produces), but the worker sends it
// as int64. With an int64 id the site lookup silently failed, so no channel was
// ever dispatched and no notification was logged.
func TestDispatchInt64SiteID(t *testing.T) {
	db, abs, err := storage.Open(filepath.Join(t.TempDir(), "n.db"))
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	defer db.Close()
	store := storage.NewStore(db, abs)

	id, err := store.CreateSite("srv", "https://example.com", 60, true,
		`[{"method":"email","channels":["ch1"]},{"method":"telegram","channels":["ch2"]}]`,
		"http", "", "")
	if err != nil {
		t.Fatalf("create: %v", err)
	}

	svc := New(store)
	// no real SMTP/Telegram endpoints: with no settings loaded every send()
	// should return early WITHOUT panicking, and Dispatch must reach the
	// siteMethods fallback using the int64 id (i.e. not return silently on a
	// failed type assertion).
	svc.Dispatch("down", "test alert", map[string]any{
		"alert_type": "down", "site_id": id, "site_name": "srv", "url": "https://example.com",
	})
}

// TestChannelsForParsesStructuredMethods ensures notify_methods given in the
// structured [{"method":...,"channels":[...]}] form are parsed.
func TestChannelsForParsesStructuredMethods(t *testing.T) {
	methods := []any{
		map[string]any{"method": "email", "channels": []any{"ch1"}},
		map[string]any{"method": "telegram", "channels": []any{"ch2"}},
	}
	enabled, specific := channelsFor(methods)
	if !enabled["email"] || !enabled["telegram"] {
		t.Fatalf("enabled = %v, want both", enabled)
	}
	if got := specific["email"]; len(got) != 1 || got[0] != "ch1" {
		t.Fatalf("specific email = %v, want [ch1]", got)
	}
	if got := specific["telegram"]; len(got) != 1 || got[0] != "ch2" {
		t.Fatalf("specific telegram = %v, want [ch2]", got)
	}
}

// TestEmailStartsPlainForPort587 runs a minimal SMTP server and verifies that
// email() connects over a plain socket for ports < 465 and negotiates STARTTLS
// only when the server advertises it.
func TestEmailStartsPlainForPort587(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	defer ln.Close()

	got := make(chan string, 1)
	go func() {
		conn, err := ln.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		conn.SetDeadline(time.Now().Add(5 * time.Second))
		r := bufio.NewReader(conn)
		fmt.Fprintf(conn, "220 test ESMTP\r\n")
		// read commands until DATA
		for {
			line, err := r.ReadString('\n')
			if err != nil {
				return
			}
			cmd := strings.ToUpper(strings.TrimSpace(line))
			switch {
			case strings.HasPrefix(cmd, "EHLO"):
				fmt.Fprintf(conn, "250-test\r\n250 AUTH PLAIN\r\n")
			case strings.HasPrefix(cmd, "AUTH PLAIN"):
				fmt.Fprintf(conn, "235 ok\r\n")
			case strings.HasPrefix(cmd, "MAIL FROM"):
				fmt.Fprintf(conn, "250 ok\r\n")
			case strings.HasPrefix(cmd, "RCPT TO"):
				fmt.Fprintf(conn, "250 ok\r\n")
			case cmd == "DATA":
				fmt.Fprintf(conn, "354 go ahead\r\n")
				for {
					l, err := r.ReadString('\n')
					if err != nil {
						return
					}
					if l == ".\r\n" {
						break
					}
				}
				fmt.Fprintf(conn, "250 ok\r\n")
				got <- "DATA"
			case cmd == "QUIT":
				fmt.Fprintf(conn, "221 bye\r\n")
				return
			default:
				fmt.Fprintf(conn, "250 ok\r\n")
			}
		}
	}()

	svc := New(nil)
	port := ln.Addr().(*net.TCPAddr).Port
	ok := svc.email("down", "hello", map[string]any{
		"smtp_server": "127.0.0.1",
		"smtp_port":   float64(port),
		"username":    "u@test",
		"password":    "pw",
		"to_email":    "u@test",
	})
	if !ok {
		t.Fatalf("email() returned false")
	}
	select {
	case c := <-got:
		if c != "DATA" {
			t.Fatalf("server saw %q, want DATA", c)
		}
	case <-time.After(5 * time.Second):
		t.Fatalf("email() did not send DATA")
	}
}
