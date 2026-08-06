package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadToleratesScalarListField(t *testing.T) {
	dir := filepath.ToSlash(t.TempDir())
	path := filepath.Join(dir, "config.json")
	// old Python-style config with ssl_notification_days as a scalar
	os.WriteFile(path, []byte(`{
	  "server": {"port": 8080},
	  "data_dir": "`+dir+`/data",
	  "alert_policy": {
	    "ssl_notification_days": 30,
	    "retry_delays": 30
	  }
	}`), 0o644)

	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Server.Port != 8080 {
		t.Errorf("port = %d", cfg.Server.Port)
	}
	// scalar coerced to a one-element list
	if len(cfg.AlertPolicy.SSLNotificationDays) != 1 || cfg.AlertPolicy.SSLNotificationDays[0] != 30 {
		t.Errorf("ssl_notification_days = %v, want [30]", cfg.AlertPolicy.SSLNotificationDays)
	}
	if len(cfg.AlertPolicy.RetryDelays) != 1 || cfg.AlertPolicy.RetryDelays[0] != 30 {
		t.Errorf("retry_delays = %v, want [30]", cfg.AlertPolicy.RetryDelays)
	}
}

func TestLoadToleratesMissingFile(t *testing.T) {
	cfg, err := Load(filepath.Join(t.TempDir(), "nope.json"))
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg == nil || cfg.Server.Port != 8080 {
		t.Errorf("defaults not applied")
	}
}

func TestLoadDefaults(t *testing.T) {
	cfg := Default()
	if cfg.AlertPolicy.SSLNotificationCooldown != 21600 {
		t.Errorf("cooldown = %d", cfg.AlertPolicy.SSLNotificationCooldown)
	}
	if len(cfg.AlertPolicy.SSLNotificationDays) != 6 {
		t.Errorf("default ssl days = %v", cfg.AlertPolicy.SSLNotificationDays)
	}
}
