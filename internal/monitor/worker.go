package monitor

import (
	"bytes"
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/config"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/netguard"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"
)

type Broadcaster interface {
	Broadcast(event map[string]any)
}

type AlertSink interface {
	Dispatch(alertType, message string, alert map[string]any)
}

type Worker struct {
	Cfg   *config.Config
	Store *storage.Store
	WS    Broadcaster
	Alert AlertSink

	HTTP *http.Client

	mu          sync.Mutex
	active      map[int64]bool
	lastSeen    map[int64]time.Time
	lastSSL     time.Time
	lastCleanup time.Time
	lastBackup  time.Time
	maintCache  []storage.MaintenanceWindow
	maintCached time.Time
	inflight    sync.WaitGroup
	// Bounded concurrency (self-DoS guard): max 50 concurrent site checks
	// and max 10 concurrent alert deliveries. Without these, N due sites
	// (5s interval) spawn N goroutines that wedge wg.Wait + SQLite pool.
	checkSem chan struct{}
	alertSem chan struct{}
	dropped  uint64 // alerts dropped when alertSem is full (visible in logs)
	// AlertSync forces synchronous dispatch (tests). Production stays async.
	AlertSync bool
	// IsLeader gates check cycles in HA active-passive setups: standbys skip
	// checks (reads/mutations served by HTTP layer rules). Nil = leader.
	IsLeader func() bool
	regexMu  sync.Mutex
	regexes  map[string]*regexp.Regexp
}

func New(cfg *config.Config, store *storage.Store, ws Broadcaster, alert AlertSink) *Worker {
	return &Worker{
		Cfg: cfg, Store: store, WS: ws, Alert: alert,
		HTTP:     &http.Client{Timeout: 30 * time.Second},
		active:   map[int64]bool{},
		lastSeen: map[int64]time.Time{},
		checkSem: make(chan struct{}, 50),
		alertSem: make(chan struct{}, 10),
		regexes:  map[string]*regexp.Regexp{},
	}
}

func (w *Worker) Run(ctx context.Context) {
	go w.loop(ctx)
}

func (w *Worker) loop(ctx context.Context) {
	time.Sleep(5 * time.Second)
	lastChecked := map[int64]time.Time{}
	for {
		select {
		case <-ctx.Done():
			return
		default:
		}
		// HA active-passive: only the leader runs checks and maintenance
		// jobs (cleanup/backup/SSL). Standbys keep serving reads via HTTP.
		leader := true
		if w.IsLeader != nil {
			leader = w.IsLeader()
		}
		if leader {
			if err := w.CheckDue(ctx, lastChecked); err != nil {
				slog.Error("monitor check cycle failed", "error", err)
			}
			w.cleanupIfDue()
			w.backupIfDue()
			w.sslIfDue()
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(5 * time.Second):
		}
	}
}

func (w *Worker) cleanupIfDue() {
	w.mu.Lock()
	defer w.mu.Unlock()
	if time.Since(w.lastCleanup) < time.Hour {
		return
	}
	w.lastCleanup = time.Now()
	_ = w.Store.Cleanup()
}

// backupIfDue creates a scheduled backup once per day (when backup.enabled)
// and rotates old backups down to backup.max_backups.
func (w *Worker) backupIfDue() {
	w.mu.Lock()
	due := w.Cfg.Backup.Enabled && time.Since(w.lastBackup) >= 24*time.Hour
	if due {
		w.lastBackup = time.Now()
	}
	w.mu.Unlock()
	if !due {
		return
	}
	if _, err := w.Store.CreateBackup(w.Cfg.BackupDir()); err != nil {
		slog.Error("scheduled backup failed", "error", err)
		return
	}
	max := w.Cfg.Backup.MaxBackups
	if max <= 0 {
		return
	}
	// Bounded list (rotation needs only the newest max+1 rows, not the whole
	// table): Backups(100000) loaded everything into memory every day.
	all, err := w.Store.Backups(max + 1)
	if err != nil || len(all) <= max {
		return
	}
	// Backups() is ordered id DESC (newest first); delete the oldest extras.
	for i := max; i < len(all); i++ {
		var id int64
		switch v := all[i]["id"].(type) {
		case int64:
			id = v
		case float64:
			id = int64(v)
		default:
			continue
		}
		if err := w.Store.DeleteBackup(id); err != nil {
			slog.Error("backup rotation failed", "id", id, "error", err)
		}
	}
}

func (w *Worker) sslIfDue() {
	w.mu.Lock()
	interval := time.Duration(w.Cfg.GetAlertPolicy().SSLCheckIntervalHours) * time.Hour
	if interval <= 0 {
		interval = 6 * time.Hour
	}
	due := time.Since(w.lastSSL) >= interval
	w.mu.Unlock()
	if due {
		w.CheckAllCertificates()
	}
}

