package main

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
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

const Version = "3.0.17"

// fatalf logs an error and exits, mirroring the old log.Fatalf behaviour.
func fatalf(format string, args ...any) {
	slog.Error(fmt.Sprintf(format, args...))
	os.Exit(1)
}

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
	case "restore":
		runRestore(os.Args[2:])
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
	fmt.Println("  uptime-monitor restore --backup FILENAME [--config PATH] [--db PATH]")
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
		fatalf("config: %v", err)
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
		fatalf("open db: %v", err)
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
		slog.Info("shutting down...")
		cancel()
		// Give in-flight monitor checks a short window to persist their result.
		worker.WaitInflight(3 * time.Second)
		ctx2, cancel2 := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel2()
		_ = srv.Shutdown(ctx2)
	}()

	slog.Info("listening", "version", Version, "addr", addr)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		fatalf("server: %v", err)
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

func createAdmin(store *storage.Store, cfg *config.Config, username string) {
	pw, _ := adminPasswordEnv()
	if pw == "" {
		pw = randomToken(18)
	}
	hash, err := auth.HashPassword(pw)
	if err != nil {
		fatalf("hash password: %v", err)
	}
	if _, err := store.CreateUser(username, hash, "admin"); err != nil {
		fatalf("create admin: %v", err)
	}
	// Require a password change on first login by default (consistent with the
	// Monitoring port). Set UPTIME_MONITOR_NO_FORCE_PASSWORD_CHANGE=1 (e.g. in
	// reset-admin) to log straight in with the given password instead.
	if os.Getenv("UPTIME_MONITOR_NO_FORCE_PASSWORD_CHANGE") != "1" {
		if u, _ := store.GetUserByUsername(username); u != nil {
			_ = store.UpdateUser(u.ID, map[string]any{"must_change_password": 1})
		}
	}
	fmt.Printf("Admin user '%s' created.\n", username)
	fmt.Printf("Generated password: %s\n", pw)
	if os.Getenv("UPTIME_MONITOR_NO_FORCE_PASSWORD_CHANGE") != "1" {
		fmt.Println("You will be asked to change this password at first login.")
	}
}

func ensureAdmin(store *storage.Store, cfg *config.Config, dbDir string) {
	username := adminUsername(cfg)
	u, err := store.GetUserByUsername(username)
	if err == nil && u != nil {
		return
	}
	createAdmin(store, cfg, username)
}

func resetAdmin(store *storage.Store, cfg *config.Config) {
	username := adminUsername(cfg)
	if u, err := store.GetUserByUsername(username); err == nil && u != nil {
		_ = store.DeleteUser(u.ID)
		_ = store.DeleteUserSessions(u.ID)
	}
	createAdmin(store, cfg, username)
}

func runResetAdmin(args []string) {
	_, _, cfgPath, dbPath := parseFlags(args)
	cfg, err := config.Load(cfgPath)
	if err != nil {
		fatalf("config: %v", err)
	}
	if dbPath == "" {
		dbPath = cfg.DBPath()
	}
	db, abs, err := storage.Open(dbPath)
	if err != nil {
		fatalf("open db: %v", err)
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

// runRestore replaces the database file from a backup. It must run while the
// server is stopped: restoring at runtime would close the live DB underneath
// concurrent API/monitor queries.
func runRestore(args []string) {
	fs := flag.NewFlagSet("restore", flag.ContinueOnError)
	var backup, cfgPath, dbPath string
	fs.StringVar(&backup, "backup", "", "")
	fs.StringVar(&cfgPath, "config", "", "")
	fs.StringVar(&dbPath, "db", "", "")
	_ = fs.Parse(args)
	if backup == "" {
		fatalf("restore: --backup <filename> is required")
	}
	cfg, err := config.Load(cfgPath)
	if err != nil {
		fatalf("config: %v", err)
	}
	if dbPath == "" {
		dbPath = cfg.DBPath()
	}
	db, abs, err := storage.Open(dbPath)
	if err != nil {
		fatalf("open db: %v", err)
	}
	defer db.Close()
	store := storage.NewStore(db, abs)
	restored, err := store.RestoreBackupFile(cfg.BackupDir(), backup)
	if err != nil {
		fatalf("restore: %v", err)
	}
	if restored == "" {
		fatalf("restore: backup %q not found in %s", backup, cfg.BackupDir())
	}
	fmt.Printf("Restored %s -> %s\n", backup, restored)
}

func randomToken(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("tmp%d", time.Now().UnixNano())
	}
	return base64.URLEncoding.EncodeToString(b)
}

var _ = strings.TrimSpace
