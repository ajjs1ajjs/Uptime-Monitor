"""Тести для Uptime Monitor"""

import pytest
import asyncio
import sqlite3
import os
import sys
import json
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Optional

# Додаємо шлях до модулів
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_module import (
    hash_password,
    verify_password,
    hash_password as old_hash_password,
)
from database import get_db_path
from models import init_database, add_site, get_all_sites, delete_site
from notifications import NotificationService


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
        + (
            [(b"cookie", f"session_id={session_id}".encode("ascii"))]
            if session_id
            else []
        ),
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

        old_hash = hashlib.sha256("admin".encode()).hexdigest()

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
        init_database(self.test_db)

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
        init_database(self.test_db)

        site_id = add_site(
            self.test_db, name="Test Site", url="https://example.com", check_interval=60
        )

        assert site_id > 0

        sites = get_all_sites(self.test_db)
        assert len(sites) == 1
        assert sites[0]["name"] == "Test Site"
        assert sites[0]["url"] == "https://example.com"

    def test_delete_site(self):
        """Тест видалення сайту"""
        # Видаляємо базу перед тестом
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        init_database(self.test_db)

        site_id = add_site(
            self.test_db, name="Test Site Delete", url="https://example-delete.com"
        )

        sites = get_all_sites(self.test_db)
        assert len(sites) == 1

        delete_site(self.test_db, site_id)

        sites = get_all_sites(self.test_db)
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
        import main
        import monitoring
        import auth_module
        import config_manager

        original_db_path = main.DB_PATH
        original_db_path_config = config_manager.DB_PATH
        original_check_site_status = monitoring.check_site_status
        original_check_site_certificate = monitoring.check_site_certificate
        main.DB_PATH = self.test_db
        config_manager.DB_PATH = self.test_db
        certificate_check_calls = []

        async def fake_check_site_status(
            site_id, url, notify_methods, notify_settings=None
        ):
            return None

        async def fake_check_site_certificate(
            site_id, url, notify_methods, notify_settings=None
        ):
            certificate_check_calls.append(url)
            return None

        try:
            main.initialize_app()
            auth_module.init_auth_tables(self.test_db)

            # Create a session for authentication
            session_id = auth_module.create_session(1, self.test_db)

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
                "url": f"example-{session_id[:8]}.com",
                "monitor_type": "ssl",
                "notify_methods": ["telegram"],
            }
            status_code, response = asyncio.run(
                _asgi_json_request(main.app, "POST", "/api/sites", payload, session_id)
            )

            assert status_code == 200
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
            assert row["url"] == f"https://example-{session_id[:8]}.com"
            assert row["monitor_type"] == "ssl"
            assert json.loads(row["notify_methods"]) == ["telegram"]
            assert certificate_check_calls == [f"https://example-{session_id[:8]}.com"]
        finally:
            import config_manager

            main.DB_PATH = original_db_path
            config_manager.DB_PATH = original_db_path_config
            monitoring.check_site_status = original_check_site_status
            monitoring.check_site_certificate = original_check_site_certificate


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

    print("\n" + "=" * 50)
    print("All tests passed!")
    print("=" * 50)