// CheckDue runs checks for sites whose interval has elapsed. Checks run in
// goroutines tracked by the inflight WaitGroup so shutdown can wait for them.
func (w *Worker) CheckDue(ctx context.Context, lastChecked map[int64]time.Time) error {
	sites, err := w.Store.GetActiveSites()
	if err != nil {
		return err
	}
	now := time.Now()
	var wg sync.WaitGroup
	for i := range sites {
		s := &sites[i]
		interval := time.Duration(s.CheckInterval) * time.Second
		if interval <= 0 {
			interval = 60 * time.Second
		}
		if last, ok := lastChecked[s.ID]; ok && now.Sub(last) < interval {
			continue
		}
		w.mu.Lock()
		if w.active[s.ID] {
			w.mu.Unlock()
			continue
		}
		w.active[s.ID] = true
		w.mu.Unlock()

		lastChecked[s.ID] = now
		// Bounded fan-out: skip (leave for next tick) instead of
		// spawning unbounded goroutines when the pool is saturated.
		select {
		case w.checkSem <- struct{}{}:
		case <-ctx.Done():
			w.mu.Lock()
			delete(w.active, s.ID)
			w.mu.Unlock()
			continue
		default:
			w.mu.Lock()
			delete(w.active, s.ID)
			w.mu.Unlock()
			slog.Warn("monitor pool saturated, site deferred", "site_id", s.ID)
			continue
		}
		wg.Add(1)
		w.inflight.Add(1)
		go func(site *storage.Site) {
			defer func() { <-w.checkSem }()
			defer wg.Done()
			defer w.inflight.Done()
			defer func() {
				w.mu.Lock()
				delete(w.active, site.ID)
				w.mu.Unlock()
			}()
			w.CheckSite(ctx, site)
		}(s)
	}
	wg.Wait()
	return nil
}

// InspectActive reports the number of sites currently marked active
// (test/sim hook: proves no check leaked its slot after a flood).
func (w *Worker) InspectActive(f func(n int)) {
	w.mu.Lock()
	defer w.mu.Unlock()
	f(len(w.active))
}

// WaitInflight blocks until in-flight checks finish or the timeout elapses.
func (w *Worker) WaitInflight(timeout time.Duration) {
	done := make(chan struct{})
	go func() {
		w.inflight.Wait()
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(timeout):
	}
}

// CheckSite runs one full check (with retries) and persists the result.
func (w *Worker) CheckSite(ctx context.Context, s *storage.Site) {
	// Snapshot the policy once per check so a concurrent admin save cannot
	// tear the struct mid-cycle ( ARCH-002: copy-modify-swap on the API side,
	// atomic snapshot read here).
	policy := w.Cfg.GetAlertPolicy()
	if w.isUnderMaintenance(s.ID) {
		return
	}
	status, code, rt, errMsg := "down", 0, 0.0, ""
	retries := s.MaxRetries
	if retries < 0 {
		retries = policy.MaxRetries
	}
	if retries < 0 {
		retries = 0
	}
	retryInterval := s.RetryIntervalSeconds
	if retryInterval <= 0 {
		retryInterval = 30
		if len(policy.RetryDelays) > 0 {
			retryInterval = policy.RetryDelays[0]
		}
	}
	for attempt := 0; attempt <= retries; attempt++ {
		select {
		case <-ctx.Done():
			return
		default:
		}
		status, code, rt, errMsg = w.doCheck(ctx, s)
		if status != "down" {
			break
		}
		if attempt < retries {
			delay := retryInterval
			if delay > 0 {
				select {
				case <-ctx.Done():
					return
				case <-time.After(time.Duration(delay) * time.Second):
				}
			}
		}
	}
	w.persist(s, status, code, rt, errMsg)
}

func (w *Worker) doCheck(ctx context.Context, s *storage.Site) (string, int, float64, string) {
	timeoutSeconds := s.RequestTimeoutSeconds
	if timeoutSeconds <= 0 {
		timeoutSeconds = w.Cfg.GetAlertPolicy().RequestTimeoutSeconds
	}
	timeout := time.Duration(timeoutSeconds) * time.Second
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	// Re-validate the target host on every check cycle, not just at site
	// creation: a hostname that resolved to a public IP when the monitor was
	// created can later be repointed (DNS rebinding, or the domain simply
	// changing hands) at an internal address or the cloud metadata endpoint.
	// Without this, the one-time check in normalizeURL is a TOCTOU gap that a
	// periodic background worker would otherwise walk straight through.
	if host, _ := extractHostPort(s.URL, 0); host != "" &&
		netguard.HostBlocked(host, w.Cfg.Server.AllowLocalhost, w.Cfg.Server.AllowPrivateNetworks) {
		return "down", 0, 0, "target host not allowed"
	}
	switch s.MonitorType {
	case "ping":
		return w.ping(ctx, s.URL, timeout)
	case "dns":
		return w.dns(ctx, s.URL, timeout)
	case "port", "tcp":
		return w.tcp(ctx, s.URL, timeout)
	case "ssl":
		// ssl monitor type is handled by certificate checks; do a TCP connect
		host, port := extractHostPort(s.URL, 443)
		return w.tcpHost(ctx, host, port, timeout)
	default: // http, https
		return w.http(ctx, s, timeout)
	}
}

