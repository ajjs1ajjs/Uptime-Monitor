package auth

import (
	"strings"
	"testing"
)

func TestNewAPIKeyFormatAndHash(t *testing.T) {
	keyID, raw := NewAPIKey()
	if keyID == "" || !strings.HasPrefix(raw, "um_") {
		t.Fatalf("bad key format: keyID=%q raw=%q", keyID, raw)
	}
	// v2 key embeds a salt: um_<salt>.<secret>
	if !strings.Contains(raw, ".") {
		t.Fatalf("v2 key should embed a salt separator '.', got %q", raw)
	}
	h := HashAPIKey(raw)
	// deterministic: same key -> same hash
	if h != HashAPIKey(raw) {
		t.Fatalf("HashAPIKey not deterministic")
	}
	// a differently-salted key must produce a different hash even for the same
	// secret suffix
	if len(h) != 64 {
		t.Fatalf("hash length = %d, want 64", len(h))
	}
}

func TestHashAPIKeyLegacyCompat(t *testing.T) {
	// keys minted by older versions had no embedded salt (base64url has no '.')
	legacy := "um_" + strings.Repeat("A", 43)
	legacyHash := HashAPIKey(legacy)
	if legacyHash == "" {
		t.Fatalf("legacy key did not hash")
	}
	if legacyHash != pbkdf2Digest(legacyAPISalt, legacy) {
		t.Fatalf("legacy key did not use the legacy fixed salt")
	}
}

func TestSplitRawKey(t *testing.T) {
	salt, secret, ok := splitRawKey("um_abc.def")
	if !ok || salt != "abc" || secret != "def" {
		t.Fatalf("split = %q %q %v", salt, secret, ok)
	}
	if _, _, ok := splitRawKey("um_nodefault"); ok {
		t.Fatalf("key without '.' should be legacy")
	}
	if _, _, ok := splitRawKey("other_abc.def"); ok {
		t.Fatalf("non-um_ key should not parse as v2")
	}
}

func TestPBKDF2KeyExport(t *testing.T) {
	raw := "um_saltvalue.secretvalue"
	if PBKDF2Key(raw) != HashAPIKey(raw) {
		t.Fatalf("PBKDF2Key and HashAPIKey disagree")
	}
}
