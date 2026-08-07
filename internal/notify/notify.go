package notify

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/smtp"
	"net/url"
	"strings"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"
)

// Service dispatches alerts over configured channels.
type Service struct {
	Store *storage.Store
	HTTP  *http.Client
}

func New(store *storage.Store) *Service {
	return &Service{
		Store: store,
		HTTP:  &http.Client{Timeout: 20 * time.Second},
	}
}

// LoadSettings returns the decrypted notify settings map.
func (s *Service) LoadSettings() map[string]any {
	raw, err := s.Store.LoadNotifyConfig()
	if err != nil || raw == "" {
		return map[string]any{}
	}
	m := map[string]any{}
	if json.Unmarshal([]byte(raw), &m) != nil {
		return map[string]any{}
	}
	return DecryptSecrets(m)
}

// channelsFor returns the enabled channels for the given notify_methods list.
// notify_methods is either ["telegram"] or [{"method":"telegram","channels":["id"]}].
func channelsFor(methods []any) (enabled map[string]bool, specific map[string][]string) {
	enabled = map[string]bool{}
	specific = map[string][]string{}
	for _, m := range methods {
		switch v := m.(type) {
		case string:
			enabled[v] = true
		case map[string]any:
			if method, ok := v["method"].(string); ok {
				enabled[method] = true
				if chs, ok := v["channels"].([]any); ok {
					for _, c := range chs {
						if id, ok := c.(string); ok {
							specific[method] = append(specific[method], id)
						}
					}
				}
			}
		}
	}
	return enabled, specific
}

func (s *Service) Dispatch(alertType, message string, alert map[string]any) {
	settings := s.LoadSettings()
	siteID := int64(0)
	switch v := alert["site_id"].(type) {
	case float64:
		siteID = int64(v)
	case int64:
		siteID = v
	case int:
		siteID = int64(v)
	}
	siteName, _ := alert["site_name"].(string)

	methods, _ := alert["notify_methods"].([]any)
	if len(methods) == 0 {
		// alert triggered from worker has no methods; fall back to site's methods
		if sid, ok := alert["site_id"]; ok {
			methods = s.siteMethods(siteID)
			_ = sid
		}
	}
	enabled, specific := channelsFor(methods)

	s.send(settings, "telegram", enabled, specific, func(cfg map[string]any) bool {
		text := message
		if h, ok := alert["message_html"].(string); ok && h != "" {
			text = h
		}
		return s.telegram(text, cfg)
	}, siteID, siteName, "telegram", message)
	s.send(settings, "discord", enabled, specific, func(cfg map[string]any) bool {
		return s.discord(alertType, message, cfg)
	}, siteID, siteName, "discord", message)
	s.send(settings, "teams", enabled, specific, func(cfg map[string]any) bool {
		return s.teams(message, cfg)
	}, siteID, siteName, "teams", message)
	s.send(settings, "slack", enabled, specific, func(cfg map[string]any) bool {
		return s.slack(message, cfg)
	}, siteID, siteName, "slack", message)
	s.send(settings, "email", enabled, specific, func(cfg map[string]any) bool {
		return s.email(alertType, siteName, message, cfg)
	}, siteID, siteName, "email", message)
	s.send(settings, "sms", enabled, specific, func(cfg map[string]any) bool {
		return s.sms(message, cfg)
	}, siteID, siteName, "sms", message)
	s.send(settings, "webhook", enabled, specific, func(cfg map[string]any) bool {
		return s.webhook(alert, cfg)
	}, siteID, siteName, "webhook", message)
	s.send(settings, "pushover", enabled, specific, func(cfg map[string]any) bool {
		return s.pushover(alertType, message, cfg)
	}, siteID, siteName, "pushover", message)
	s.send(settings, "gotify", enabled, specific, func(cfg map[string]any) bool {
		return s.gotify(message, cfg)
	}, siteID, siteName, "gotify", message)
	s.send(settings, "ntfy", enabled, specific, func(cfg map[string]any) bool {
		return s.ntfy(message, cfg)
	}, siteID, siteName, "ntfy", message)
}

func (s *Service) siteMethods(siteID int64) []any {
	site, err := s.Store.GetSite(siteID)
	if err != nil || site == nil {
		return nil
	}
	var methods []any
	if json.Unmarshal([]byte(site.NotifyMethods), &methods) != nil {
		return nil
	}
	return methods
}

func (s *Service) send(settings map[string]any, method string, enabled map[string]bool, specific map[string][]string, fn func(map[string]any) bool, siteID int64, siteName, label, message string) {
	if !enabled[method] {
		return
	}
	section, ok := settings[method].(map[string]any)
	if !ok {
		return
	}
	if on, ok := section["enabled"].(bool); ok && !on {
		return
	}
	allowed := specific[method]
	channels, _ := section["channels"].([]any)
	sent := false
	for _, ch := range channels {
		cfg, ok := ch.(map[string]any)
		if !ok {
			continue
		}
		if len(allowed) > 0 {
			id, _ := cfg["id"].(string)
			if !containsStr(allowed, id) {
				continue
			}
		}
		okSend := fn(cfg)
		if okSend {
			sent = true
		}
		status := "failed"
		if okSend {
			status = "sent"
		}
		_ = s.Store.LogNotification(siteID, siteName, label, status, messagePreview(message))
	}
	if !sent && len(channels) == 0 {
		_ = s.Store.LogNotification(siteID, siteName, label, "failed", "no channels configured")
	}
}

