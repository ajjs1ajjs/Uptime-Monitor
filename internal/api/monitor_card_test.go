package api

import (
	"testing"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"
)

func TestMonitorCardPartialRenders(t *testing.T) {
	app := &App{Set: NewTemplateSet()}
	s := storage.Site{
		ID: 1, Name: "Example", URL: "https://example.com", CheckInterval: 60,
		IsActive: true, Status: "unknown", MonitorType: "http",
		Tags: "[]", NotifyMethods: "[]",
	}
	ctx := monitorCardCtx(s)
	html, err := app.render("partials/monitor_card.html", ctx)
	if err != nil {
		t.Fatalf("render error: %v", err)
	}
	t.Logf("rendered: %s", html)
	if html == "" {
		t.Fatalf("empty render")
	}
}
