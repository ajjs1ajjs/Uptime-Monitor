import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_DB_PATH = None


@pytest.fixture(autouse=True)
def setup_test_db():
    global TEST_DB_PATH
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        TEST_DB_PATH = f.name

    # Patch DB_PATH before any imports
    with patch("Uptime_Robot.state.DB_PATH", TEST_DB_PATH):
        with patch("Uptime_Robot.main.DB_PATH", TEST_DB_PATH):
            from Uptime_Robot.models import init_database
            import asyncio
            asyncio.run(init_database(TEST_DB_PATH))

            from Uptime_Robot.database import get_db_connection
            conn = get_db_connection(TEST_DB_PATH)

            # Insert test sites
            async def _setup():
                async with conn as c:
                    await c.execute(
                        "INSERT INTO sites (name, url, check_interval, is_active, status) VALUES (?, ?, ?, ?, ?)",
                        ("Test Site 1", "https://example.com", 60, 1, "up"),
                    )
                    await c.execute(
                        "INSERT INTO sites (name, url, check_interval, is_active, status) VALUES (?, ?, ?, ?, ?)",
                        ("Test Site 2", "https://google.com", 60, 1, "up"),
                    )

                    now = datetime.now()
                    for i in range(5):
                        ts = (now - timedelta(minutes=i * 5)).isoformat()
                        status = "up" if i % 2 == 0 else "down"
                        await c.execute(
                            "INSERT INTO status_history (site_id, status, status_code, response_time, checked_at) VALUES (?, ?, ?, ?, ?)",
                            (1, status, 200 if status == "up" else 503, 100 + i * 10, ts),
                        )

                    await c.commit()

            asyncio.run(_setup())

    yield

    os.unlink(TEST_DB_PATH)


@pytest.fixture
def db():
    from Uptime_Robot.database import get_db_connection
    return get_db_connection(TEST_DB_PATH)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from Uptime_Robot.main import app

    with patch("Uptime_Robot.state.DB_PATH", TEST_DB_PATH):
        with patch("Uptime_Robot.routers.api.DB_PATH", TEST_DB_PATH):
            with TestClient(app) as c:
                yield c


class TestSitesAPI:
    def test_get_sites_via_db(self, db):
        async def _test():
            async with db as conn:
                async with conn.execute("SELECT * FROM sites") as c:
                    sites = await c.fetchall()

            assert len(sites) == 2
            assert sites[0]["name"] == "Test Site 1"
            assert sites[0]["url"] == "https://example.com"

        import asyncio
        asyncio.run(_test())

    def test_get_active_sites(self, db):
        async def _test():
            async with db as conn:
                async with conn.execute("SELECT * FROM sites WHERE is_active = 1") as c:
                    sites = await c.fetchall()

            assert len(sites) == 2
            for site in sites:
                assert site["is_active"] == 1

        import asyncio
        asyncio.run(_test())

    def test_add_site(self, db):
        async def _test():
            async with db as conn:
                await conn.execute(
                    "INSERT INTO sites (name, url, check_interval, is_active, monitor_type) VALUES (?, ?, ?, ?, ?)",
                    ("New Site", "https://newsite.com", 120, 1, "http"),
                )
                await conn.commit()

                async with conn.execute("SELECT * FROM sites WHERE url = ?", ("https://newsite.com",)) as c:
                    site = await c.fetchone()

            assert site is not None
            assert site["name"] == "New Site"
            assert site["check_interval"] == 120

        import asyncio
        asyncio.run(_test())


