"""Tests for monitoring module pure functions"""
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_invalid_url_raises(self):
        from Uptime_Robot.routers.api import _normalize_and_validate_url

        with pytest.raises(Exception):
            _normalize_and_validate_url("not a url at all !!!", "http")

    def test_ftp_url_rejected_for_http(self):
        from Uptime_Robot.routers.api import _normalize_and_validate_url

        with pytest.raises(Exception):
            _normalize_and_validate_url("ftp://example.com", "http")

    def test_http_scheme_added_automatically(self):
        from Uptime_Robot.routers.api import _normalize_and_validate_url

        url = _normalize_and_validate_url("example.com/path", "http")
        assert url.startswith("http://")

    def test_ip_address_accepted(self):
        from Uptime_Robot.routers.api import _normalize_and_validate_url

        url = _normalize_and_validate_url("192.168.1.1:8080", "http")
        assert "192.168.1.1" in url


class TestCheckDNS:
    @pytest.mark.asyncio
    async def test_dns_check_success(self):
        from Uptime_Robot.monitoring import _check_dns
        from datetime import datetime
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(return_value=[("family", "type", "proto", "canonname", "sockaddr")])
            status, code, rt, err = await _check_dns("http://example.com", datetime.now())
            assert status == "up"
            assert code == 0
            assert err is None
            assert rt >= 0

    @pytest.mark.asyncio
    async def test_dns_check_failure(self):
        from Uptime_Robot.monitoring import _check_dns
        from datetime import datetime
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(side_effect=Exception("Name or service not known"))
            status, code, rt, err = await _check_dns("http://nonexistent-domain-xyz.com", datetime.now())
            assert status == "down"
            assert code == 1
            assert "DNS resolution failed" in err
            assert rt >= 0


class TestCheckHttpRegex:
    @pytest.mark.asyncio
    async def test_regex_match_success(self):
        from Uptime_Robot.monitoring import _check_http
        from datetime import datetime
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "<html><body>Welcome to My Uptime Monitor page!</body></html>"

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_context)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            policy = {"request_timeout_seconds": 5, "treat_4xx_as_down": True, "verify_ssl": True}
            status, code, rt, err = await _check_http("http://example.com", datetime.now(), policy, "regex:Welcome to.*page!")
            assert status == "up"
            assert code == 200
            assert err is None

    @pytest.mark.asyncio
    async def test_regex_match_failure(self):
        from Uptime_Robot.monitoring import _check_http
        from datetime import datetime
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "<html><body>Welcome to My Uptime Monitor page!</body></html>"

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_context)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            policy = {"request_timeout_seconds": 5, "treat_4xx_as_down": True, "verify_ssl": True}
            status, code, rt, err = await _check_http("http://example.com", datetime.now(), policy, "regex:Welcome to.*dashboard!")
            assert status == "down"
            assert code == 200
            assert err == "Regex pattern not matched"

    @pytest.mark.asyncio
    async def test_regex_invalid_pattern(self):
        from Uptime_Robot.monitoring import _check_http
        from datetime import datetime
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "<html><body>Some page</body></html>"

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_context)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            policy = {"request_timeout_seconds": 5, "treat_4xx_as_down": True, "verify_ssl": True}
            status, code, rt, err = await _check_http("http://example.com", datetime.now(), policy, "regex:[invalid-regex-(")
            assert status == "down"
            assert code == 200
            assert "Invalid regex pattern" in err


class TestDailyMaintenanceMidnight:
    @pytest.mark.asyncio
    async def test_daily_maintenance_midnight_crossing(self):
        from Uptime_Robot.monitoring.maintenance import is_under_maintenance
        from datetime import datetime, timedelta
        
        # Test window: start 23:00, duration 120 mins (23:00 - 01:00)
        # Evaluated at 00:30 (next day) -> should return True
        mock_row = {
            "rule_type": "daily",
            "start_hour_minute": "23:00",
            "duration_minutes": 120,
            "site_id": 1,
            "is_active": 1
        }
        
        eval_time = datetime(2026, 6, 4, 0, 30, 0)
        
        class MockDateTime:
            @classmethod
            def now(cls):
                return eval_time
            @classmethod
            def fromisoformat(cls, s):
                return datetime.fromisoformat(s)

        mock_conn = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [mock_row]
        mock_conn.execute.return_value.__aenter__.return_value = mock_cursor
        
        with patch("Uptime_Robot.monitoring.maintenance.datetime", MockDateTime), \
             patch("Uptime_Robot.monitoring.maintenance.get_db_connection") as mock_get_db:
            
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_conn
            mock_get_db.return_value = mock_context
            
            result = await is_under_maintenance(1)
            assert result is True


class TestSSLCheckerAsync:
    @pytest.mark.asyncio
    async def test_check_ssl_certificate_nonblocking(self):
        from Uptime_Robot.ssl_checker import check_ssl_certificate
        
        # Patch the underlying sync checker
        mock_info = {
            "hostname": "example.com",
            "subject": "CN=example.com",
            "issuer": "Let's Encrypt",
            "start_date": "2026-06-01T00:00:00",
            "expire_date": "2026-09-01T00:00:00",
            "days_until_expire": 90,
            "is_valid": True,
            "checked_at": "2026-06-04T00:00:00"
        }
        
        with patch("Uptime_Robot.ssl_checker._check_ssl_certificate_sync", return_value=mock_info) as mock_sync:
            res = await check_ssl_certificate("https://example.com")
            assert res == mock_info
            mock_sync.assert_called_once_with("https://example.com")


class TestCheckAllCertificatesRobustness:
    @pytest.mark.asyncio
    async def test_check_all_certificates_ignores_individual_errors(self):
        from Uptime_Robot.monitoring import check_all_certificates
        
        mock_conn = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "url": "https://first.com", "notify_methods": "[]"},
            {"id": 2, "url": "https://second.com", "notify_methods": "[]"}
        ]
        mock_conn.execute.return_value.__aenter__.return_value = mock_cursor
        
        calls = []
        async def fake_check_site_certificate(site_id, url, methods, settings):
            calls.append(url)
            if url == "https://first.com":
                raise Exception("DB Error or Network error on first site")
        
        with patch("Uptime_Robot.monitoring.get_db_connection") as mock_get_db, \
             patch("Uptime_Robot.monitoring.check_site_certificate", fake_check_site_certificate):
            
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_conn
            mock_get_db.return_value = mock_context
            
            await check_all_certificates({})
            
            assert "https://first.com" in calls
            assert "https://second.com" in calls

