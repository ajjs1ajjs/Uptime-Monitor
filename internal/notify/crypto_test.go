package notify

import (
	"encoding/base64"
	"os"
	"path/filepath"
	"testing"

	"github.com/fernet/fernet-go"
)

// TestLegacyFernetDecrypt verifies that tokens written by the old Python
// backend (Fernet with the master.key) can be decrypted by the Go binary.
func TestLegacyFernetDecrypt(t *testing.T) {
	dir := t.TempDir()
	key := make([]byte, 32)
	// deterministic key for the test
	copy(key, "0123456789abcdef0123456789abcdef")
	ks, err := fernet.DecodeKeys(base64.URLEncoding.EncodeToString(key))
	if err != nil {
		t.Fatalf("decode key: %v", err)
	}
	raw, err := fernet.EncryptAndSign([]byte("secret-token-123"), ks[0])
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	fernetKey := base64.URLEncoding.EncodeToString(key) // 44-char Fernet key
	if err := os.WriteFile(filepath.Join(dir, "master.key"), []byte(fernetKey), 0o600); err != nil {
		t.Fatalf("write key: %v", err)
	}
	t.Setenv("CONFIG_PATH", filepath.Join(dir, "config.json"))

	stored := "__ENC__" + string(raw)
	out, err := decrypt(loadKey32(t), stored)
	if err != nil {
		t.Fatalf("decrypt: %v", err)
	}
	if out != "secret-token-123" {
		t.Fatalf("decrypted = %q, want secret-token-123", out)
	}
}

// TestDecryptNonSecret returns value unchanged when not a secret token.
func TestDecryptNonSecret(t *testing.T) {
	out, err := decrypt(nil, "plain-value")
	if err != nil {
		t.Fatalf("decrypt: %v", err)
	}
	if out != "plain-value" {
		t.Fatalf("out = %q", out)
	}
}

// loadKey32 reads the master.key written by the test (base64 Fernet key) and
// returns its first 32 bytes, matching LoadMasterKey's behaviour.
func loadKey32(t *testing.T) []byte {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(configDir(), "master.key"))
	if err != nil {
		t.Fatalf("read key: %v", err)
	}
	return b[:32]
}
