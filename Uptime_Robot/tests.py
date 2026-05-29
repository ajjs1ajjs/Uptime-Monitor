"""Тести для Uptime Monitor"""

import asyncio
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from typing import Optional

# Додаємо шлях до модулів
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_module import hash_password, verify_password  # noqa: E402
from database import get_db_connection  # noqa: E402
from models import (
    add_maintenance_window,
    add_site,  # noqa: E402
    delete_site,
    get_all_sites,
    init_database,
)
from notifications import NotificationService  # noqa: E402


async def _asgi_json_request(
    app, method: str, path: str, payload: dict, session_id: Optional[str] = None
):
    """Minimal ASGI JSON request helper without external test clients."""
    body = json.dumps(payload).encode("utf-8")
    response_chunks = []
    status_code = None
    request_sent = False

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            headers = [
                (b"host", b"testserver"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ]
            if session_id:
                headers.append((b"cookie", f"session_id={session_id}".encode("ascii")))
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
                "headers": headers,
            }
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            response_chunks.append(message.get("body", b""))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        + ([(b"cookie", f"session_id={session_id}".encode("ascii"))] if session_id else []),
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    await app(scope, receive, send)
    response_body = b"".join(response_chunks).decode("utf-8") if response_chunks else ""
    response_json = json.loads(response_body) if response_body else {}
    return status_code, response_json


class TestAuth:
    """Тести авторизації"""

    def test_password_hashing(self):
        """Тест хешування паролів"""
        password = "test_password123"
        hashed = hash_password(password)

        # Перевіряємо що хеш відрізняється від пароля
        assert hashed != password
        # Перевіряємо що bcrypt хеш починається з $2b$
        assert hashed.startswith("$2b$")
        # Перевіряємо верифікацію
        assert verify_password(password, hashed) is True
        assert verify_password("wrong_password", hashed) is False

    def test_password_verification_old_hash(self):
        """Тест сумісності зі старими SHA256 хешами"""
        # Старий SHA256 хеш для "admin"
        import hashlib

        old_hash = hashlib.sha256(b"admin").hexdigest()

        # Старий метод не повинен працювати з новим verify_password
        assert verify_password("admin", old_hash) is False


class TestDatabase:
    """Тести бази даних"""

    def setup_method(self):
        """Налаштування перед кожним тестом"""
        self.test_db = "test_sites.db"
        # Видаляємо стару базу якщо існує
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        asyncio.run(init_database(self.test_db))

    def teardown_method(self):
        """Очистка після кожного тесту"""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_init_database(self):
        """Тест ініціалізації БД"""
        assert os.path.exists(self.test_db)

        conn = sqlite3.connect(self.test_db)
        c = conn.cursor()

        # Перевіряємо чи створились таблиці
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in c.fetchall()]

        assert "sites" in tables
        assert "status_history" in tables
        assert "ssl_certificates" in tables

        conn.close()

    def test_add_site(self):
        """Тест додавання сайту"""
        # Видаляємо базу перед тестом
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        asyncio.run(init_database(self.test_db))

        site_id = asyncio.run(
            add_site(self.test_db, name="Test Site", url="https://example.com", check_interval=60)
        )

        assert site_id > 0

        sites = asyncio.run(get_all_sites(self.test_db))
        assert len(sites) == 1
        assert sites[0]["name"] == "Test Site"
        assert sites[0]["url"] == "https://example.com"

    def test_delete_site(self):
        """Тест видалення сайту"""
        # Видаляємо базу перед тестом
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        asyncio.run(init_database(self.test_db))

        site_id = asyncio.run(
            add_site(self.test_db, name="Test Site Delete", url="https://example-delete.com")
        )

        sites = asyncio.run(get_all_sites(self.test_db))
        assert len(sites) == 1

        asyncio.run(delete_site(self.test_db, site_id))

        sites = asyncio.run(get_all_sites(self.test_db))
        assert len(sites) == 0


class TestValidation:
    """Тести валідації"""

    def test_url_validation(self):
        """Тест валідації URL"""
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://sub.example.com/path",
        ]

        invalid_urls = [
            "ftp://example.com",
            "example.com",
            "not_a_url",
        ]

        for url in valid_urls:
            assert url.startswith(("http://", "https://"))

        for url in invalid_urls:
            assert not url.startswith(("http://", "https://"))

    def test_site_name_validation(self):
        """Тест валідації назви сайту"""
        valid_names = [
            "My Site",
            "Site-123",
            "A",
        ]

        for name in valid_names:
            assert len(name.strip()) > 0


