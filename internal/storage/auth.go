package storage

import (
	"database/sql"
	"strings"
	"time"
)

// User mirrors the auth.User model but lives in storage so queries can build it.
type User struct {
	ID                 int64  `json:"id"`
	Username           string `json:"username"`
	PasswordHash       string `json:"-"`
	Role               string `json:"role"`
	MustChangePassword int    `json:"must_change_password"`
	CreatedAt          string `json:"created_at"`
	LastLogin          string `json:"last_login"`
}

// --- users ---

func (st *Store) GetUserByUsername(username string) (*User, error) {
	row := st.DB.QueryRow(`SELECT id, username, password_hash, role, must_change_password, created_at, last_login
	  FROM users WHERE username = ?`, username)
	return scanUser(row)
}

func (st *Store) GetUserByID(id int64) (*User, error) {
	row := st.DB.QueryRow(`SELECT id, username, password_hash, role, must_change_password, created_at, last_login
	  FROM users WHERE id = ?`, id)
	return scanUser(row)
}

func scanUser(row interface{ Scan(...any) error }) (*User, error) {
	var u User
	var role sql.NullString
	var mcp, created, lastLogin sql.NullString
	err := row.Scan(&u.ID, &u.Username, &u.PasswordHash, &role, &mcp, &created, &lastLogin)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if role.Valid {
		u.Role = role.String
	}
	if u.Role == "" {
		u.Role = "viewer"
	}
	if mcp.String == "1" {
		u.MustChangePassword = 1
	}
	u.CreatedAt = created.String
	u.LastLogin = lastLogin.String
	return &u, nil
}

