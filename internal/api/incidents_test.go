package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"
)

// Regression: /api/incidents used to LIMIT 200 raw down/slow rows and only
// then drop outage-continuation rows in Go. One long outage therefore ate the
// whole budget and the endpoint reported a single incident while silently
// hiding every older one. The "is this the start of an outage" filter now runs
// inside SQL, before LIMIT.
func TestIncidentsNotSwallowedByOneLongOutage(t *testing.T) {
	app, _, _ := newTestApp(t)
	siteID, err := app.Store.CreateSite("s", "https://example.com", 60, true, "[]", "http", "", "[]")
	if err != nil {
		t.Fatalf("create site: %v", err)
	}

	// Oldest first so LAG() sees a sensible timeline. minutesAgo counts down.
	add := func(minutesAgo int, status string) {
		ts := storage.TimeString(time.Now().Add(-time.Duration(minutesAgo) * time.Minute))
		if _, err := app.Store.DB.Exec(
			`INSERT INTO status_history (site_id, status, checked_at) VALUES (?,?,?)`,
			siteID, status, ts); err != nil {
			t.Fatalf("insert history: %v", err)
		}
	}

	add(400, "up")
	add(399, "down") // incident A
	add(398, "up")
	// Incident B: one long outage, longer than the old 200-row budget.
	for i := 300; i > 50; i-- {
		add(i, "down")
	}

	req := httptest.NewRequest(http.MethodGet, "/api/incidents", nil)
	w := httptest.NewRecorder()
	app.handleIncidents(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (%s)", w.Code, w.Body.String())
	}
	var got []map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("incidents = %d, want 2 (one per outage, not one per down check)", len(got))
	}
	// Newest first: incident B then incident A.
	if got[0]["prev_status"] != "up" || got[1]["prev_status"] != "up" {
		t.Errorf("every reported incident must start from an up state, got %v and %v",
			got[0]["prev_status"], got[1]["prev_status"])
	}
}