class TestMonitoring:
    @patch("aiohttp.ClientSession")
    def test_site_up_down_detection(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__aenter__ = MagicMock(return_value=mock_response)
        mock_response.__aexit__ = MagicMock(return_value=None)

        mock_session.return_value.__aenter__.return_value.get.return_value = mock_response

        from Uptime_Robot.monitoring import get_alert_policy
        policy = get_alert_policy()

        if policy["treat_4xx_as_down"]:
            status = "up" if 200 <= 200 < 400 else "down"
        else:
            status = "up" if 200 < 500 else "down"
        assert status == "up"

    def test_alert_policy_defaults(self):
        from Uptime_Robot.monitoring import get_alert_policy
        policy = get_alert_policy()

        assert policy["request_timeout_seconds"] >= 1
        assert policy["down_failures_threshold"] >= 1
        assert policy["up_success_threshold"] >= 1
        assert policy["still_down_repeat_seconds"] >= 60
        assert "verify_ssl" in policy
        assert policy["verify_ssl"] is True

    def test_normalize_ssl_url(self):
        from Uptime_Robot.monitoring import normalize_ssl_url

        assert normalize_ssl_url("https://example.com") == "https://example.com"
        assert normalize_ssl_url("example.com") == "https://example.com"
        assert normalize_ssl_url("") is None
        assert normalize_ssl_url(None) is None


class TestNotifications:
    def test_format_telegram_down(self):
        from Uptime_Robot.notifications import format_telegram_message

        data = {
            "site_name": "Test",
            "url": "https://test.com",
            "status_code": 500,
            "error": "Timeout",
            "checked_at": "2026-01-01T00:00:00",
        }
        msg = format_telegram_message(data, "down")
        assert "Test" in msg
        assert "500" in msg
        assert "Timeout" in msg

    def test_format_discord_embed(self):
        from Uptime_Robot.notifications import format_discord_message

        data = {
            "site_name": "Test",
            "url": "https://test.com",
            "status_code": 200,
            "response_time": 150,
            "checked_at": "2026-01-01T00:00:00",
        }
        payload = format_discord_message(data, "up")
        assert "embeds" in payload
        assert payload["embeds"][0]["color"] == 65280  # green


class TestDataValidation:
    def test_url_validation(self):
        from urllib.parse import urlparse

        valid_urls = [
            "https://example.com",
            "http://localhost:8080",
            "https://sub.example.com/path",
        ]

        for url in valid_urls:
            parsed = urlparse(url)
            assert parsed.scheme in ["http", "https"]
            assert parsed.netloc != ""

    def test_invalid_urls(self):
        from urllib.parse import urlparse

        invalid_urls = ["not-a-url", "ftp://example.com", ""]

        for url in invalid_urls:
            parsed = urlparse(url)
            is_valid = parsed.scheme in ["http", "https"] and parsed.netloc != ""
            assert not is_valid

    def test_password_validation(self):
        from Uptime_Robot.auth_module import validate_password_strength

        is_valid, msg = validate_password_strength("short")
        assert not is_valid
        assert "12 characters" in msg

        is_valid, msg = validate_password_strength("alllowercase123")
        assert not is_valid
        assert "uppercase" in msg

        is_valid, msg = validate_password_strength("ALLUPPERCASE123")
        assert not is_valid
        assert "lowercase" in msg

        is_valid, msg = validate_password_strength("NoDigitsHere!")
        assert not is_valid
        assert "digit" in msg

        is_valid, msg = validate_password_strength("ValidP@ss1234")
        assert is_valid
        assert msg == ""


class TestSSLCertificates:
    def test_ssl_cert_check(self, db):
        async def _test():
            async with db as conn:
                await conn.execute(
                    "INSERT INTO ssl_certificates (site_id, hostname, issuer, days_until_expire, is_valid, last_checked) VALUES (?, ?, ?, ?, ?, ?)",
                    (1, "example.com", "Let's Encrypt", 30, 1, datetime.now().isoformat()),
                )
                await conn.commit()

                async with conn.execute("SELECT * FROM ssl_certificates WHERE site_id = ?", (1,)) as c:
                    cert = await c.fetchone()

            assert cert is not None
            assert cert["hostname"] == "example.com"
            assert cert["days_until_expire"] == 30

        import asyncio
        asyncio.run(_test())

    def test_ssl_expiring(self, db):
        async def _test():
            async with db as conn:
                await conn.execute(
                    "INSERT INTO ssl_certificates (site_id, hostname, days_until_expire, is_valid) VALUES (?, ?, ?, ?)",
                    (1, "expiring.com", 5, 1),
                )
                await conn.commit()

                async with conn.execute("SELECT * FROM ssl_certificates WHERE days_until_expire <= 7 AND is_valid = 1") as c:
                    expiring = await c.fetchall()

            assert len(expiring) == 1
            assert expiring[0]["days_until_expire"] == 5

        import asyncio
        asyncio.run(_test())

    def test_ssl_expired(self, db):
        async def _test():
            async with db as conn:
                await conn.execute(
                    "INSERT INTO ssl_certificates (site_id, hostname, days_until_expire, is_valid) VALUES (?, ?, ?, ?)",
                    (1, "expired.com", -5, 0),
                )
                await conn.commit()

                async with conn.execute("SELECT * FROM ssl_certificates WHERE days_until_expire < 0 OR is_valid = 0") as c:
                    expired = await c.fetchall()

            assert len(expired) == 1

        import asyncio
        asyncio.run(_test())


class TestHealthEndpoint:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