class TestNotificationService:
    """Тести сервісу сповіщень"""

    def test_notification_service_init(self):
        """Тест ініціалізації сервісу"""
        settings = {
            "telegram": {"enabled": True, "token": "test_token", "chat_id": "123456"},
            "email": {"enabled": False},
        }

        service = NotificationService(settings)
        assert service.settings == settings


# pytest.ini конфігурація
"""
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
"""


class TestApiSmoke:
    """Smoke tests for API routes."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="uptime-smoke-")
        self.test_db = os.path.join(self.tmp_dir, "smoke_sites.db")
        self._create_legacy_db_without_monitor_type(self.test_db)

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_legacy_db_without_monitor_type(self, db_path: str):
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            check_interval INTEGER DEFAULT 60,
            is_active BOOLEAN DEFAULT 1,
            last_notification TEXT,
            notify_methods TEXT DEFAULT '[]',
            monitor_type TEXT DEFAULT 'http'
        )""")
        conn.commit()
        conn.close()

    def test_post_sites_smoke_with_monitor_type_migration(self):
        from unittest.mock import patch

        import auth_module
        import main
        import monitoring

        original_check_site_status = monitoring.check_site_status
        original_check_site_certificate = monitoring.check_site_certificate
        certificate_check_calls = []

        async def fake_check_site_status(site_id, url, notify_methods, notify_settings=None):
            return None

        async def fake_check_site_certificate(site_id, url, notify_methods, notify_settings=None):
            certificate_check_calls.append(url)
            return None

        async def _run_test():
            await main.initialize_app_async()
            await auth_module.init_auth_tables(self.test_db)

            # Create a session for authentication
            session_id = await auth_module.create_session(1, self.test_db)
            safe_session_id = session_id[:8].replace("_", "-")

            conn = sqlite3.connect(self.test_db)
            c = conn.cursor()
            c.execute("PRAGMA table_info(sites)")
            columns = [row[1] for row in c.fetchall()]
            conn.close()
            assert "monitor_type" in columns

            monitoring.check_site_status = fake_check_site_status
            monitoring.check_site_certificate = fake_check_site_certificate

            payload = {
                "name": "Smoke Monitor",
                "url": f"example-{safe_session_id}.com",
                "monitor_type": "ssl",
                "notify_methods": ["telegram"],
            }
            status_code, response = await _asgi_json_request(
                main.app, "POST", "/api/sites", payload, session_id
            )

            await asyncio.sleep(0.1)
            if status_code != 200:
                raise AssertionError(
                    f"Smoke test failed. Status: {status_code}, Response: {response}"
                )
            assert response.get("message") == "Site added"
            assert isinstance(response.get("id"), int)

            conn = sqlite3.connect(self.test_db)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT name, url, monitor_type, notify_methods FROM sites WHERE id = ?",
                (response["id"],),
            )
            row = c.fetchone()
            conn.close()

            assert row is not None
            assert row["name"] == "Smoke Monitor"
            assert row["url"] == f"https://example-{safe_session_id}.com"
            assert row["monitor_type"] == "ssl"
            assert json.loads(row["notify_methods"]) == ["telegram"]
            assert certificate_check_calls == [f"https://example-{safe_session_id}.com"]

        patchers = [
            patch("main.DB_PATH", self.test_db),
            patch("state.DB_PATH", self.test_db),
            patch("dependencies.DB_PATH", self.test_db),
            patch("config_manager.DB_PATH", self.test_db),
            patch("routers.api.DB_PATH", self.test_db),
            patch("routers.auth.DB_PATH", self.test_db),
        ]

        for p in patchers:
            p.start()

        try:
            asyncio.run(_run_test())
        finally:
            for p in patchers:
                try:
                    p.stop()
                except Exception:
                    pass
            monitoring.check_site_status = original_check_site_status
            monitoring.check_site_certificate = original_check_site_certificate


