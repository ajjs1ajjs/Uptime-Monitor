package main

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/ajjs1ajjs/Uptime-Monitor/internal/api"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/auth"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/config"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/monitor"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/notify"
	"github.com/ajjs1ajjs/Uptime-Monitor/internal/storage"
)

const Version = "3.0.11"

func main() {
	if len(os.Args) < 2 {
		printUsage()
		return
	}
	switch os.Args[1] {
	case "--version", "-v":
		fmt.Println(Version)
	case "server":
		runServer(os.Args[2:])
	case "reset-admin":
		runResetAdmin(os.Args[2:])
	case "has-admin":
		runHasAdmin(os.Args[2:])
	default:
		printUsage()
	}
}

func printUsage() {
	fmt.Println("Uptime Monitor " + Version)
	fmt.Println("Usage:")
	fmt.Println("  uptime-monitor server [--host HOST] [--port PORT] [--config PATH]")
	fmt.Println("  uptime-monitor reset-admin [--config PATH] [--db PATH]")
	fmt.Println("  uptime-monitor has-admin [--config PATH] [--db PATH]")
	fmt.Println("  uptime-monitor --version")
}

func parseFlags(args []string) (host string, port int, cfgPath, dbPath string) {
	fs := flag.NewFlagSet("server", flag.ContinueOnError)
	fs.StringVar(&host, "host", "", "")
	fs.IntVar(&port, "port", 0, "")
	fs.StringVar(&cfgPath, "config", "", "")
	fs.StringVar(&dbPath, "db", "", "")
	_ = fs.Parse(args)
	return
}

func runServer(args []string) {
	host, port, cfgPath, dbPath := parseFlags(args)
	cfg, err := config.Load(cfgPath)
	if err != nil {
		log.Fatalf("config: %v", err)
	}
	if host != "" {
		cfg.Server.Host = host
	}
	if port != 0 {
		cfg.Server.Port = port
	}
	if dbPath == "" {
		dbPath = cfg.DBPath()
	}

	db, abs, err := storage.Open(dbPath)
	if err != nil {
		log.Fatalf("open db: %v", err)
	}
	store := storage.NewStore(db, abs)

	ensureAdmin(store, cfg, abs)

	// make sure notify_config has a row
	if raw, _ := store.LoadNotifyConfig(); raw == "" {
		_ = store.SaveNotifyConfig(`{}`)
	}

	ws := api.NewWSManager()
	notifySvc := notify.New(store)
	worker := monitor.New(cfg, store, ws, notifySvc)

	app := &api.App{
		Cfg: cfg, Store: store, Worker: worker, Notify: notifySvc, WS: ws,
		Set: api.NewTemplateSet(), Start: time.Now(), Version: Version,
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	worker.Run(ctx)

	// dual-stack bind: ":port" listens on IPv4+IPv6 (a lesson from Monitoring).
	bindHost := cfg.Server.Host
	var addr string
	if bindHost == "" || bindHost == "0.0.0.0" || bindHost == "auto" {
		addr = fmt.Sprintf(":%d", cfg.Server.Port)
	} else {
		addr = fmt.Sprintf("%s:%d", bindHost, cfg.Server.Port)
	}
	srv := &http.Server{
		Addr:         addr,
		Handler:      app.Handler(),
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 60 * time.Second,
	}

	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
		<-sig
		log.Println("shutting down...")
		cancel()
		ctx2, cancel2 := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel2()
		_ = srv.Shutdown(ctx2)
	}()

	log.Printf("Uptime Monitor %s listening on http://%s", Version, addr)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("server: %v", err)
	}
}

// --- admin user management (same principle as the Monitoring port) ---

func adminUsername(cfg *config.Config) string {
	if u := os.Getenv("UPTIME_MONITOR_ADMIN_USERNAME"); u != "" {
		return u
	}
	return "admin"
}

func adminPasswordEnv() (string, bool) {
	pw := os.Getenv("UPTIME_MONITOR_ADMIN_PASSWORD")
	if pw == "" {
		pw = os.Getenv("PYMON_ADMIN_PASSWORD")
	}
	return pw, pw != ""
}

func createAdmin(store *storage.Store, cfg *config.Config, dbDir, username string) {
	pw, _ := adminPasswordEnv()
	if pw == "" {
		pw = randomToken(18)
	}
	hash, err := auth.HashPassword(pw)
	if err != nil {
		log.Fatalf("hash password: %v", err)
	}
	if _, err := store.CreateUser(username, hash, "admin"); err != nil {
		log.Fatalf("create admin: %v", err)
	}
	// require password change on first login (consistent with the Monitoring port)
	if u, _ := store.GetUserByUsername(username); u != nil {
		_ = store.UpdateUser(u.ID, map[string]any{"must_change_password": 1})
	}
	fmt.Printf("Admin user '%s' created.\n", username)
	fmt.Printf("Generated password: %s\n", pw)
	if dbDir != "" {
		pwFile := filepath.Join(dbDir, "admin_password.txt")
		if err := os.WriteFile(pwFile, []byte(pw+"\n"), 0o600); err == nil {
			fmt.Printf("One-time password saved to %s (delete it after login).\n", pwFile)
		}
	}
}

func ensureAdmin(store *storage.Store, cfg *config.Config, dbDir string) {
	username := adminUsername(cfg)
	u, err := store.GetUserByUsername(username)
	if err == nil && u != nil {
		return
	}
	createAdmin(store, cfg, dbDir, username)
}

func resetAdmin(store *storage.Store, cfg *config.Config) {
	username := adminUsername(cfg)
	if u, err := store.GetUserByUsername(username); err == nil && u != nil {
		_ = store.DeleteUser(u.ID)
		_ = store.DeleteUserSessions(u.ID)
	}
	createAdmin(store, cfg, filepath.Dir(store.DBPath), username)
}

func runResetAdmin(args []string) {
	_, _, cfgPath, dbPath := parseFlags(args)
	cfg, err := config.Load(cfgPath)
	if err != nil {
		log.Fatalf("config: %v", err)
	}
	if dbPath == "" {
		dbPath = cfg.DBPath()
	}
	db, abs, err := storage.Open(dbPath)
	if err != nil {
		log.Fatalf("open db: %v", err)
	}
	store := storage.NewStore(db, abs)
	resetAdmin(store, cfg)
}

func runHasAdmin(args []string) {
	_, _, cfgPath, dbPath := parseFlags(args)
	cfg, err := config.Load(cfgPath)
	if err != nil {
		fmt.Println("no")
		return
	}
	if dbPath == "" {
		dbPath = cfg.DBPath()
	}
	db, abs, err := storage.Open(dbPath)
	if err != nil {
		fmt.Println("no")
		return
	}
	defer db.Close()
	store := storage.NewStore(db, abs)
	u, err := store.GetUserByUsername(adminUsername(cfg))
	if err == nil && u != nil {
		fmt.Println("yes")
		return
	}
	fmt.Println("no")
}

func randomToken(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("tmp%d", time.Now().UnixNano())
	}
	return base64.URLEncoding.EncodeToString(b)
}

var _ = strings.TrimSpace
