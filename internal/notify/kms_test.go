package notify

import (
	"encoding/base64"
	"os"
	"testing"
)

func TestKMSEnvRoundtrip(t *testing.T) {
	raw := make([]byte, 32)
	for i := range raw {
		raw[i] = byte(i)
	}
	t.Setenv("UPTIME_MONITOR_KMS", "env")
	t.Setenv("UPTIME_MONITOR_KEK_B64", base64.URLEncoding.EncodeToString(raw))
	k, ok, err := resolveKMSKey()
	if err != nil || !ok {
		t.Fatalf("env kms = %v, %v, %v; want key, true, nil", k != nil, ok, err)
	}
	if string(k) != string(raw) {
		t.Fatalf("env kms returned wrong key")
	}
}

func TestKMSFailClosed(t *testing.T) {
	t.Setenv("UPTIME_MONITOR_KMS", "vault")
	os.Unsetenv("VAULT_ADDR")
	os.Unsetenv("VAULT_TOKEN")
	if _, ok, err := resolveKMSKey(); err == nil || !ok {
		t.Fatalf("misconfigured vault must fail closed, got ok=%v err=%v", ok, err)
	}
	t.Setenv("UPTIME_MONITOR_KMS", "bogus-provider")
	if _, ok, err := resolveKMSKey(); ok || err != nil {
		t.Fatalf("unknown provider must fall back to file (ok=false, err=nil), got %v %v", ok, err)
	}
	os.Unsetenv("UPTIME_MONITOR_KMS")
}