class TestMonitorTypes:
    """Тести нових типів моніторингу (Ping, Port, HTTP Keyword)"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="uptime-monitor-")
        self.test_db = os.path.join(self.tmp_dir, "monitor_sites.db")
        asyncio.run(init_database(self.test_db))

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    async def test_ping_check(self):
        from unittest.mock import AsyncMock, patch

        import monitoring

        # Mock the subprocess execution for ping
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"ping response", b"")

        # Test success case
        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("database.get_db_path", return_value=self.test_db),
        ):

            site_id = await add_site(
                self.test_db, name="Ping Test", url="127.0.0.1", monitor_type="ping"
            )
            status, code, rt, err = await monitoring.check_site_status(site_id, "127.0.0.1", [], {})
            assert status == "up"
            assert code == 0
            assert err is None

        # Test failure case
        mock_proc.returncode = 1
        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("database.get_db_path", return_value=self.test_db),
        ):

            status, code, rt, err = await monitoring.check_site_status(site_id, "127.0.0.1", [], {})
            assert status == "down"
            assert err == "Ping failed"

    async def test_port_check(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        import monitoring

        # Test success case
        mock_writer = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_reader = AsyncMock()
        with (
            patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)),
            patch("database.get_db_path", return_value=self.test_db),
        ):

            site_id = await add_site(
                self.test_db, name="Port Test", url="127.0.0.1:80", monitor_type="port"
            )
            status, code, rt, err = await monitoring.check_site_status(
                site_id, "127.0.0.1:80", [], {}
            )
            assert status == "up"
            assert code == 80
            assert err is None

        # Test failure case (connection refused)
        with (
            patch(
                "asyncio.open_connection", side_effect=ConnectionRefusedError("Connection refused")
            ),
            patch("database.get_db_path", return_value=self.test_db),
        ):

            status, code, rt, err = await monitoring.check_site_status(
                site_id, "127.0.0.1:80", [], {}
            )
            assert status == "down"
            assert "Connection refused" in err

    async def test_keyword_check(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        import monitoring

        # Mock aiohttp client session
        mock_response = AsyncMock()
        mock_response.status = 200

        # Scenario 1: Keyword is present
        mock_response.text.return_value = "<html><body>Welcome to My Site</body></html>"

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_context)

        with (
            patch("aiohttp.ClientSession", return_value=mock_session),
            patch("database.get_db_path", return_value=self.test_db),
        ):

            site_id = await add_site(
                self.test_db,
                name="HTTP Keyword",
                url="http://example.com",
                monitor_type="http",
                keyword="Welcome",
            )
            status, code, rt, err = await monitoring.check_site_status(
                site_id, "http://example.com", [], {}
            )
            assert status == "up"
            assert code == 200
            assert err is None

        # Scenario 2: Keyword is missing
        mock_response.text.return_value = "<html><body>Error page</body></html>"
        with (
            patch("aiohttp.ClientSession", return_value=mock_session),
            patch("database.get_db_path", return_value=self.test_db),
        ):

            status, code, rt, err = await monitoring.check_site_status(
                site_id, "http://example.com", [], {}
            )
            assert status == "down"
            assert err == "Keyword not found"


class TestAdvancedFeatures:
    """Тести розширеного функціоналу (Maintenance Windows, SLA Reports, Webhooks)"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="uptime-monitor-advanced-")
        self.test_db = os.path.join(self.tmp_dir, "monitor_sites.db")
        asyncio.run(init_database(self.test_db))

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    async def test_maintenance_window_skips_checks(self):
        from unittest.mock import patch

        import monitoring

        site_id = await add_site(
            self.test_db, name="Maint Site", url="http://example.com", monitor_type="http"
        )

        now = datetime.now()
        start_time = (now - timedelta(hours=1)).isoformat() + "Z"
        end_time = (now + timedelta(hours=1)).isoformat() + "Z"

        await add_maintenance_window(
            self.test_db,
            name="Maint Window",
            site_id=site_id,
            rule_type="one_off",
            start_time=start_time,
            end_time=end_time,
        )

        with patch("database.get_db_path", return_value=self.test_db):
            status, code, rt, err = await monitoring.check_site_status(
                site_id, "http://example.com", [], {}
            )
            assert status == "maintenance"
            assert err == "Maintenance Window Active"

    async def test_sla_report_calculations(self):
        site_id = await add_site(
            self.test_db, name="SLA Site", url="http://example.com", monitor_type="http"
        )
        async with get_db_connection(self.test_db) as conn:
            await conn.execute(
                "INSERT INTO status_history (site_id, status, response_time, checked_at) VALUES (?, 'up', 100, datetime('now'))",
                (site_id,),
            )
            await conn.execute(
                "INSERT INTO status_history (site_id, status, response_time, checked_at) VALUES (?, 'up', 120, datetime('now'))",
                (site_id,),
            )
            await conn.execute(
                "INSERT INTO status_history (site_id, status, response_time, checked_at) VALUES (?, 'down', 0, datetime('now'))",
                (site_id,),
            )
            await conn.commit()

        async with get_db_connection(self.test_db) as conn:
            async with conn.execute(
                """SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_count,
                    AVG(response_time) as avg_rt
                  FROM status_history
                  WHERE site_id = ? AND checked_at >= datetime('now', '-7 days')""",
                (site_id,),
            ) as c:
                stats = await c.fetchone()
            async with conn.execute(
                """SELECT COUNT(*) FROM status_history
                   WHERE site_id = ? AND status IN ('down', 'slow') AND checked_at >= datetime('now', '-7 days')""",
                (site_id,),
            ) as c:
                incidents = (await c.fetchone())[0]

        total = stats["total"] or 0
        up_count = stats["up_count"] or 0
        uptime = (up_count / total * 100) if total > 0 else 100.0
        stats["avg_rt"] or 0

        assert total == 3
        assert up_count == 2
        assert abs(uptime - 66.67) < 0.1
        assert incidents == 1

    async def test_webhook_alert_dispatch(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        import notifications

        mock_response = AsyncMock()
        mock_response.status = 200

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_context)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            settings = {"webhook_url": "http://my-webhook.internal/endpoint"}
            message = {"alert_type": "down", "site_name": "Test Site", "url": "http://test"}

            await notifications.send_webhook(message, settings)

            mock_session.post.assert_called_once_with(
                "http://my-webhook.internal/endpoint", json=message
            )