func (w *Worker) http(ctx context.Context, s *storage.Site, timeout time.Duration) (string, int, float64, string) {
	policy := w.Cfg.GetAlertPolicy()
	start := time.Now()
	// Pinned dial: resolve once through the guard and connect to the vetted
	// IP instead of letting the transport re-resolve (DNS-rebinding TOCTOU).
	allowLocal, allowPrivate := w.Cfg.Server.AllowLocalhost, w.Cfg.Server.AllowPrivateNetworks
	client := &http.Client{
		Timeout: timeout,
		Transport: &http.Transport{
			DialContext: func(dctx context.Context, network, addr string) (net.Conn, error) {
				h, p, err := net.SplitHostPort(addr)
				if err != nil {
					h, p = addr, "80"
				}
				ips, rerr := netguard.ResolveAllowed(dctx, h, allowLocal, allowPrivate)
				if rerr != nil {
					return nil, rerr
				}
				d := net.Dialer{Timeout: timeout}
				return d.DialContext(dctx, network, net.JoinHostPort(ips[0].String(), p))
			},
		},
		// A target allowed at creation/re-check time can still redirect to an
		// internal address or the cloud metadata endpoint; validate every hop,
		// not just the initial URL, so redirects can't be used to route around
		// the SSRF guard.
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			if len(via) >= 10 {
				return fmt.Errorf("stopped after 10 redirects")
			}
			if netguard.HostBlocked(req.URL.Hostname(), w.Cfg.Server.AllowLocalhost, w.Cfg.Server.AllowPrivateNetworks) {
				return fmt.Errorf("redirect target not allowed: %s", req.URL.Hostname())
			}
			return nil
		},
	}
	if !policy.VerifySSL {
		client.Transport = &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
		}
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, s.URL, nil)
	if err != nil {
		return "down", 0, 0, "invalid url"
	}
	// Some targets' WAF/anti-bot layers silently tarpit the default Go
	// User-Agent (hanging until our timeout instead of responding), which
	// looks identical to a real outage. A normal browser-like UA avoids that.
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; UptimeMonitor/1.0; +https://github.com/ajjs1ajjs/Uptime-Monitor)")
	resp, err := client.Do(req)
	rt := float64(time.Since(start).Milliseconds())
	if err != nil {
		return "down", 0, rt, err.Error()[:min(100, len(err.Error()))]
	}
	defer resp.Body.Close()
	rt = float64(time.Since(start).Milliseconds())

	if s.Keyword != nil && *s.Keyword != "" {
		// Bound the body we read so a misbehaving target cannot exhaust memory
		// while we search for the keyword.
		const maxKeywordBody = 512 * 1024
		content, err := io.ReadAll(io.LimitReader(resp.Body, maxKeywordBody))
		if err != nil {
			return "down", resp.StatusCode, rt, "keyword read failed"
		}
		match := false
		kw := *s.Keyword
		if strings.HasPrefix(kw, "regex:") {
			pattern := strings.TrimPrefix(kw, "regex:")
			if re := w.cachedRegexp(pattern); re != nil {
				match = re.Match(content)
			}
		} else {
			match = bytes.Contains(content, []byte(kw))
		}
		if !match {
			return "down", resp.StatusCode, rt, "keyword not found"
		}
	}

	code := resp.StatusCode
	treat4xx := policy.Treat4xxAsDown
	if code >= 200 && code < 400 {
		return "up", code, rt, ""
	}
	if !treat4xx && code < 500 {
		return "up", code, rt, ""
	}
	return "down", code, rt, fmt.Sprintf("HTTP %d", code)
}

