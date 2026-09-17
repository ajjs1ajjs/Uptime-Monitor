package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadToleratesScalarListField(t *testing.T) {
	dir := filepath.ToSlash(t.TempDir())
	path := filepath.Join(dir, "config.json")
	// legacy-style config with ssl_notification_days as a scalar
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

// A malformed section must fall back to its defaults without dragging the rest
// of the file down with it - and without leaking half-applied values from the
// failed decode (json.Unmarshal assigns fields until it hits the error, so the
// retry has to start from a fresh struct).
func TestLoadDropsOnlyTheBrokenSection(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "config.json")
	const raw = `{
	  "server": {"port": 9999, "allow_private_networks": true},
	  "data_dir": "/srv/uptime",
	  "alert_policy": {"max_retries": "not a number", "up_success_threshold": 42}
	}`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}
	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if cfg.Server.Port != 9999 || !cfg.Server.AllowPrivateNetworks {
		t.Errorf("valid server section was dropped: %+v", cfg.Server)
	}
	if cfg.DataDir != "/srv/uptime" {
		t.Errorf("data_dir = %q, want /srv/uptime", cfg.DataDir)
	}
	// The broken section must be the default, not a partial decode of itself.
	def := Default().AlertPolicy
	if cfg.AlertPolicy.MaxRetries != def.MaxRetries {
		t.Errorf("max_retries = %d, want the default %d", cfg.AlertPolicy.MaxRetries, def.MaxRetries)
	}
	if cfg.AlertPolicy.UpSuccessThreshold != def.UpSuccessThreshold {
		t.Errorf("up_success_threshold = %d, want the default %d (no half-applied values from the broken section)",
			cfg.AlertPolicy.UpSuccessThreshold, def.UpSuccessThreshold)
	}
	if cfg.Path() != path {
		t.Errorf("Path() = %q, want %q (Save must still target the file it loaded)", cfg.Path(), path)
	}
}

// DBPath must not mutate the config: the worker reads the same struct from
// another goroutine.
func TestDBPathDoesNotMutateConfig(t *testing.T) {
	t.Setenv("DB_PATH", "")
	cfg := Default()
	cfg.DataDir = ""
	got := cfg.DBPath()
	if cfg.DataDir != "" {
		t.Errorf("DBPath() wrote DataDir = %q as a side effect", cfg.DataDir)
	}
	if got == "" {
		t.Errorf("DBPath() = %q, want a default path", got)
	}
}