func (st *Store) ListUsers() ([]User, error) {
	rows, err := st.DB.Query(`SELECT id, username, password_hash, role, must_change_password, created_at, last_login
	  FROM users ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []User
	for rows.Next() {
		u, err := scanUser(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, *u)
	}
	return out, rows.Err()
}

func (st *Store) CreateUser(username, hash, role string) (int64, error) {
	if role == "" {
		role = "viewer"
	}
	res, err := st.DB.Exec(`INSERT INTO users (username, password_hash, role, must_change_password, created_at)
	  VALUES (?,?,?,0,?)`, username, hash, role, Now())
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func (st *Store) UpdateUser(id int64, fields map[string]any) error {
	if len(fields) == 0 {
		return nil
	}
	var sets []string
	var args []any
	for k, v := range fields {
		sets = append(sets, k+" = ?")
		args = append(args, v)
	}
	args = append(args, id)
	_, err := st.DB.Exec(`UPDATE users SET `+strings.Join(sets, ", ")+` WHERE id = ?`, args...)
	return err
}

func (st *Store) DeleteUser(id int64) error {
	tx, err := st.DB.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	if _, err := tx.Exec(`DELETE FROM sessions WHERE user_id = ?`, id); err != nil {
		return err
	}
	if _, err := tx.Exec(`DELETE FROM users WHERE id = ?`, id); err != nil {
		return err
	}
	return tx.Commit()
}

func (st *Store) CountAdmins() (int, error) {
	var n int
	err := st.DB.QueryRow(`SELECT COUNT(*) FROM users WHERE role = 'admin'`).Scan(&n)
	return n, err
}

// --- sessions ---

func (st *Store) CreateSession(userID int64, sessionID string, expiresAt time.Time) error {
	_, err := st.DB.Exec(`INSERT INTO sessions (user_id, session_id, created_at, expires_at)
	  VALUES (?,?,?,?)`, userID, sessionID, Now(), expiresAt.UTC().Format("2006-01-02T15:04:05.000000+00:00"))
	return err
}

func (st *Store) GetSession(sessionID string) (*User, error) {
	row := st.DB.QueryRow(`SELECT u.id, u.username, u.password_hash, u.role, u.must_change_password, u.created_at, u.last_login
	  FROM sessions s JOIN users u ON s.user_id = u.id
	  WHERE s.session_id = ? AND s.expires_at > datetime('now')`, sessionID)
	return scanUser(row)
}

func (st *Store) DeleteSession(sessionID string) error {
	_, err := st.DB.Exec(`DELETE FROM sessions WHERE session_id = ?`, sessionID)
	return err
}

func (st *Store) DeleteUserSessions(userID int64) error {
	_, err := st.DB.Exec(`DELETE FROM sessions WHERE user_id = ?`, userID)
	return err
}

// --- api keys ---

type APIKey struct {
	KeyID      string  `json:"key_id"`
	UserID     int64   `json:"user_id"`
	Name       string  `json:"name"`
	KeyHash    string  `json:"-"`
	CreatedAt  string  `json:"created_at"`
	LastUsedAt *string `json:"last_used_at"`
	IsActive   bool    `json:"is_active"`
}

func (st *Store) CreateAPIKey(keyID, userID int64, name, keyIDStr, hash string) error {
	_, err := st.DB.Exec(`INSERT INTO api_keys (key_id, user_id, name, key_hash, created_at, is_active)
	  VALUES (?,?,?,?,?,1)`, keyIDStr, userID, name, hash, Now())
	return err
}

func (st *Store) GetAPIKeyByHash(hash string) (*APIKey, error) {
	row := st.DB.QueryRow(`SELECT key_id, user_id, name, key_hash, created_at, last_used_at, is_active
	  FROM api_keys WHERE key_hash = ?`, hash)
	var k APIKey
	var lastUsed sql.NullString
	var active int
	err := row.Scan(&k.KeyID, &k.UserID, &k.Name, &k.KeyHash, &k.CreatedAt, &lastUsed, &active)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	k.IsActive = active == 1
	if lastUsed.Valid {
		v := lastUsed.String
		k.LastUsedAt = &v
	}
	return &k, nil
}

func (st *Store) ListAPIKeys() ([]APIKey, error) {
	rows, err := st.DB.Query(`SELECT key_id, user_id, name, key_hash, created_at, last_used_at, is_active FROM api_keys ORDER BY created_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []APIKey
	for rows.Next() {
		var k APIKey
		var lastUsed sql.NullString
		var active int
		if err := rows.Scan(&k.KeyID, &k.UserID, &k.Name, &k.KeyHash, &k.CreatedAt, &lastUsed, &active); err != nil {
			return nil, err
		}
		k.IsActive = active == 1
		if lastUsed.Valid {
			v := lastUsed.String
			k.LastUsedAt = &v
		}
		out = append(out, k)
	}
	return out, rows.Err()
}

func (st *Store) RevokeAPIKey(keyID string) error {
	_, err := st.DB.Exec(`UPDATE api_keys SET is_active = 0 WHERE key_id = ?`, keyID)
	return err
}

func (st *Store) TouchAPIKey(keyID string) {
	var last sql.NullString
	_ = st.DB.QueryRow(`SELECT last_used_at FROM api_keys WHERE key_id = ?`, keyID).Scan(&last)
	now := Now()
	// throttle to once per 60s
	if last.Valid && last.String != "" {
		if t, err := time.Parse("2006-01-02T15:04:05.999999-07:00", last.String); err == nil {
			if time.Since(t) < 60*time.Second {
				return
			}
		}
	}
	_, _ = st.DB.Exec(`UPDATE api_keys SET last_used_at = ? WHERE key_id = ?`, now, keyID)
}

// --- CSRF tokens ---

func (st *Store) CreateCSRFToken(sessionID, token string) error {
	_, err := st.DB.Exec(`INSERT INTO csrf_tokens (session_id, token) VALUES (?,?)`, sessionID, token)
	return err
}

func (st *Store) ConsumeCSRFToken(sessionID, token string) bool {
	res, err := st.DB.Exec(`DELETE FROM csrf_tokens WHERE session_id = ? AND token = ?`, sessionID, token)
	return err == nil && mustRowsAffected(res) > 0
}

func mustRowsAffected(res sql.Result) int64 {
	n, _ := res.RowsAffected()
	return n
}

// --- app seeding helpers ---

func (st *Store) CountSites() (int, error) {
	var n int
	err := st.DB.QueryRow(`SELECT COUNT(*) FROM sites`).Scan(&n)
	return n, err
}