func (w *Worker) ping(ctx context.Context, rawURL string, timeout time.Duration) (string, int, float64, string) {
	host, _ := extractHostPort(rawURL, 0)
	if host == "" || strings.HasPrefix(host, "-") {
		return "down", 0, 0, "invalid host"
	}
	// Pin the target like http() and tcpHost() do. doCheck already re-runs
	// HostBlocked every cycle, but that check resolves the name and then ping
	// resolved it a second time - a rebinding race between the two answers,
	// and HostBlocked fails open on a DNS error by design (it is also the
	// creation-time UX check). Resolving once here, fail-closed, and pinging
	// the vetted address closes both gaps and drops a redundant lookup.
	ips, err := netguard.ResolveAllowed(ctx, host, w.Cfg.Server.AllowLocalhost, w.Cfg.Server.AllowPrivateNetworks)
	if err != nil {
		return "down", 0, 0, "target host not allowed"
	}
	target := preferIPv4(ips)
	start := time.Now()
	// Absolute binary path (no PATH hijack); Unix-only by design.
	pingBin, err := exec.LookPath("ping")
	if err != nil {
		for _, p := range []string{"/bin/ping", "/usr/bin/ping", "/sbin/ping"} {
			if _, se := os.Stat(p); se == nil {
				pingBin = p
				err = nil
				break
			}
		}
	}
	if err != nil {
		return "down", 0, 0, "ping unavailable"
	}
	secs := int(timeout.Seconds())
	if secs < 1 {
		secs = 1
	}
	args := []string{"-c", "1", "-W", fmt.Sprintf("%d", secs), "--", target.String()}
	// Bounded by both the check timeout AND the parent ctx: previously this
	// ignored the parent (context.Background()), so a worker shutdown
	// (ctx cancelled) would leave an in-flight ping subprocess running for up
	// to timeout+5s instead of being killed immediately along with everything
	// else WaitInflight is supposed to be waiting on.
	ctx, cancel := context.WithTimeout(ctx, timeout+5*time.Second)
	defer cancel()
	pingCmd := exec.CommandContext(ctx, pingBin, args...)
	err = pingCmd.Run()
	rt := float64(time.Since(start).Milliseconds())
	if err != nil {
		return "down", 0, rt, "ping failed"
	}
	return "up", 0, rt, ""
}

func (w *Worker) dns(ctx context.Context, rawURL string, timeout time.Duration) (string, int, float64, string) {
	host, _ := extractHostPort(rawURL, 0)
	start := time.Now()
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	_, err := net.DefaultResolver.LookupHost(ctx, host)
	rt := float64(time.Since(start).Milliseconds())
	if err != nil {
		return "down", 0, rt, "dns failed"
	}
	return "up", 0, rt, ""
}

func (w *Worker) tcp(ctx context.Context, rawURL string, timeout time.Duration) (string, int, float64, string) {
	host, port := extractHostPort(rawURL, 80)
	return w.tcpHost(ctx, host, port, timeout)
}

func (w *Worker) tcpHost(ctx context.Context, host string, port int, timeout time.Duration) (string, int, float64, string) {
	start := time.Now()
	// Pinned dial through the guard (see http()).
	ips, err := netguard.ResolveAllowed(ctx, host, w.Cfg.Server.AllowLocalhost, w.Cfg.Server.AllowPrivateNetworks)
	if err != nil {
		return "down", 0, 0, "target host not allowed"
	}
	d := net.Dialer{Timeout: timeout}
	conn, err := d.DialContext(ctx, "tcp", net.JoinHostPort(ips[0].String(), fmt.Sprintf("%d", port)))
	rt := float64(time.Since(start).Milliseconds())
	if err != nil {
		return "down", 0, rt, "connection failed"
	}
	conn.Close()
	return "up", 0, rt, ""
}

func extractHostPort(raw string, defPort int) (string, int) {
	host := strings.TrimSpace(raw)
	port := defPort
	if !strings.Contains(host, "://") {
		host = "http://" + host
	}
	if u, err := url.Parse(host); err == nil {
		if u.Hostname() != "" {
			host = u.Hostname()
		}
		if u.Port() != "" {
			fmt.Sscanf(u.Port(), "%d", &port)
		}
	}
	host = strings.Trim(host, "[] ")
	return host, port
}

func (w *Worker) isUnderMaintenance(siteID int64) bool {
	// Maintenance windows change rarely; cache them briefly so we don't re-query
	// the DB for every site on every check cycle.
	w.mu.Lock()
	if time.Since(w.maintCached) > 5*time.Second {
		if windows, err := w.Store.MaintenanceWindows(); err == nil {
			w.maintCache = windows
			w.maintCached = time.Now()
		}
	}
	windows := w.maintCache
	w.mu.Unlock()

	now := time.Now()
	for _, mw := range windows {
		if !mw.IsActive {
			continue
		}
		if mw.SiteID != nil && *mw.SiteID != siteID {
			continue
		}
		if maintenanceActive(mw, now) {
			return true
		}
	}
	return false
}

