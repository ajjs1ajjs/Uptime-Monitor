package notify

import (
	"path/filepath"
	"testing"

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
