package monitor

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"net/url"
	"os/exec"
	"regexp"
	"runtime"
	"strings"
	"sync"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/config"
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
}

func New(cfg *config.Config, store *storage.Store, ws Broadcaster, alert AlertSink) *Worker {
	return &Worker{
		Cfg: cfg, Store: store, WS: ws, Alert: alert,
		HTTP:     &http.Client{Timeout: 30 * time.Second},
		active:   map[int64]bool{},
		lastSeen: map[int64]time.Time{},
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
		if err := w.CheckDue(lastChecked); err != nil {
			log.Printf("monitor: %v", err)
		}
		w.cleanupIfDue()
		w.sslIfDue()
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

func (w *Worker) sslIfDue() {
	w.mu.Lock()
	interval := time.Duration(w.Cfg.AlertPolicy.SSLCheckIntervalHours) * time.Hour
	if interval <= 0 {
		interval = 6 * time.Hour
	}
	due := time.Since(w.lastSSL) >= interval
	w.mu.Unlock()
	if due {
		w.CheckAllCertificates()
	}
}

// CheckDue runs checks for sites whose interval has elapsed.
func (w *Worker) CheckDue(lastChecked map[int64]time.Time) error {
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
		wg.Add(1)
		go func(site *storage.Site) {
			defer wg.Done()
			defer func() {
				w.mu.Lock()
				delete(w.active, site.ID)
				w.mu.Unlock()
			}()
			w.CheckSite(site)
		}(s)
	}
	wg.Wait()
	return nil
}

// CheckSite runs one full check (with retries) and persists the result.
func (w *Worker) CheckSite(s *storage.Site) {
	policy := w.Cfg.AlertPolicy
	if w.isUnderMaintenance(s.ID) {
		return
	}
	status, code, rt, errMsg := "down", 0, 0.0, ""
	retries := policy.MaxRetries
	if retries < 0 {
		retries = 0
	}
	for attempt := 0; attempt <= retries; attempt++ {
		status, code, rt, errMsg = w.doCheck(s)
		if status != "down" {
			break
		}
		if attempt < retries {
			delay := 30
			if attempt < len(policy.RetryDelays) {
				delay = policy.RetryDelays[attempt]
			} else if len(policy.RetryDelays) > 0 {
				delay = policy.RetryDelays[len(policy.RetryDelays)-1]
			}
			if delay > 0 {
				time.Sleep(time.Duration(delay) * time.Second)
			}
		}
	}
	w.persist(s, status, code, rt, errMsg)
}

func (w *Worker) doCheck(s *storage.Site) (string, int, float64, string) {
	timeout := time.Duration(w.Cfg.AlertPolicy.RequestTimeoutSeconds) * time.Second
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	switch s.MonitorType {
	case "ping":
		return w.ping(s.URL, timeout)
	case "dns":
		return w.dns(s.URL, timeout)
	case "port", "tcp":
		return w.tcp(s.URL, timeout)
	case "ssl":
		// ssl monitor type is handled by certificate checks; do a TCP connect
		host, port := extractHostPort(s.URL, 443)
		return w.tcpHost(host, port, timeout)
	default: // http, https
		return w.http(s, timeout)
	}
}

func (w *Worker) http(s *storage.Site, timeout time.Duration) (string, int, float64, string) {
	start := time.Now()
	client := &http.Client{Timeout: timeout}
	if !w.Cfg.AlertPolicy.VerifySSL {
		client.Transport = &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
		}
	}
	resp, err := client.Get(s.URL)
	rt := float64(time.Since(start).Milliseconds())
	if err != nil {
		return "down", 0, rt, err.Error()[:min(100, len(err.Error()))]
	}
	defer resp.Body.Close()
	rt = float64(time.Since(start).Milliseconds())

	if s.Keyword != nil && *s.Keyword != "" {
		buf := make([]byte, 0, 256*1024)
		tmp := make([]byte, 64*1024)
		for {
			n, err := resp.Body.Read(tmp)
			if n > 0 {
				buf = append(buf, tmp[:n]...)
			}
			if err != nil {
				break
			}
		}
		content := string(buf)
		match := false
		kw := *s.Keyword
		if strings.HasPrefix(kw, "regex:") {
			pattern := strings.TrimPrefix(kw, "regex:")
			if re, err := regexp.Compile(pattern); err == nil {
				match = re.MatchString(content)
			}
		} else {
			match = strings.Contains(content, kw)
		}
		if !match {
			return "down", resp.StatusCode, rt, "keyword not found"
		}
	}

	code := resp.StatusCode
	treat4xx := w.Cfg.AlertPolicy.Treat4xxAsDown
	if code >= 200 && code < 400 {
		return "up", code, rt, ""
	}
	if !treat4xx && code < 500 {
		return "up", code, rt, ""
	}
	return "down", code, rt, fmt.Sprintf("HTTP %d", code)
}

func (w *Worker) ping(rawURL string, timeout time.Duration) (string, int, float64, string) {
	host, _ := extractHostPort(rawURL, 0)
	if host == "" || strings.HasPrefix(host, "-") {
		return "down", 0, 0, "invalid host"
	}
	start := time.Now()
	args := []string{"-n", "1", "-w", fmt.Sprintf("%d", timeout.Milliseconds())}
	if runtime.GOOS != "windows" {
		args = []string{"-c", "1", "-W", fmt.Sprintf("%d", int(timeout.Seconds()))}
	}
	args = append(args, "--", host)
	ctx, cancel := context.WithTimeout(context.Background(), timeout+5*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "ping", args...)
	err := cmd.Run()
	rt := float64(time.Since(start).Milliseconds())
	if err != nil {
		return "down", 0, rt, "ping failed"
	}
	return "up", 0, rt, ""
}

