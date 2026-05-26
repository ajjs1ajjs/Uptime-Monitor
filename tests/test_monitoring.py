"""Tests for monitoring module pure functions"""
from unittest.mock import AsyncMock, patch

import pytest

from Uptime_Robot.monitoring import get_alert_policy, normalize_ssl_url


SENSITIVE_KEYS = {
    "request_timeout_seconds", "down_failures_threshold", "up_success_threshold",
    "still_down_repeat_seconds", "treat_4xx_as_down", "ssl_notification_days",
    "ssl_notification_cooldown_seconds", "ssl_check_interval_hours", "verify_ssl",
}


class TestAlertPolicy:
    def test_default_values(self):
        policy = get_alert_policy()
        assert isinstance(policy, dict)
        assert policy.get("request_timeout_seconds", 0) >= 1
        assert policy.get("down_failures_threshold", 0) >= 1
        assert policy.get("up_success_threshold", 0) >= 1
        assert policy.get("still_down_repeat_seconds", 0) >= 60
        assert policy.get("verify_ssl") is True

    def test_all_expected_keys_present(self):
        policy = get_alert_policy()
        for key in SENSITIVE_KEYS:
            assert key in policy, f"Missing key: {key}"

    def test_treat_4xx_as_down_is_boolean(self):
        policy = get_alert_policy()
        assert isinstance(policy["treat_4xx_as_down"], bool)

    def test_timeout_is_positive(self):
        policy = get_alert_policy()
        assert policy["request_timeout_seconds"] > 0

    def test_thresholds_are_positive(self):
        policy = get_alert_policy()
        assert policy["down_failures_threshold"] >= 1
        assert policy["up_success_threshold"] >= 1


class TestNormalizeSSLUrl:
    def test_normal_https_url_unchanged(self):
        assert normalize_ssl_url("https://example.com") == "https://example.com"
        assert normalize_ssl_url("https://example.com:443") == "https://example.com:443"

    def test_adds_https_prefix(self):
        assert normalize_ssl_url("example.com") == "https://example.com"
        assert normalize_ssl_url("sub.example.com") == "https://sub.example.com"

    def test_http_stays_http(self):
        assert normalize_ssl_url("http://example.com") == "http://example.com"

    def test_empty_returns_none(self):
        assert normalize_ssl_url("") is None

    def test_none_returns_none(self):
        assert normalize_ssl_url(None) is None

    def test_handles_port(self):
        assert normalize_ssl_url("example.com:8080") == "https://example.com:8080"


class TestNormalizeAndValidateURL:
    def test_valid_http_url(self):
        from Uptime_Robot.routers.api import _normalize_and_validate_url

        url = _normalize_and_validate_url("https://example.com", "http")
        assert "example.com" in url

    def test_missing_scheme(self):
        from Uptime_Robot.routers.api import _normalize_and_validate_url

        url = _normalize_and_validate_url("example.com", "http")
        assert "example.com" in url

    def test_empty_url_raises(self):
        from Uptime_Robot.routers.api import _normalize_and_validate_url

        with pytest.raises(Exception):
            _normalize_and_validate_url("", "http")