func maintenanceActive(mw storage.MaintenanceWindow, now time.Time) bool {
	switch mw.RuleType {
	case "one_off":
		if mw.StartTime == nil || mw.EndTime == nil {
			return false
		}
		// The UI sends RFC3339 (new Date(...).toISOString()); older data may use
		// "2006-01-02T15:04". Parsing to absolute instants makes the comparison
		// timezone-correct regardless of the stored format.
		start, err1 := parseFlexTime(*mw.StartTime)
		end, err2 := parseFlexTime(*mw.EndTime)
		if err1 != nil || err2 != nil {
			return false
		}
		return now.After(start) && now.Before(end)
	case "daily":
		if mw.StartHourMinute == nil || mw.DurationMinutes == nil {
			return false
		}
		start, err := time.Parse("15:04", *mw.StartHourMinute)
		if err != nil {
			return false
		}
		startToday := time.Date(now.Year(), now.Month(), now.Day(), start.Hour(), start.Minute(), 0, 0, now.Location())
		end := startToday.Add(time.Duration(*mw.DurationMinutes) * time.Minute)
		return now.After(startToday) && now.Before(end)
	case "weekly":
		if mw.DayOfWeek == nil || mw.StartHourMinute == nil || mw.DurationMinutes == nil {
			return false
		}
		start, err := time.Parse("15:04", *mw.StartHourMinute)
		if err != nil {
			return false
		}
		daysDiff := (int(now.Weekday()) + 6) % 7 // Mon=0
		target := (int(*mw.DayOfWeek) + 6) % 7
		if daysDiff != target {
			return false
		}
		startToday := time.Date(now.Year(), now.Month(), now.Day(), start.Hour(), start.Minute(), 0, 0, now.Location())
		end := startToday.Add(time.Duration(*mw.DurationMinutes) * time.Minute)
		return now.After(startToday) && now.Before(end)
	}
	return false
}

func parseFlexTime(s string) (time.Time, error) {
	if t, err := time.Parse(time.RFC3339, s); err == nil {
		return t, nil
	}
	// Legacy/no-zone values are treated as server-local time, matching how the
	// daily and weekly rules compute their windows against time.Now().
	for _, layout := range []string{"2006-01-02T15:04:05", "2006-01-02T15:04"} {
		if t, err := time.ParseInLocation(layout, s, time.Local); err == nil {
			return t, nil
		}
	}
	return time.Time{}, fmt.Errorf("invalid time %q", s)
}

// persist writes the result, runs the alerting state machine, and broadcasts.
func (w *Worker) persist(s *storage.Site, status string, code int, rt float64, errMsg string) {
	now := storage.Now()
	prev := s.Status
	policy := w.Cfg.GetAlertPolicy()

	var codePtr *int
	if code != 0 {
		c := code
		codePtr = &c
	}
	var rtPtr *float64
	if rt > 0 {
		r := rt
		rtPtr = &r
	}
	var errPtr *string
	if errMsg != "" {
		e := errMsg
		errPtr = &e
	}
	_ = w.Store.AddStatusHistory(s.ID, status, codePtr, rtPtr, errPtr)

	// alerting state machine
	if status == "down" {
		s.FailedAttempts++
		s.SuccessAttempts = 0
		if s.FirstFailureAt == nil {
			f := now
			s.FirstFailureAt = &f
		}
		grace := time.Duration(policy.GracePeriodSeconds) * time.Second
		repeat := time.Duration(policy.StillDownRepeatSeconds) * time.Second
		// Clamp the repeat floor so repeat=0 can't alert-flood every cycle
		// (each due tick would re-fire still_down + fan out to all channels).
		if repeat < 60*time.Second {
			repeat = 60 * time.Second
		}
		first := parseTime(*s.FirstFailureAt)
		prevDown := prev == "down"
		if !w.suppressed(s) {
			if !prevDown {
				// fresh failure: alert immediately when grace == 0, otherwise
				// wait for a later check once the grace period has elapsed
				if grace == 0 || time.Since(first) >= grace {
					w.alert("down", s, code, errMsg, rt)
					s.LastDownAlert = &now
				}
			} else if s.LastDownAlert == nil {
				// still down but the initial "down" alert never fired because
				// the first failure landed inside the grace period: fire it now
				// that the grace period has elapsed
				if time.Since(first) >= grace {
					w.alert("down", s, code, errMsg, rt)
					s.LastDownAlert = &now
				}
			} else if t := parseTime(*s.LastDownAlert); !t.IsZero() && time.Since(t) >= repeat {
				w.alert("still_down", s, code, errMsg, rt)
				s.LastDownAlert = &now
			}
		}
	} else if status == "up" {
		s.FailedAttempts = 0
		s.SuccessAttempts++
		threshold := s.UpSuccessThreshold
		if threshold <= 0 {
			threshold = policy.UpSuccessThreshold
		}
		if threshold <= 0 {
			threshold = 2
		}
		// Only clear the down-tracking fields once the threshold is actually
		// reached: clearing LastDownAlert on every successful check (even
		// before the threshold) erased the signal the "up" alert depends on,
		// so with a threshold above 1 the alert would never fire — the check
		// reloads s fresh from the DB every cycle, so prev alone can't be
		// used as the gate either (it flips to "up" after the first success).
		if s.SuccessAttempts >= threshold {
			if s.LastDownAlert != nil {
				w.alert("up", s, code, "", rt)
			}
			s.FirstFailureAt = nil
			s.LastDownAlert = nil
			s.SilencedUntil = nil
			s.Acknowledged = 0
		}
	}

	_ = w.Store.UpdateSite(s.ID, map[string]any{
		"status": status, "status_code": codePtr, "response_time": rtPtr,
		"error_message": errPtr, "failed_attempts": s.FailedAttempts,
		"success_attempts": s.SuccessAttempts, "last_down_alert": s.LastDownAlert,
		"first_failure_at": s.FirstFailureAt, "silenced_until": s.SilencedUntil,
		"acknowledged": s.Acknowledged,
	})

	if w.WS != nil {
		w.WS.Broadcast(map[string]any{
			"type": "site_status", "site_id": s.ID, "status": status,
			"status_code": code, "response_time": rt, "error_message": errMsg, "checked_at": now,
		})
	}
}

