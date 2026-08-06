package notify

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"os"
	"path/filepath"
)

// Master key handling. The key lives in the config directory (NOT the working
// directory) so it survives systemd services that run with CWD="/".
func LoadMasterKey() ([]byte, error) {
	if env := os.Getenv("UPTIME_MONITOR_MASTER_KEY"); env != "" {
		return []byte(env), nil
	}
	dir := configDir()
	path := filepath.Join(dir, "master.key")
	b, err := os.ReadFile(path)
	if err == nil && len(b) >= 32 {
		return b[:32], nil
	}
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	if err := os.WriteFile(path, key, 0o600); err != nil {
		return nil, fmt.Errorf("write master.key: %w", err)
	}
	return key, nil
}

func configDir() string {
	if c := os.Getenv("CONFIG_PATH"); c != "" {
		return filepath.Dir(c)
	}
	if home, err := os.UserHomeDir(); err == nil {
		return filepath.Join(home, "UptimeMonitor")
	}
	return "."
}

const encPrefix = "__ENC__"

func encrypt(key []byte, plaintext string) (string, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err := rand.Read(nonce); err != nil {
		return "", err
	}
	sealed := gcm.Seal(nonce, nonce, []byte(plaintext), nil)
	return encPrefix + base64.URLEncoding.EncodeToString(sealed), nil
}

func decrypt(key []byte, value string) (string, error) {
	if len(value) < len(encPrefix) || value[:len(encPrefix)] != encPrefix {
		return value, nil
	}
	raw, err := base64.URLEncoding.DecodeString(value[len(encPrefix):])
	if err != nil {
		return value, nil
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return value, nil
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return value, nil
	}
	ns := gcm.NonceSize()
	if len(raw) < ns {
		return value, nil
	}
	plain, err := gcm.Open(nil, raw[:ns], raw[ns:], nil)
	if err != nil {
		return value, nil
	}
	return string(plain), nil
}

var secretFields = map[string]string{
	"token":       "token",
	"webhook_url": "webhook_url",
	"password":    "password",
	"auth_token":  "auth_token",
}

// EncryptSecrets walks the settings map and encrypts known secret fields.
func EncryptSecrets(settings map[string]any) map[string]any {
	key, err := LoadMasterKey()
	if err != nil {
		return settings
	}
	return walkSecrets(settings, key, true)
}

// DecryptSecrets walks the settings map and decrypts __ENC__ values.
func DecryptSecrets(settings map[string]any) map[string]any {
	key, err := LoadMasterKey()
	if err != nil {
		return settings
	}
	return walkSecrets(settings, key, false)
}

func walkSecrets(settings map[string]any, key []byte, encryptMode bool) map[string]any {
	out := map[string]any{}
	for k, v := range settings {
		switch val := v.(type) {
		case map[string]any:
			out[k] = walkSecrets(val, key, encryptMode)
		case []any:
			list := make([]any, 0, len(val))
			for _, item := range val {
				if m, ok := item.(map[string]any); ok {
					list = append(list, walkSecrets(m, key, encryptMode))
				} else {
					list = append(list, item)
				}
			}
			out[k] = list
		case string:
			if isSecretField(k) && val != "" {
				if encryptMode {
					if enc, err := encrypt(key, val); err == nil {
						out[k] = enc
						continue
					}
				} else {
					if dec, err := decrypt(key, val); err == nil {
						out[k] = dec
						continue
					}
				}
			}
			out[k] = v
		default:
			out[k] = v
		}
	}
	return out
}

func isSecretField(k string) bool {
	_, ok := secretFields[k]
	return ok
}

// RedactSecrets blanks secret fields (for viewer-role rendering).
func RedactSecrets(settings map[string]any) map[string]any {
	key, _ := LoadMasterKey()
	_ = key
	return walkRedact(settings)
}

func walkRedact(settings map[string]any) map[string]any {
	out := map[string]any{}
	for k, v := range settings {
		switch val := v.(type) {
		case map[string]any:
			out[k] = walkRedact(val)
		case []any:
			list := make([]any, 0, len(val))
			for _, item := range val {
				if m, ok := item.(map[string]any); ok {
					list = append(list, walkRedact(m))
				} else {
					list = append(list, item)
				}
			}
			out[k] = list
		case string:
			if isSecretField(k) && val != "" {
				out[k] = "***REDACTED***"
			} else {
				out[k] = v
			}
		default:
			out[k] = v
		}
	}
	return out
}
