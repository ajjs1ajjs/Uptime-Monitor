"""Tests for auth module functions (pure units, no DB)"""
import pytest

from Uptime_Robot.auth_module import (
    validate_password_strength,
    has_role,
    is_admin,
    is_viewer_or_higher,
    hash_password,
    verify_password,
    generate_api_key,
    _hash_api_key,
    API_KEY_PREFIX,
)


class TestPasswordStrength:
    def test_too_short(self):
        valid, msg = validate_password_strength("Ab1")
        assert not valid
        assert "12 characters" in msg

    def test_no_uppercase(self):
        valid, msg = validate_password_strength("alllowercase123")
        assert not valid
        assert "uppercase" in msg

    def test_no_lowercase(self):
        valid, msg = validate_password_strength("ALLUPPERCASE123")
        assert not valid
        assert "lowercase" in msg

    def test_no_digit(self):
        valid, msg = validate_password_strength("NoDigitsHere!")
        assert not valid
        assert "digit" in msg

    def test_valid_password(self):
        valid, msg = validate_password_strength("ValidP@ss1234")
        assert valid
        assert msg == ""

    def test_exactly_12_chars_missing_upper(self):
        valid, msg = validate_password_strength("abcdefgh1!jk")
        assert not valid

    def test_exactly_12_chars_valid(self):
        valid, msg = validate_password_strength("Abcdefgh1!jk")
        assert valid


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "SecurePass123!"
        hashed = hash_password(password)
        assert hashed != password
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("CorrectPass1")
        assert not verify_password("WrongPass1", hashed)

    def test_empty_password_fails(self):
        hashed = hash_password("RealPass1!")
        assert not verify_password("", hashed)

    def test_invalid_hash_returns_false(self):
        assert not verify_password("pass", "not-a-hash")

    def test_different_hashes(self):
        h1 = hash_password("Pass1234!")
        h2 = hash_password("Pass1234!")
        assert h1 != h2  # bcrypt uses different salts


class TestRoleChecks:
    def test_admin_has_role_admin(self):
        assert has_role({"role": "admin"}, "admin")

    def test_admin_has_role_viewer(self):
        assert has_role({"role": "admin"}, "viewer")

    def test_viewer_has_role_viewer(self):
        assert has_role({"role": "viewer"}, "viewer")

    def test_viewer_does_not_have_role_admin(self):
        assert not has_role({"role": "viewer"}, "admin")

    def test_none_user_returns_false(self):
        assert not has_role(None, "admin")
        assert not has_role(None, "viewer")

    def test_empty_user_returns_false(self):
        assert not has_role({}, "admin")

    def test_is_admin(self):
        assert is_admin({"role": "admin"})
        assert not is_admin({"role": "viewer"})
        assert not is_admin({})
        assert not is_admin(None)

    def test_is_viewer_or_higher(self):
        assert is_viewer_or_higher({"role": "admin"})
        assert is_viewer_or_higher({"role": "viewer"})
        assert not is_viewer_or_higher({"role": "guest"})
        assert not is_viewer_or_higher({})
        assert not is_viewer_or_higher(None)

    def test_missing_role_defaults_to_viewer(self):
        assert not has_role({"role": None}, "admin")

    def test_role_none_is_not_admin(self):
        assert not is_admin({"role": None})


class TestApiKeyGeneration:
    def test_generates_with_prefix(self):
        key = generate_api_key()
        assert key.startswith(API_KEY_PREFIX)

    def test_unique_keys(self):
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100

    def test_hash_is_deterministic(self):
        key = generate_api_key()
        h1 = _hash_api_key(key)
        h2 = _hash_api_key(key)
        assert h1 == h2

    def test_different_keys_different_hashes(self):
        key1 = generate_api_key()
        key2 = generate_api_key()
        assert _hash_api_key(key1) != _hash_api_key(key2)

    def test_hash_length(self):
        key = generate_api_key()
        h = _hash_api_key(key)
        assert len(h) == 64  # SHA-256 hex

    def test_key_format(self):
        key = generate_api_key()
        assert len(key) > len(API_KEY_PREFIX)
        assert "_" in key