func (w *Worker) suppressed(s *storage.Site) bool {
	if s.Acknowledged == 1 {
		return true
	}
	if s.SilencedUntil != nil {
		if t := parseTime(*s.SilencedUntil); !t.IsZero() && time.Now().Before(t) {
			return true
		}
	}
	return false
}

func (w *Worker) alert(alertType string, s *storage.Site, code int, errMsg string, rt float64) {
	if w.Alert == nil {
		return
	}
	// Async delivery: the blocking fan-out (SMTP 30s, HTTP 20s × channels)
	// previously stalled the check goroutine, holding wg.Wait + active[] and
	// shifting every other site's schedule. Alerts now queue behind a bounded
	// semaphore; when full the alert is counted and dropped (logged) instead
	// of stalling checks. State transitions in persist() already applied.
	if w.AlertSync {
		w.dispatchAlert(alertType, s, code, errMsg, rt)
		return
	}
	select {
	case w.alertSem <- struct{}{}:
	default:
		w.mu.Lock()
		w.dropped++
		n := w.dropped
		w.mu.Unlock()
		slog.Warn("alert queue full, alert dropped", "site_id", s.ID, "type", alertType, "dropped_total", n)
		return
	}
	go func(site storage.Site) {
		defer func() { <-w.alertSem }()
		w.dispatchAlert(alertType, &site, code, errMsg, rt)
	}(*s)
}

// dispatchAlert builds the payload and fans out (runs off the check path).
func (w *Worker) dispatchAlert(alertType string, s *storage.Site, code int, errMsg string, rt float64) {
	var methods []any
	_ = json.Unmarshal([]byte(s.NotifyMethods), &methods)
	checkedAt := storage.Now()
	payload := map[string]any{
		"alert_type": alertType, "site_id": s.ID, "site_name": s.Name, "url": s.URL,
		"status_code": code, "error": errMsg, "response_time": rt, "checked_at": checkedAt,
		"notify_methods": methods,
	}

	// Human-readable structured message. Kept plain for email/sms/slack; the
	// telegram channel renders its own HTML variant (see notify.telegram).
	ts := checkedAt
	if len(ts) > 19 {
		ts = ts[:19]
	}
	rtTxt := ""
	if rt > 0 {
		rtTxt = fmt.Sprintf("%.0f ms", rt)
	}
	codeTxt := ""
	if code > 0 {
		codeTxt = fmt.Sprintf("HTTP %d", code)
	}
	statusTxt := ""
	switch alertType {
	case "down":
		statusTxt = "🔴 МОНІТОР НЕДОСТУПНИЙ"
	case "still_down":
		statusTxt = "🔴 МОНІТОР ДОСІ НЕДОСТУПНИЙ"
	case "up":
		statusTxt = "✅ МОНІТОР ВІДНОВЛЕНО"
	case "ssl":
		statusTxt = "⚠️ SSL ПОПЕРЕДЖЕННЯ"
	}

	var b strings.Builder
	b.WriteString(statusTxt)
	b.WriteString("\n\n")
	b.WriteString("📌 Назва: ")
	b.WriteString(s.Name)
	b.WriteString("\n🌐 URL: ")
	b.WriteString(s.URL)
	if codeTxt != "" {
		b.WriteString("\n🔢 Код: ")
		b.WriteString(codeTxt)
	}
	if rtTxt != "" {
		b.WriteString("\n⚡ Час відповіді: ")
		b.WriteString(rtTxt)
	}
	if errMsg != "" {
		b.WriteString("\n📝 Помилка: ")
		b.WriteString(errMsg)
	}
	b.WriteString("\n🕒 Час: ")
	b.WriteString(ts)
	message := b.String()

	// Telegram renders an HTML variant with bold labels; escape user-supplied
	// fields so they can't break out of the message or the markup.
	htmlEsc := func(v string) string {
		r := strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;")
		return r.Replace(v)
	}
	htmlTitle := ""
	switch alertType {
	case "down":
		htmlTitle = "🔴 <b>Монітор недоступний</b>"
	case "still_down":
		htmlTitle = "🔴 <b>Монітор досі недоступний</b>"
	case "up":
		htmlTitle = "✅ <b>Монітор відновлено</b>"
	case "ssl":
		htmlTitle = "⚠️ <b>SSL попередження</b>"
	}
	var h strings.Builder
	h.WriteString(htmlTitle)
	h.WriteString("\n\n📌 Назва: <b>")
	h.WriteString(htmlEsc(s.Name))
	h.WriteString("</b>\n🌐 URL: <code>")
	h.WriteString(htmlEsc(s.URL))
	h.WriteString("</code>")
	if codeTxt != "" {
		h.WriteString("\n🔢 Код: <b>")
		h.WriteString(htmlEsc(codeTxt))
		h.WriteString("</b>")
	}
	if rtTxt != "" {
		h.WriteString("\n⚡ Час відповіді: <b>")
		h.WriteString(htmlEsc(rtTxt))
		h.WriteString("</b>")
	}
	if errMsg != "" {
		h.WriteString("\n📝 Помилка: <i>")
		h.WriteString(htmlEsc(errMsg))
		h.WriteString("</i>")
	}
	h.WriteString("\n🕒 Час: <code>")
	h.WriteString(htmlEsc(ts))
	h.WriteString("</code>")
	payload["message_html"] = h.String()

	w.Alert.Dispatch(alertType, message, payload)
}