func messagePreview(m string) string {
	if len(m) > 200 {
		return m[:200]
	}
	return m
}

func containsStr(list []string, v string) bool {
	for _, x := range list {
		if x == v {
			return true
		}
	}
	return false
}

func (s *Service) postJSON(url string, payload any) bool {
	b, err := json.Marshal(payload)
	if err != nil {
		return false
	}
	resp, err := s.HTTP.Post(url, "application/json", bytes.NewReader(b))
	if err != nil {
		log.Printf("notify: %v", err)
		return false
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)
	return resp.StatusCode >= 200 && resp.StatusCode < 300
}

func (s *Service) postForm(url string, data url.Values) bool {
	resp, err := s.HTTP.PostForm(url, data)
	if err != nil {
		log.Printf("notify: %v", err)
		return false
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)
	return resp.StatusCode >= 200 && resp.StatusCode < 300
}

func (s *Service) telegram(message string, cfg map[string]any) bool {
	token, _ := cfg["token"].(string)
	chatID, _ := cfg["chat_id"].(string)
	if token == "" || chatID == "" {
		return false
	}
	payload := map[string]any{"chat_id": chatID, "text": message, "parse_mode": "HTML"}
	if t, ok := cfg["message_thread_id"].(string); ok && t != "" {
		payload["message_thread_id"] = t
	}
	return s.postJSON(fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", token), payload)
}

func (s *Service) discord(alertType, message string, cfg map[string]any) bool {
	webhook, _ := cfg["webhook_url"].(string)
	if webhook == "" {
		return false
	}
	color := 16711680 // red
	if alertType == "up" {
		color = 65280 // green
	}
	return s.postJSON(webhook, map[string]any{
		"embeds": []map[string]any{{
			"title": "Uptime Monitor", "description": message, "color": color,
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		}},
	})
}

func (s *Service) teams(message string, cfg map[string]any) bool {
	webhook, _ := cfg["webhook_url"].(string)
	if webhook == "" {
		return false
	}
	return s.postJSON(webhook, map[string]any{
		"@type": "MessageCard", "@context": "https://schema.org/extensions",
		"themeColor": "FF0000", "title": "Uptime Monitor Alert",
		"text": message,
	})
}

func (s *Service) slack(message string, cfg map[string]any) bool {
	webhook, _ := cfg["webhook_url"].(string)
	if webhook == "" {
		return false
	}
	return s.postJSON(webhook, map[string]any{"text": message})
}

func (s *Service) email(alertType, siteName, message string, cfg map[string]any) bool {
	server, _ := cfg["smtp_server"].(string)
	to, _ := cfg["to_email"].(string)
	if server == "" || to == "" {
		return false
	}
	port := int(num(cfg["smtp_port"], 587))
	user, _ := cfg["username"].(string)
	pass, _ := cfg["password"].(string)

	addr := net.JoinHostPort(server, fmt.Sprintf("%d", port))
	var conn net.Conn
	var err error
	if port == 465 {
		// implicit TLS (SMTPS)
		conn, err = tls.Dial("tcp", addr, &tls.Config{ServerName: server})
	} else {
		// plain connection, then STARTTLS (587) or unencrypted (25)
		conn, err = net.DialTimeout("tcp", addr, 8*time.Second)
	}
	if err != nil {
		log.Printf("notify: email dial %s: %v", addr, err)
		return false
	}
	defer conn.Close()
	// bound the whole SMTP conversation, not just the dial
	_ = conn.SetDeadline(time.Now().Add(30 * time.Second))
	client, err := smtp.NewClient(conn, server)
	if err != nil {
		log.Printf("notify: email newclient %s: %v", addr, err)
		return false
	}
	defer client.Close()
	if port == 587 {
		if ok, _ := client.Extension("STARTTLS"); ok {
			if err := client.StartTLS(&tls.Config{ServerName: server}); err != nil {
				log.Printf("notify: email starttls %s: %v", addr, err)
				return false
			}
		}
	}
	if pass != "" {
		if err := authSMTP(client, server, user, pass); err != nil {
			log.Printf("notify: email auth %s: %v", addr, err)
			return false
		}
	}
	if err := client.Mail(user); err != nil {
		log.Printf("notify: email mail %s: %v", addr, err)
		return false
	}
	if err := client.Rcpt(to); err != nil {
		log.Printf("notify: email rcpt %s: %v", addr, err)
		return false
	}
	w, err := client.Data()
	if err != nil {
		log.Printf("notify: email data %s: %v", addr, err)
		return false
	}
	label := map[string]string{
		"down": "DOWN", "still_down": "DOWN", "up": "UP", "ssl": "SSL", "test": "TEST",
	}[alertType]
	subject := fmt.Sprintf("Uptime Monitor [%s]: %s", label, siteName)
	if siteName == "" {
		subject = fmt.Sprintf("Uptime Monitor [%s]", label)
	}
	body := fmt.Sprintf("From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n%s",
		user, to, subject, message)
	w.Write([]byte(body))
	w.Close()
	return client.Quit() == nil
}

func (s *Service) sms(message string, cfg map[string]any) bool {
	sid, _ := cfg["account_sid"].(string)
	auth, _ := cfg["auth_token"].(string)
	from, _ := cfg["from_number"].(string)
	to, _ := cfg["to_number"].(string)
	if sid == "" || to == "" {
		return false
	}
	body := url.Values{}
	body.Set("From", from)
	body.Set("To", to)
	body.Set("Body", truncateBytes(message, 1600))
	req, err := http.NewRequest("POST", fmt.Sprintf("https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json", sid), strings.NewReader(body.Encode()))
	if err != nil {
		return false
	}
	req.SetBasicAuth(sid, auth)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := s.HTTP.Do(req)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)
	return resp.StatusCode >= 200 && resp.StatusCode < 300
}