func (w *Worker) dns(rawURL string, timeout time.Duration) (string, int, float64, string) {
	host, _ := extractHostPort(rawURL, 0)
	start := time.Now()
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	_, err := net.DefaultResolver.LookupHost(ctx, host)
	rt := float64(time.Since(start).Milliseconds())
	if err != nil {
		return "down", 0, rt, "dns failed"
	}
	return "up", 0, rt, ""
}

func (w *Worker) tcp(rawURL string, timeout time.Duration) (string, int, float64, string) {
	host, port := extractHostPort(rawURL, 80)
	return w.tcpHost(host, port, timeout)
}

func (w *Worker) tcpHost(host string, port int, timeout time.Duration) (string, int, float64, string) {
	start := time.Now()
	conn, err := net.DialTimeout("tcp", net.JoinHostPort(host, fmt.Sprintf("%d", port)), timeout)
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
	windows, err := w.Store.MaintenanceWindows()
	if err != nil {
		return false
	}
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
		start, err1 := time.Parse("2006-01-02T15:04", *mw.StartTime)
		end, err2 := time.Parse("2006-01-02T15:04", *mw.EndTime)
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

// persist writes the result, runs the alerting state machine, and broadcasts.
func (w *Worker) persist(s *storage.Site, status string, code int, rt float64, errMsg string) {
	now := storage.Now()
	prev := s.Status

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

	// alerting state machine (mirrors Python _process_alerting)
	if status == "down" {
		s.FailedAttempts++
		s.SuccessAttempts = 0
		if s.FirstFailureAt == nil {
			f := now
			s.FirstFailureAt = &f
		}
		grace := time.Duration(w.Cfg.AlertPolicy.GracePeriodSeconds) * time.Second
		repeat := time.Duration(w.Cfg.AlertPolicy.StillDownRepeatSeconds) * time.Second
		first := parseTime(*s.FirstFailureAt)
		prevDown := prev == "down"
		if !w.suppressed(s) {
			if !prevDown && grace == 0 {
				w.alert("down", s, code, errMsg, rt)
				s.LastDownAlert = &now
			} else if !prevDown && time.Since(first) >= grace {
				w.alert("down", s, code, errMsg, rt)
				s.LastDownAlert = &now
			} else if prevDown && s.LastDownAlert != nil {
				if t := parseTime(*s.LastDownAlert); !t.IsZero() && time.Since(t) >= repeat {
					w.alert("still_down", s, code, errMsg, rt)
					s.LastDownAlert = &now
				}
			}
		}
	} else if status == "up" {
		s.FailedAttempts = 0
		s.SuccessAttempts++
		threshold := w.Cfg.AlertPolicy.UpSuccessThreshold
		if threshold <= 0 {
			threshold = 2
		}
		if s.SuccessAttempts >= threshold && (prev == "down" || prev == "slow") {
			w.alert("up", s, code, "", rt)
		}
		s.FirstFailureAt = nil
		s.LastDownAlert = nil
		s.SilencedUntil = nil
		s.Acknowledged = 0
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
	payload := map[string]any{
		"alert_type": alertType, "site_id": s.ID, "site_name": s.Name, "url": s.URL,
		"status_code": code, "error": errMsg, "response_time": rt, "checked_at": storage.Now(),
	}
	var message string
	switch alertType {
	case "down":
		message = fmt.Sprintf("🔴 Monitor DOWN: %s (%s) — code=%d — %s", s.Name, s.URL, code, errMsg)
	case "still_down":
		message = fmt.Sprintf("🔴 Still DOWN: %s (%s) — code=%d — %s", s.Name, s.URL, code, errMsg)
	case "up":
		message = fmt.Sprintf("✅ Monitor UP: %s (%s) restored", s.Name, s.URL)
	case "ssl":
		message = fmt.Sprintf("⚠️ SSL: %s", errMsg)
	}
	w.Alert.Dispatch(alertType, message, payload)
}

func parseTime(s string) time.Time {
	t, err := time.Parse("2006-01-02T15:04:05.999999-07:00", s)
	if err == nil {
		return t
	}
	t, err = time.Parse("2006-01-02T15:04:05", s)
	if err == nil {
		return t
	}
	return time.Time{}
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
	conn, err := tls.DialWithDialer(&net.Dialer{Timeout: 10 * time.Second}, "tcp",
		net.JoinHostPort(host, fmt.Sprintf("%d", port)),
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
	thresholds := w.Cfg.AlertPolicy.SSLNotificationDays
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
	cooldown := time.Duration(w.Cfg.AlertPolicy.SSLNotificationCooldown) * time.Second
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
	if !changed {
		return
	}
	urgency := "🟡 УВАГА"
	if days <= 0 || days <= 3 {
		urgency = "🔴 КРИТИЧНО"
	} else if days <= 7 {
		urgency = "🟠 ВАЖЛИВО"
	}
	msg := fmt.Sprintf("%s SSL сертифікат для %s закінчується через %d днів (%s)", urgency, s.URL, days, cert.NotAfter.Format("02.01.2006"))
	w.alert("ssl", s, 0, msg, 0)
	_ = w.Store.UpdateSSLThresholds(s.ID, notified, storage.Now())
}

func contains(list []int, v int) bool {
	for _, x := range list {
		if x == v {
			return true
		}
	}
	return false
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