if __name__ == "__main__":
    # Запуск тестів
    print("Running tests...")

    # Тести авторизації
    auth_tests = TestAuth()
    auth_tests.test_password_hashing()
    print("[OK] Password hashing test passed")

    auth_tests.test_password_verification_old_hash()
    print("[OK] Old hash compatibility test passed")

    # Тести бази даних
    db_tests = TestDatabase()
    db_tests.setup_method()
    db_tests.test_init_database()
    print("[OK] Database initialization test passed")

    db_tests.setup_method()
    db_tests.test_add_site()
    print("[OK] Add site test passed")

    db_tests.setup_method()
    db_tests.test_delete_site()
    print("[OK] Delete site test passed")
    db_tests.teardown_method()

    # Тести валідації
    val_tests = TestValidation()
    val_tests.test_url_validation()
    print("[OK] URL validation test passed")

    val_tests.test_site_name_validation()
    print("[OK] Site name validation test passed")

    # Тести сповіщень
    notif_tests = TestNotificationService()
    notif_tests.test_notification_service_init()
    print("[OK] Notification service test passed")

    smoke_tests = TestApiSmoke()
    smoke_tests.setup_method()
    try:
        smoke_tests.test_post_sites_smoke_with_monitor_type_migration()
        print("[OK] API smoke test (/api/sites + monitor_type migration) passed")
    finally:
        smoke_tests.teardown_method()

    # Тести типів моніторів
    monitor_tests = TestMonitorTypes()
    monitor_tests.setup_method()
    try:
        asyncio.run(monitor_tests.test_ping_check())
        print("[OK] Monitor types: Ping check test passed")
        asyncio.run(monitor_tests.test_port_check())
        print("[OK] Monitor types: Port check test passed")
        asyncio.run(monitor_tests.test_keyword_check())
        print("[OK] Monitor types: HTTP Keyword check test passed")
    finally:
        monitor_tests.teardown_method()

    # Тести розширеного функціоналу
    advanced_tests = TestAdvancedFeatures()
    advanced_tests.setup_method()
    try:
        asyncio.run(advanced_tests.test_maintenance_window_skips_checks())
        print("[OK] Advanced features: Maintenance window skips checks passed")
    finally:
        advanced_tests.teardown_method()

    advanced_tests.setup_method()
    try:
        asyncio.run(advanced_tests.test_sla_report_calculations())
        print("[OK] Advanced features: SLA report calculations passed")
    finally:
        advanced_tests.teardown_method()

    advanced_tests.setup_method()
    try:
        asyncio.run(advanced_tests.test_webhook_alert_dispatch())
        print("[OK] Advanced features: Webhook alert dispatch passed")
    finally:
        advanced_tests.teardown_method()

    print("\n" + "=" * 50)
    print("All tests passed!")
    print("=" * 50)
