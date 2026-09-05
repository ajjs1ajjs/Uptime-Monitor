package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
)

type Server struct {
	Port   int    `json:"port"`
	Host   string `json:"host"`
	Domain string `json:"domain"`
	// TrustedProxies lists proxy CIDRs (e.g. "10.0.0.0/8") whose
	// X-Forwarded-For/X-Forwarded-Proto headers are honored. When empty, these
	// headers are ignored and r.RemoteAddr is always used, so clients cannot
	// spoof their IP to bypass rate limiting.
	TrustedProxies []string `json:"trusted_proxies"`
	// AllowLocalhost, when true, permits creating monitors that target the
	// "localhost" hostname (otherwise the SSRF guard blocks it).
	AllowLocalhost bool `json:"allow_localhost"`
	// AllowPrivateNetworks, when true, permits creating monitors that target
	// RFC1918/ULA private-range addresses (10.0.0.0/8, 172.16.0.0/12,
	// 192.168.0.0/16, fc00::/7). Off by default so a monitor pointed at an
	// attacker-controlled hostname cannot be used to probe the internal
	// network the server runs on; enable explicitly for legitimate internal
	// infrastructure monitoring.
	AllowPrivateNetworks bool `json:"allow_private_networks"`
}

type CORS struct {
	AllowOrigins []string `json:"allow_origins"`
}

type SSL struct {
	Enabled      bool   `json:"enabled"`
	CertPath     string `json:"cert_path"`
	KeyPath      string `json:"key_path"`
	RedirectHTTP bool   `json:"redirect_http"`
	HSTS         bool   `json:"hsts"`
	HSTSMaxAge   int    `json:"hsts_max_age"`
}

// IntList accepts either a JSON array or a single number (tolerant of config
// files where the field was written as a scalar).
type IntList []int

func (l *IntList) UnmarshalJSON(b []byte) error {
	if string(b) == "null" || string(b) == "" {
		return nil
	}
	var arr []int
	if err := json.Unmarshal(b, &arr); err == nil {
		*l = arr
		return nil
	}
	var n int
	if err := json.Unmarshal(b, &n); err == nil {
		*l = []int{n}
		return nil
	}
	// Unparseable: leave as nil (defaults will be applied later).
	return nil
}

type AlertPolicy struct {
	RequestTimeoutSeconds   int     `json:"request_timeout_seconds"`
	GracePeriodSeconds      int     `json:"grace_period_seconds"`
	UpSuccessThreshold      int     `json:"up_success_threshold"`
	StillDownRepeatSeconds  int     `json:"still_down_repeat_seconds"`
	Treat4xxAsDown          bool    `json:"treat_4xx_as_down"`
	VerifySSL               bool    `json:"verify_ssl"`
	SSLNotificationDays     IntList `json:"ssl_notification_days"`
	SSLNotificationCooldown int     `json:"ssl_notification_cooldown_seconds"`
	SSLCheckIntervalHours   int     `json:"ssl_check_interval_hours"`
	RetryDelays             IntList `json:"retry_delays"`
	MaxRetries              int     `json:"max_retries"`
}

type Backup struct {
	Enabled    bool   `json:"enabled"`
	MaxBackups int    `json:"max_backups"`
	BackupDir  string `json:"backup_dir"`
}

type Config struct {
	Server        Server      `json:"server"`
	CORS          CORS        `json:"cors"`
	SSL           SSL         `json:"ssl"`
	DataDir       string      `json:"data_dir"`
	LogDir        string      `json:"log_dir"`
	CheckInterval int         `json:"check_interval"`
	AlertPolicy   AlertPolicy `json:"alert_policy"`
	Backup        Backup      `json:"backup"`

	path string `json:"-"`
}

func defaultDataDir() string {
	if runtime.GOOS == "windows" {
		return filepath.Join(os.Getenv("USERPROFILE"), "UptimeMonitor", "data")
	}
	return "/var/lib/uptime-monitor"
}

func defaultLogDir() string {
	if runtime.GOOS == "windows" {
		return filepath.Join(os.Getenv("USERPROFILE"), "UptimeMonitor", "logs")
	}
	return "/var/log/uptime-monitor"
}

func Default() *Config {
	return &Config{
		Server:        Server{Port: 8080, Host: "auto", Domain: "auto", AllowLocalhost: false, AllowPrivateNetworks: false},
		CORS:          CORS{AllowOrigins: []string{"http://localhost:8080"}},
		SSL:           SSL{HSTSMaxAge: 31536000},
		DataDir:       defaultDataDir(),
		LogDir:        defaultLogDir(),
		CheckInterval: 60,
		AlertPolicy: AlertPolicy{
			RequestTimeoutSeconds:   15,
			UpSuccessThreshold:      3,
			StillDownRepeatSeconds:  600,
			Treat4xxAsDown:          true,
			VerifySSL:               true,
			SSLNotificationDays:     []int{30, 14, 7, 5, 3, 1},
			SSLNotificationCooldown: 21600,
			SSLCheckIntervalHours:   6,
			RetryDelays:             []int{10, 10, 10, 10, 10},
			MaxRetries:              5,
		},
		Backup: Backup{Enabled: true, MaxBackups: 10},
	}
}