// cachedRegexp compiles once and reuses (ReDoS/CPU guard: patterns are
// owner-controlled; cap length 500 and cache so every 5s check doesn't
// recompile. Go RE2 has no backtracking, but huge classes on 512KiB bodies
// still burn CPU without a cache).
func (w *Worker) cachedRegexp(pattern string) *regexp.Regexp {
	if len(pattern) == 0 || len(pattern) > 500 {
		return nil
	}
	w.regexMu.Lock()
	defer w.regexMu.Unlock()
	if re, ok := w.regexes[pattern]; ok {
		return re
	}
	re, err := regexp.Compile(pattern)
	if err != nil {
		return nil
	}
	if len(w.regexes) > 200 {
		clear(w.regexes)
	}
	w.regexes[pattern] = re
	return re
}

// parseTime reads a timestamp written by storage.Now() (or by an older
// version, or supplied by a client via silenced_until). A zero time means
// unparseable, which every caller treats as "no timestamp".
func parseTime(s string) time.Time {
	t, err := storage.ParseTime(s)
	if err != nil {
		return time.Time{}
	}
	return t
}

// --- SSL certificate checking ---

func (w *Worker) CheckAllCertificates() {
	w.mu.Lock()
	w.lastSSL = time.Now()
	w.mu.Unlock()

	sites, err := w.Store.GetActiveSites()
	if err != nil {
		return
	}
	for i := range sites {
		if sites[i].MonitorType == "ssl" || strings.HasPrefix(strings.ToLower(sites[i].URL), "https://") {
			w.checkCert(&sites[i])
			time.Sleep(time.Second)
		}
	}
}

func (w *Worker) checkCert(s *storage.Site) {
	host, port := extractHostPort(s.URL, 443)
	// F1: the certificate prober dialed without the SSRF guard — an internal
	// host blocked for http/tcp/ping was still reachable every
	// SSLCheckIntervalHours. Guard + pin like the other dial paths.
	if netguard.HostBlocked(host, w.Cfg.Server.AllowLocalhost, w.Cfg.Server.AllowPrivateNetworks) {
		return
	}
	dialCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	ips, err := netguard.ResolveAllowed(dialCtx, host, w.Cfg.Server.AllowLocalhost, w.Cfg.Server.AllowPrivateNetworks)
	if err != nil {
		return
	}
	conn, err := tls.DialWithDialer(&net.Dialer{Timeout: 10 * time.Second}, "tcp",
		net.JoinHostPort(ips[0].String(), fmt.Sprintf("%d", port)),
		&tls.Config{InsecureSkipVerify: true, ServerName: host})
	if err != nil {
		_ = w.Store.SaveSSLCertificate(s.ID, map[string]any{
			"hostname": host, "issuer": "", "subject": "", "start_date": "", "expire_date": "",
			"days_until_expire": 0, "is_valid": false,
		})
		return
	}
	defer conn.Close()
	state := conn.ConnectionState()
	if len(state.PeerCertificates) == 0 {
		return
	}
	cert := state.PeerCertificates[0]
	days := int(time.Until(cert.NotAfter).Hours() / 24)
	valid := days > 0

	_ = w.Store.SaveSSLCertificate(s.ID, map[string]any{
		"hostname": host, "issuer": cert.Issuer.String(), "subject": cert.Subject.String(),
		"start_date":        cert.NotBefore.Format("2006-01-02 15:04:05"),
		"expire_date":       cert.NotAfter.Format("2006-01-02 15:04:05"),
		"days_until_expire": days, "is_valid": valid,
	})

	// threshold alerting
	w.notifySSLThresholds(s, cert, days)
}

