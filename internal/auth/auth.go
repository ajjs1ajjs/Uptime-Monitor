package auth

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"strings"
	"time"

	"golang.org/x/crypto/bcrypt"
	"golang.org/x/crypto/pbkdf2"
)

// legacyAPISalt was the single fixed salt used by earlier versions. New keys
// carry a per-key random salt embedded in the key, but old keys still need to
// verify, so we keep this fallback.
const legacyAPISalt = "uptime-monitor-api-key-salt"

type User struct {
	ID                 int64  `json:"id"`
	Username           string `json:"username"`
	PasswordHash       string `json:"-"`
	Role               string `json:"role"`
	MustChangePassword bool   `json:"must_change_password"`
	CreatedAt          string `json:"created_at"`
	LastLogin          string `json:"last_login"`
}

func HashPassword(pw string) (string, error) {
	b, err := bcrypt.GenerateFromPassword([]byte(pw), bcrypt.DefaultCost)
	return string(b), err
}

func VerifyPassword(hash, pw string) bool {
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(pw)) == nil
}

// HashAPIKey derives a deterministic PBKDF2-HMAC-SHA256 digest so lookups work
// by hashing the presented key. New keys embed a random per-key salt in the
// key itself ("um_<salt>.<secret>"), so identical secrets never produce the
// same hash and rainbow-table precomputation is not possible even if the whole
// hash database leaks. Keys minted by older versions (no embedded salt) still
// verify via the legacy fixed salt.
func HashAPIKey(rawKey string) string {
	if salt, secret, ok := splitRawKey(rawKey); ok {
		return pbkdf2Digest(salt, secret)
	}
	return pbkdf2Digest(legacyAPISalt, rawKey)
}

func pbkdf2Digest(salt, secret string) string {
	dk := pbkdf2.Key([]byte(secret), []byte(salt), 100000, 32, sha256.New)
	return hex.EncodeToString(dk)
}

// splitRawKey splits a v2 key "um_<salt>.<secret>" into its parts.
func splitRawKey(raw string) (salt, secret string, ok bool) {
	const prefix = "um_"
	if !strings.HasPrefix(raw, prefix) {
		return "", "", false
	}
	rest := raw[len(prefix):]
	i := strings.IndexByte(rest, '.')
	if i <= 0 || i == len(rest)-1 {
		return "", "", false
	}
	return rest[:i], rest[i+1:], true
}

func NewAPIKey() (keyID, raw string) {
	salt := randomToken(16)
	secret := randomToken(32)
	raw = "um_" + salt + "." + secret
	return randomToken(8), raw
}

func randomToken(n int) string {
	b := make([]byte, n)
	_, _ = rand.Read(b)
	return base64.URLEncoding.EncodeToString(b)
}

func SessionID() string {
	return randomToken(32)
}

// RandomToken returns a cryptographically random URL-safe string (exported for
// CSRF tokens and temp passwords in the API layer).
func RandomToken(n int) string {
	return randomToken(n)
}

func CheckPasswordPolicy(pw string) (bool, string) {
	if len(pw) < 12 {
		return false, "Password must be at least 12 characters"
	}
	hasUpper, hasLower, hasDigit := false, false, false
	for _, c := range pw {
		switch {
		case c >= 'A' && c <= 'Z':
			hasUpper = true
		case c >= 'a' && c <= 'z':
			hasLower = true
		case c >= '0' && c <= '9':
			hasDigit = true
		}
	}
	if !hasUpper || !hasLower || !hasDigit {
		return false, "Password must contain uppercase, lowercase and a digit"
	}
	return true, ""
}

func IsAdmin(u *User) bool {
	return u != nil && u.Role == "admin"
}

// ConstantTimeEqual compares two strings in constant time.
func ConstantTimeEqual(a, b string) bool {
	return hmac.Equal([]byte(a), []byte(b))
}

// PBKDF2Key is exported for tests.
func PBKDF2Key(raw string) string { return HashAPIKey(raw) }

func NormalizeUsername(u string) string {
	return strings.TrimSpace(u)
}

func NowISO() string {
	return time.Now().UTC().Format("2006-01-02T15:04:05.000000+00:00")
}

var _ = fmt.Sprintf