func (s *Service) webhook(alert map[string]any, cfg map[string]any) bool {
	webhook, _ := cfg["webhook_url"].(string)
	if webhook == "" {
		return false
	}
	payload := alert
	if payload == nil {
		payload = map[string]any{}
	}
	return s.postJSON(webhook, payload)
}

func (s *Service) pushover(alertType, message string, cfg map[string]any) bool {
	token, _ := cfg["token"].(string)
	user, _ := cfg["user_key"].(string)
	if token == "" || user == "" {
		return false
	}
	data := url.Values{}
	data.Set("token", token)
	data.Set("user", user)
	data.Set("title", "Uptime Monitor: "+alertType)
	data.Set("message", message)
	data.Set("priority", "1")
	return s.postForm("https://api.pushover.net/1/messages.json", data)
}

func (s *Service) gotify(message string, cfg map[string]any) bool {
	server, _ := cfg["server_url"].(string)
	token, _ := cfg["token"].(string)
	if server == "" || token == "" {
		return false
	}
	req, err := http.NewRequest("POST", strings.TrimRight(server, "/")+"/message", bytes.NewReader([]byte(`{"title":"Uptime Monitor","message":`+quote(message)+`,"priority":5}`)))
	if err != nil {
		return false
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Gotify-Key", token)
	resp, err := s.HTTP.Do(req)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)
	return resp.StatusCode >= 200 && resp.StatusCode < 300
}

func (s *Service) ntfy(message string, cfg map[string]any) bool {
	topic, _ := cfg["topic"].(string)
	server, _ := cfg["server_url"].(string)
	if server == "" {
		server = "https://ntfy.sh"
	}
	if topic == "" {
		return false
	}
	req, err := http.NewRequest("POST", strings.TrimRight(server, "/")+"/"+topic, bytes.NewReader([]byte(message)))
	if err != nil {
		return false
	}
	req.Header.Set("Title", "Uptime Monitor")
	if token, ok := cfg["token"].(string); ok && token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	resp, err := s.HTTP.Do(req)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)
	return resp.StatusCode >= 200 && resp.StatusCode < 300
}

func quote(s string) string {
	b, _ := json.Marshal(s)
	return string(b)
}

func num(v any, def int) int {
	switch n := v.(type) {
	case float64:
		return int(n)
	case int:
		return n
	case string:
		var x int
		if _, err := fmt.Sscanf(n, "%d", &x); err == nil {
			return x
		}
	}
	return def
}

func truncateBytes(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

// authSMTP picks an AUTH mechanism the server actually advertises. Exchange
// often only supports LOGIN/NTLM, so PLAIN (the only one Go's smtp.PlainAuth
// can do) would time out. Prefer PLAIN when available, otherwise fall back to
// LOGIN.
func authSMTP(c *smtp.Client, server, user, pass string) error {
	if ok, mechs := c.Extension("AUTH"); ok {
		if strings.Contains(strings.ToUpper(mechs), "LOGIN") {
			return c.Auth(&loginAuth{user: user, password: pass})
		}
	}
	return c.Auth(smtp.PlainAuth("", user, pass, server))
}

// loginAuth implements SMTP AUTH LOGIN (base64 user/password exchange).
type loginAuth struct {
	user, password string
}

func (a *loginAuth) Start(_ *smtp.ServerInfo) (string, []byte, error) {
	return "LOGIN", nil, nil
}

func (a *loginAuth) Next(fromServer []byte, more bool) ([]byte, error) {
	if !more {
		return nil, nil
	}
	switch strings.ToLower(strings.TrimSpace(string(fromServer))) {
	case "username:":
		return []byte(a.user), nil
	case "password:":
		return []byte(a.password), nil
	default:
		return nil, fmt.Errorf("unexpected server challenge: %q", string(fromServer))
	}
}