func (w *Worker) notifySSLThresholds(s *storage.Site, cert *x509.Certificate, days int) {
	policy := w.Cfg.GetAlertPolicy()
	thresholds := policy.SSLNotificationDays
	if len(thresholds) == 0 {
		return
	}
	// load current thresholds for this site
	row := w.Store.DB.QueryRow(`SELECT ssl_notified_thresholds, last_notified FROM ssl_certificates WHERE site_id = ?`, s.ID)
	var raw sqlNullString2
	var lastNotified string
	_ = row.Scan(&raw, &lastNotified)
	var notified []int
	if raw.Valid && raw.String != "" {
		_ = json.Unmarshal([]byte(raw.String), &notified)
	}
	// The certificate was renewed: the new expiry has more days left than any
	// threshold we have already notified for, so previous notifications no
	// longer apply. Reset the list or the re-notification would be suppressed.
	reset := false
	if len(notified) > 0 && days > maxInt(notified) {
		notified = nil
		reset = true
	}
	cooldown := time.Duration(policy.SSLNotificationCooldown) * time.Second
	if lt := parseTime(lastNotified); !lt.IsZero() && time.Since(lt) < cooldown {
		return
	}
	changed := false
	for _, th := range thresholds {
		if days <= th && !contains(notified, th) {
			notified = append(notified, th)
			changed = true
		}
	}
	if !changed && !reset {
		return
	}
	if changed {
		urgency := "🟡 УВАГА"
		if days <= 0 || days <= 3 {
			urgency = "🔴 КРИТИЧНО"
		} else if days <= 7 {
			urgency = "🟠 ВАЖЛИВО"
		}
		msg := fmt.Sprintf("%s SSL сертифікат для %s закінчується через %d днів (%s)", urgency, s.URL, days, cert.NotAfter.Format("02.01.2006"))
		w.alert("ssl", s, 0, msg, 0)
		_ = w.Store.UpdateSSLThresholds(s.ID, notified, storage.Now())
	} else {
		// Reset-only (BUG-002, documented behavior): the certificate was
		// renewed, so the notified-threshold list is cleared — but the
		// notification cooldown (last_notified) is deliberately NOT advanced.
		// Rationale: last_notified throttles repeat alerts for the SAME
		// expiring certificate; a renewal resets *what* was notified, not
		// *when* we last alerted. Consequence: if the renewed certificate
		// already sits below a threshold (e.g. renewed late, 25 days left
		// with threshold 30), the re-alert fires only after the previous
		// cooldown elapses. Operators who renew certificates should expect
		// the next threshold alert no earlier than
		// last_notified + ssl_notification_cooldown_seconds.
		b, _ := json.Marshal(notified)
		_, _ = w.Store.DB.Exec(`UPDATE ssl_certificates SET ssl_notified_thresholds = ? WHERE site_id = ?`, string(b), s.ID)
	}
}

// preferIPv4 picks an IPv4 address when the guard returned one: iputils ping
// handles both families, but an IPv4 literal is the safer argument on older
// builds. The list is never empty (ResolveAllowed errors instead).
func preferIPv4(ips []net.IP) net.IP {
	for _, ip := range ips {
		if ip.To4() != nil {
			return ip
		}
	}
	return ips[0]
}

func contains(list []int, v int) bool {
	for _, x := range list {
		if x == v {
			return true
		}
	}
	return false
}

func maxInt(list []int) int {
	m := 0
	for _, x := range list {
		if x > m {
			m = x
		}
	}
	return m
}

type sqlNullString2 struct {
	Valid  bool
	String string
}

func (n *sqlNullString2) Scan(v any) error {
	if v == nil {
		n.Valid = false
		n.String = ""
		return nil
	}
	switch x := v.(type) {
	case []byte:
		n.Valid = true
		n.String = string(x)
	case string:
		n.Valid = true
		n.String = x
	default:
		n.Valid = true
		n.String = fmt.Sprintf("%v", x)
	}
	return nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