func deepMerge(base, overlay map[string]any) map[string]any {
	out := map[string]any{}
	for k, v := range base {
		out[k] = v
	}
	for k, v := range overlay {
		if bm, ok := out[k].(map[string]any); ok {
			if om, ok2 := v.(map[string]any); ok2 {
				out[k] = deepMerge(bm, om)
				continue
			}
		}
		out[k] = v
	}
	return out
}

func Load(path string) (*Config, error) {
	cfg := Default()
	if path == "" {
		path = os.Getenv("CONFIG_PATH")
	}
	if path == "" {
		if _, err := os.Stat("config.json"); err == nil {
			path = "config.json"
		} else if runtime.GOOS != "windows" {
			if _, err := os.Stat("/etc/uptime-monitor/config.json"); err == nil {
				path = "/etc/uptime-monitor/config.json"
			}
		}
	}
	if path == "" {
		return cfg, nil
	}
	cfg.path = path
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			fmt.Fprintf(os.Stderr, "config: %s not found, using defaults\n", path)
			return cfg, nil
		}
		return nil, fmt.Errorf("read config: %w", err)
	}
	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		// Loud and impossible to miss in journalctl/logs: an operator who
		// edited config.json and made a syntax error must know their changes
		// were NOT applied, not just see a quiet one-liner buried in startup
		// output while security-relevant settings (allow_localhost, CORS,
		// trusted_proxies) silently reverted to defaults.
		fmt.Fprintf(os.Stderr, "config: ERROR: %s is invalid JSON (%v) - IGNORING IT, using built-in defaults instead. Your configuration was NOT applied.\n", path, err)
		return cfg, nil
	}
	base, _ := json.Marshal(cfg)
	var baseMap map[string]any
	_ = json.Unmarshal(base, &baseMap)
	merged := deepMerge(baseMap, raw)
	b, _ := json.Marshal(merged)
	if err := json.Unmarshal(b, cfg); err != nil {
		// Tolerant: a malformed section (e.g. alert_policy written by an older
		// version) must not prevent the server from starting. Drop the bad
		// top-level sections and keep the rest.
		fmt.Fprintf(os.Stderr, "config: ERROR: %s has an invalid section (%v) - that section falls back to defaults; the rest of the file was applied.\n", path, err)
		for k := range raw {
			merged2 := deepMerge(baseMap, raw)
			delete(merged2, k)
			b2, _ := json.Marshal(merged2)
			if err2 := json.Unmarshal(b2, cfg); err2 == nil {
				return cfg, nil
			}
		}
		return cfg, nil
	}
	return cfg, nil
}

// Save persists the config back to the file it was loaded from, preserving
// only the fields written by the app (alert policy). The path falls back to
// CONFIG_PATH so API-driven changes survive restarts.
func (c *Config) Save() error {
	path := c.Path()
	if path == "" {
		return fmt.Errorf("config path not set")
	}
	b, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, b, 0o644)
}

// WriteDefaultFile writes a default config to the given path (used by tests
// and first-run setup).
func (c *Config) WriteDefaultFile(path string) error {
	b, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, b, 0o644)
}

func (c *Config) Path() string {
	if c.path != "" {
		return c.path
	}
	if p := os.Getenv("CONFIG_PATH"); p != "" {
		return p
	}
	return "config.json"
}

func (c *Config) DBPath() string {
	if p := os.Getenv("DB_PATH"); p != "" {
		return p
	}
	if c.DataDir == "" {
		c.DataDir = defaultDataDir()
	}
	return filepath.Join(c.DataDir, "sites.db")
}

func (c *Config) MasterKeyPath() string {
	if k := os.Getenv("UPTIME_MONITOR_MASTER_KEY"); k != "" {
		return ""
	}
	return filepath.Join(configDir(), "master.key")
}

func configDir() string {
	if c := os.Getenv("CONFIG_PATH"); c != "" {
		return filepath.Dir(c)
	}
	if runtime.GOOS == "windows" {
		return filepath.Join(os.Getenv("USERPROFILE"), "UptimeMonitor")
	}
	return "/etc/uptime-monitor"
}

func (c *Config) BackupDir() string {
	if c.Backup.BackupDir != "" {
		return c.Backup.BackupDir
	}
	return filepath.Join(filepath.Dir(c.DBPath()), "backups")
}
