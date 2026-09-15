package notify

// KMS providers for the master key (enterprise round).
//
// The data-plane key (master.key) can come from:
//   - file (default): existing master.key behaviour, unchanged.
//   - env: 32 raw bytes in UPTIME_MONITOR_KEK_B64 (base64 std/URL-safe,
//     HSM-injected, never on disk).
//   - vault: HashiCorp Vault KV-v2 (VAULT_ADDR, VAULT_TOKEN, VAULT_KEY_NAME,
//     default key name "uptime-monitor-kek", field "kek_b64").
//   - aws: KMS-exported 32B key in UPTIME_MONITOR_KEK_B64 with provenance
//     UPTIME_MONITOR_KMS_KEY_ID (aws kms generate-data-key). Native SigV4
//     KMS API calls are roadmap; without the exported key this fails closed.
//
// Selection: UPTIME_MONITOR_KMS=vault|aws|env|file (default file). Only the
// selected provider is consulted; failures are fail-closed (no silent
// fallback to another provider).

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"
)

// kmsKind reports which provider is configured ("file" when none).
func kmsKind() string {
	if v := strings.ToLower(strings.TrimSpace(os.Getenv("UPTIME_MONITOR_KMS"))); v != "" {
		return v
	}
	if os.Getenv("UPTIME_MONITOR_KEK_B64") != "" {
		return "env"
	}
	if os.Getenv("VAULT_ADDR") != "" {
		return "vault"
	}
	if os.Getenv("UPTIME_MONITOR_KMS_KEY_ID") != "" {
		return "aws"
	}
	return "file"
}

func decodeKEK(b64 string) ([]byte, error) {
	s := strings.TrimSpace(b64)
	if raw, err := base64.URLEncoding.DecodeString(s); err == nil && len(raw) == 32 {
		return raw, nil
	}
	if raw, err := base64.StdEncoding.DecodeString(s); err == nil && len(raw) == 32 {
		return raw, nil
	}
	return nil, fmt.Errorf("KEK must decode to exactly 32 bytes")
}

func kmsEnvKEK() ([]byte, error) {
	b64 := os.Getenv("UPTIME_MONITOR_KEK_B64")
	if b64 == "" {
		return nil, fmt.Errorf("UPTIME_MONITOR_KEK_B64 not set")
	}
	return decodeKEK(b64)
}

func kmsVaultKEK() ([]byte, error) {
	addr := strings.TrimRight(os.Getenv("VAULT_ADDR"), "/")
	token := os.Getenv("VAULT_TOKEN")
	key := os.Getenv("VAULT_KEY_NAME")
	if addr == "" {
		return nil, fmt.Errorf("VAULT_ADDR not set")
	}
	if token == "" {
		return nil, fmt.Errorf("VAULT_TOKEN not set")
	}
	if key == "" {
		key = "uptime-monitor-kek"
	}
	client := &http.Client{Timeout: 10 * time.Second}
	req, err := http.NewRequest(http.MethodGet, addr+"/v1/secret/data/"+key, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Vault-Token", token)
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("vault read: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("vault read failed: %s", resp.Status)
	}
	var v struct {
		Data struct {
			Data map[string]string `json:"data"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&v); err != nil {
		return nil, fmt.Errorf("vault decode: %w", err)
	}
	b64, ok := v.Data.Data["kek_b64"]
	if !ok || b64 == "" {
		return nil, fmt.Errorf("vault: kek_b64 not found at secret/data/%s", key)
	}
	return decodeKEK(b64)
}

func kmsAWSKEK() ([]byte, error) {
	if os.Getenv("UPTIME_MONITOR_KMS_KEY_ID") == "" {
		return nil, fmt.Errorf("UPTIME_MONITOR_KMS_KEY_ID not set")
	}
	// Provenance mode: operators export a data key out-of-band
	// (aws kms generate-data-key --key-id $ID --key-spec AES_256) into
	// UPTIME_MONITOR_KEK_B64. Native SigV4 KMS calls are roadmap.
	if b64 := os.Getenv("UPTIME_MONITOR_KEK_B64"); b64 != "" {
		return decodeKEK(b64)
	}
	return nil, fmt.Errorf("BCK_KMS=aws style flow: set UPTIME_MONITOR_KEK_B64 to a KMS-exported 32B key (native KMS API is roadmap)")
}

// resolveKMSKey returns (key, true, nil) when a non-file provider is
// configured, (nil, false, nil) when file mode applies, or an error that must
// fail closed when the configured provider is unusable.
func resolveKMSKey() ([]byte, bool, error) {
	switch kmsKind() {
	case "env":
		k, err := kmsEnvKEK()
		if err != nil {
			return nil, true, err
		}
		return k, true, nil
	case "vault":
		k, err := kmsVaultKEK()
		if err != nil {
			return nil, true, err
		}
		return k, true, nil
	case "aws":
		k, err := kmsAWSKEK()
		if err != nil {
			return nil, true, err
		}
		return k, true, nil
	default:
		return nil, false, nil
	}
}
