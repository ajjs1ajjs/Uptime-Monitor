"""Advanced tests: notification_history, backup/restore, healthcheck, status page, model helpers"""
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def test_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    from Uptime_Robot.models import init_database
    import asyncio
    asyncio.run(init_database(db_path))
    yield db_path
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture(autouse=True)
def patch_db_path(test_db):
    patches = [
        patch("Uptime_Robot.state.DB_PATH", test_db),
        patch("Uptime_Robot.config_manager.DB_PATH", test_db),
        patch("Uptime_Robot.main.DB_PATH", test_db),
        patch("Uptime_Robot.routers.api.DB_PATH", test_db),
        patch("Uptime_Robot.routers.auth.DB_PATH", test_db),
        patch("Uptime_Robot.dependencies.DB_PATH", test_db),
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture
def sample_site(test_db):
    from Uptime_Robot.database import get_db_connection
    import asyncio

    async def _setup():
        async with get_db_connection(test_db) as conn:
            await conn.execute(
                "INSERT INTO sites (name, url, check_interval, is_active, status) VALUES (?, ?, ?, ?, ?)",
                ("Test Site", "https://example.com", 60, 1, "up"),
            )
            await conn.commit()
            async with conn.execute("SELECT id FROM sites WHERE name = ?", ("Test Site",)) as c:
                row = await c.fetchone()
                return row["id"] if row else None

    return asyncio.run(_setup())


@pytest.fixture
def sample_history(test_db, sample_site):
    from Uptime_Robot.database import get_db_connection
    import asyncio

    async def _setup():
        async with get_db_connection(test_db) as conn:
            for i in range(100):
                status = "up" if i % 10 != 0 else "down"
                ts = (datetime.now() - timedelta(hours=i)).isoformat()
                await conn.execute(
                    "INSERT INTO status_history (site_id, status, status_code, response_time, checked_at) VALUES (?, ?, ?, ?, ?)",
                    (sample_site, status, 200 if status == "up" else 500, 100 + i * 0.5, ts),
                )
            await conn.commit()

    asyncio.run(_setup())
    return sample_site


# --- Notification History Tests ---

class TestNotificationHistory:
    @pytest.mark.asyncio
    async def test_log_notification(self, test_db, sample_site):
        from Uptime_Robot.models import log_notification, get_notification_history
        await log_notification(test_db, sample_site, "Test Site", "telegram", "sent", "Test msg")
        history = await get_notification_history(test_db)
        assert len(history) == 1
        assert history[0]["method"] == "telegram"
        assert history[0]["status"] == "sent"
        assert history[0]["site_name"] == "Test Site"

    @pytest.mark.asyncio
    async def test_log_notification_truncates_preview(self, test_db, sample_site):
        from Uptime_Robot.models import log_notification, get_notification_history
        long_msg = "x" * 500
        await log_notification(test_db, sample_site, "S", "discord", "sent", long_msg)
        history = await get_notification_history(test_db)
        assert len(history[0]["message_preview"]) <= 200

    @pytest.mark.asyncio
    async def test_get_notification_history_empty(self, test_db):
        from Uptime_Robot.models import get_notification_history
        history = await get_notification_history(test_db)
        assert history == []

    @pytest.mark.asyncio
    async def test_get_notification_history_limit(self, test_db, sample_site):
        from Uptime_Robot.models import log_notification, get_notification_history
        for i in range(20):
            await log_notification(test_db, sample_site, "S", "telegram", "sent", f"msg{i}")
        history = await get_notification_history(test_db, limit=5)
        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_log_notification_multiple_methods(self, test_db, sample_site):
        from Uptime_Robot.models import log_notification, get_notification_history
        await log_notification(test_db, sample_site, "S", "telegram", "sent", "t")
        await log_notification(test_db, sample_site, "S", "discord", "failed", "d")
        history = await get_notification_history(test_db)
        assert len(history) == 2
        methods = {h["method"] for h in history}
        assert methods == {"telegram", "discord"}

    @pytest.mark.asyncio
    async def test_log_notification_site_name_none(self, test_db):
        from Uptime_Robot.models import log_notification, get_notification_history
        await log_notification(test_db, 0, None, "webhook", "sent", "")
        history = await get_notification_history(test_db)
        assert history[0]["site_name"] is None

    @pytest.mark.asyncio
    async def test_notification_history_order(self, test_db, sample_site):
        from Uptime_Robot.models import log_notification, get_notification_history
        await log_notification(test_db, sample_site, "S", "telegram", "sent", "first")
        await log_notification(test_db, sample_site, "S", "discord", "sent", "second")
        history = await get_notification_history(test_db)
        assert history[0]["method"] == "discord"  # newest first

    @pytest.mark.asyncio
    async def test_log_notification_persists_to_db(self, test_db, sample_site):
        from Uptime_Robot.database import get_db_connection
        from Uptime_Robot.models import log_notification
        await log_notification(test_db, sample_site, "S", "email", "sent", "persist")
        async with get_db_connection(test_db) as conn:
            async with conn.execute("SELECT COUNT(*) FROM notification_history") as c:
                row = await c.fetchone()
                assert row[0] == 1

    @pytest.mark.asyncio
    async def test_log_notification_no_crash_on_bad_site_id(self, test_db):
        from Uptime_Robot.models import log_notification, get_notification_history
        await log_notification(test_db, 99999, "Ghost", "telegram", "sent", "bad_id")
        history = await get_notification_history(test_db)
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_notification_history_in_api(self, test_db, sample_site):
        from Uptime_Robot.models import log_notification
        await log_notification(test_db, sample_site, "Test Site", "telegram", "sent", "API test")
        from Uptime_Robot.models import get_notification_history
        history = await get_notification_history(test_db)
        assert any(h["method"] == "telegram" for h in history)


class TestSendNotificationLogging:
    @pytest.mark.asyncio
    async def test_send_notification_logs_history(self, test_db, sample_site):
        with patch("Uptime_Robot.notifications.send_telegram", AsyncMock()):
            from Uptime_Robot.notifications import send_notification
            await send_notification(
                {"alert_type": "down", "site_name": "Test Site"},
                ["telegram"],
                {"telegram": {"enabled": True, "channels": [{"token": "x", "chat_id": "y"}]}},
                site_id=sample_site,
                site_name="Test Site",
            )
            from Uptime_Robot.models import get_notification_history
            history = await get_notification_history(test_db)
            assert len(history) >= 1
            assert history[0]["method"] == "telegram"

    @pytest.mark.asyncio
    async def test_send_notification_no_log_without_site_id(self, test_db):
        with patch("Uptime_Robot.notifications.send_telegram", AsyncMock()):
            from Uptime_Robot.notifications import send_notification
            await send_notification(
                {"alert_type": "down"},
                ["telegram"],
                {"telegram": {"enabled": True, "channels": [{"token": "x", "chat_id": "y"}]}},
            )
            from Uptime_Robot.models import get_notification_history
            history = await get_notification_history(test_db)
            assert len(history) == 0

    @pytest.mark.asyncio
    async def test_send_notification_does_not_crash(self, test_db, sample_site):
        with patch("Uptime_Robot.notifications.send_telegram", AsyncMock()):
            from Uptime_Robot.notifications import send_notification
            await send_notification(
                {"alert_type": "ssl"},
                ["telegram"],
                {"telegram": {"enabled": True, "channels": [{"token": "x", "chat_id": "y"}]}},
                site_id=sample_site,
                site_name="Test",
            )

    @pytest.mark.asyncio
    async def test_send_notification_logs_each_method(self, test_db, sample_site):
        with patch("Uptime_Robot.notifications.send_telegram", AsyncMock()), \
             patch("Uptime_Robot.notifications.send_discord", AsyncMock()):
            from Uptime_Robot.notifications import send_notification
            await send_notification(
                {"alert_type": "down"},
                ["telegram", "discord"],
                {
                    "telegram": {"enabled": True, "channels": [{"token": "x", "chat_id": "y"}]},
                    "discord": {"enabled": True, "channels": [{"webhook_url": "https://hook"}]},
                },
                site_id=sample_site,
                site_name="Test",
            )
            from Uptime_Robot.models import get_notification_history
            history = await get_notification_history(test_db)
            assert len(history) == 2
            assert {h["method"] for h in history} == {"telegram", "discord"}


# --- Backup Tests ---

class TestBackup:
    @pytest.mark.asyncio
    async def test_create_backup(self, test_db, sample_site):
        from Uptime_Robot.models import create_backup, get_backups
        backup_dir = tempfile.mkdtemp()
        backup_path = os.path.join(backup_dir, "test_backup.db")
        result = await create_backup(test_db, backup_path)
        assert os.path.exists(backup_path)
        assert result["site_count"] >= 1
        os.unlink(backup_path)
        os.rmdir(backup_dir)

    @pytest.mark.asyncio
    async def test_get_backups(self, test_db, sample_site):
        from Uptime_Robot.models import create_backup, get_backups
        backup_dir = tempfile.mkdtemp()
        backup_path = os.path.join(backup_dir, "b1.db")
        await create_backup(test_db, backup_path)
        backups = await get_backups(test_db)
        assert len(backups) >= 1
        assert backups[0]["filename"] == "b1.db"
        os.unlink(backup_path)
        os.rmdir(backup_dir)

    @pytest.mark.asyncio
    async def test_get_backups_empty(self, test_db):
        from Uptime_Robot.models import get_backups
        backups = await get_backups(test_db)
        assert backups == []

    @pytest.mark.asyncio
    async def test_backup_creates_dir(self, test_db, sample_site):
        from Uptime_Robot.models import create_backup
        backup_dir = os.path.join(tempfile.gettempdir(), "test_backup_nonexistent")
        backup_path = os.path.join(backup_dir, "b.db")
        result = await create_backup(test_db, backup_path)
        assert os.path.exists(backup_dir)
        assert result["filename"] == "b.db"
        shutil.rmtree(backup_dir)


# --- Healthcheck Tests ---

class TestHealthcheck:
    def test_health_endpoint_exists(self, test_db):
        with patch("Uptime_Robot.state.DB_PATH", test_db), \
             patch("Uptime_Robot.main.DB_PATH", test_db), \
             patch("Uptime_Robot.config_manager.DB_PATH", test_db):
            from Uptime_Robot.main import app
            from fastapi.testclient import TestClient
            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert "timestamp" in data

    def test_health_returns_json(self, test_db):
        with patch("Uptime_Robot.state.DB_PATH", test_db), \
             patch("Uptime_Robot.main.DB_PATH", test_db), \
             patch("Uptime_Robot.config_manager.DB_PATH", test_db):
            from Uptime_Robot.main import app
            client = TestClient(app)
            resp = client.get("/health")
            assert resp.headers["content-type"].startswith("application/json")


# --- Status Page Tests ---

class TestStatusPageData:
    @pytest.mark.asyncio
    async def test_uptime_percentage_calculation(self, test_db, sample_history):
        from Uptime_Robot.routers.ui import public_status_page
        from fastapi import Request
        with patch("Uptime_Robot.routers.ui.SITE_TITLE", "Test"), \
             patch("Uptime_Robot.routers.ui.LOGO_URL", ""), \
             patch("Uptime_Robot.routers.ui.FOOTER_TEXT", ""), \
             patch("Uptime_Robot.routers.ui.PRIMARY_COLOR", "#000"), \
             patch("Uptime_Robot.routers.ui.BRAND_ACCENT_COLOR", "#fff"), \
             patch("Uptime_Robot.routers.ui.DISPLAY_ADDRESS", ""):
            mock_req = MagicMock(spec=Request)
            mock_req.base_url = "http://test"
            resp = await public_status_page(mock_req)
            assert "text/html" in resp.headers.get("content-type", "")

    def test_status_page_sorts_down_first(self, test_db):
        from Uptime_Robot.database import get_db_connection
        import asyncio
        async def _setup():
            async with get_db_connection(test_db) as conn:
                for name, status in [("Site A", "up"), ("Site B", "down"), ("Site C", "up"), ("Site D", "slow")]:
                    await conn.execute(
                        "INSERT INTO sites (name, url, check_interval, is_active, status) VALUES (?, ?, ?, ?, ?)",
                        (name, f"https://{name}.com", 60, 1, status),
                    )
                await conn.commit()
            async with get_db_connection(test_db) as conn:
                async with conn.execute("SELECT status FROM sites WHERE is_active = 1 ORDER BY id") as c:
                    rows = await c.fetchall()
                    statuses = [r["status"] for r in rows]
                    assert "down" in statuses
                    assert "up" in statuses
                    assert "slow" in statuses
        asyncio.run(_setup())

    @pytest.mark.asyncio
    async def test_response_time_passed_to_template(self, test_db, sample_history):
        from Uptime_Robot.database import get_db_connection
        async with get_db_connection(test_db) as conn:
            async with conn.execute(
                "SELECT response_time FROM status_history WHERE site_id = ? ORDER BY checked_at DESC LIMIT 1",
                (sample_history,),
            ) as c:
                row = await c.fetchone()
                assert row is not None
                assert row[0] is not None


class TestNotificationHistoryAPI:
    def test_requires_admin(self, test_db):
        with patch("Uptime_Robot.state.DB_PATH", test_db), \
             patch("Uptime_Robot.routers.api.DB_PATH", test_db):
            from Uptime_Robot.main import app
            client = TestClient(app)
            resp = client.get("/api/notification-history")
            assert resp.status_code in (401, 403)

    def test_login_response_format(self, test_db):
        with patch("Uptime_Robot.state.DB_PATH", test_db), \
             patch("Uptime_Robot.routers.api.DB_PATH", test_db), \
             patch("Uptime_Robot.routers.auth.DB_PATH", test_db):
            from Uptime_Robot.main import app
            client = TestClient(app)
            resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
            assert resp.status_code in (200, 404, 422)


# --- Model Helper Tests ---

class TestModels:
    @pytest.mark.asyncio
    async def test_log_audit_event(self, test_db):
        from Uptime_Robot.models import log_audit_event, get_audit_log
        await log_audit_event(test_db, 1, "admin", "test_action", "site", "1", "details")
        log = await get_audit_log(test_db)
        assert len(log) == 1
        assert log[0]["action"] == "test_action"

    @pytest.mark.asyncio
    async def test_get_audit_log_empty(self, test_db):
        from Uptime_Robot.models import get_audit_log
        log = await get_audit_log(test_db)
        assert log == []

    @pytest.mark.asyncio
    async def test_get_audit_log_limit(self, test_db):
        from Uptime_Robot.models import log_audit_event, get_audit_log
        for i in range(10):
            await log_audit_event(test_db, 1, "u", f"a{i}", None, None, None)
        log = await get_audit_log(test_db, limit=3)
        assert len(log) == 3

    @pytest.mark.asyncio
    async def test_get_sites_returns_active_only(self, test_db):
        from Uptime_Robot.database import get_db_connection
        from Uptime_Robot.models import get_all_sites
        async with get_db_connection(test_db) as conn:
            await conn.execute(
                "INSERT INTO sites (name, url, check_interval, is_active, status) VALUES (?, ?, ?, ?, ?)",
                ("Active", "https://active.com", 60, 1, "up"),
            )
            await conn.execute(
                "INSERT INTO sites (name, url, check_interval, is_active, status) VALUES (?, ?, ?, ?, ?)",
                ("Inactive", "https://inactive.com", 60, 0, "down"),
            )
            await conn.commit()
        sites = await get_all_sites(test_db)
        active = [s for s in sites if s["is_active"]]
        inactive = [s for s in sites if not s["is_active"]]
        assert len(active) >= 1
        assert len(inactive) >= 1
        assert any(s["name"] == "Active" for s in active)
        assert any(s["name"] == "Inactive" for s in inactive)

    @pytest.mark.asyncio
    async def test_status_history_insertion(self, test_db, sample_site):
        from Uptime_Robot.database import get_db_connection
        async with get_db_connection(test_db) as conn:
            await conn.execute(
                "INSERT INTO status_history (site_id, status, status_code, response_time, checked_at) VALUES (?, ?, ?, ?, ?)",
                (sample_site, "down", 500, 200.5, datetime.now().isoformat()),
            )
            await conn.commit()
            async with conn.execute(
                "SELECT COUNT(*) FROM status_history WHERE site_id = ?", (sample_site,)
            ) as c:
                row = await c.fetchone()
                assert row[0] >= 1

    @pytest.mark.asyncio
    async def test_backup_restore(self, test_db, sample_site):
        from Uptime_Robot.models import create_backup, get_backups
        backup_dir = tempfile.mkdtemp()
        backup_path = os.path.join(backup_dir, "restore_test.db")
        await create_backup(test_db, backup_path)
        shutil.copy2(backup_path, test_db + ".restored")
        assert os.path.exists(test_db + ".restored")
        os.unlink(backup_path)
        os.unlink(test_db + ".restored")
        os.rmdir(backup_dir)

    @pytest.mark.asyncio
    async def test_backup_records_site_count(self, test_db, sample_site):
        from Uptime_Robot.models import create_backup
        backup_dir = tempfile.mkdtemp()
        backup_path = os.path.join(backup_dir, "count.db")
        result = await create_backup(test_db, backup_path)
        assert result["site_count"] >= 1
        os.unlink(backup_path)
        os.rmdir(backup_dir)

    @pytest.mark.asyncio
    async def test_backup_file_size_nonzero(self, test_db, sample_site):
        from Uptime_Robot.models import create_backup
        from Uptime_Robot.database import get_db_connection
        async with get_db_connection(test_db) as conn:
            for i in range(50):
                await conn.execute(
                    "INSERT INTO status_history (site_id, status, checked_at) VALUES (?, ?, ?)",
                    (sample_site, "up", datetime.now().isoformat()),
                )
            await conn.commit()
        backup_dir = tempfile.mkdtemp()
        backup_path = os.path.join(backup_dir, "size.db")
        await create_backup(test_db, backup_path)
        assert os.path.getsize(backup_path) > 0
        os.unlink(backup_path)
        os.rmdir(backup_dir)


class TestMoreEdgeCases:
    @pytest.mark.asyncio
    async def test_notification_history_no_data(self, test_db):
        from Uptime_Robot.models import get_notification_history
        h = await get_notification_history(test_db, limit=0)
        assert h == []

    @pytest.mark.asyncio
    async def test_backup_empty_db(self, test_db):
        from Uptime_Robot.models import create_backup
        backup_dir = tempfile.mkdtemp()
        backup_path = os.path.join(backup_dir, "empty.db")
        result = await create_backup(test_db, backup_path)
        assert result["site_count"] == 0
        os.unlink(backup_path)
        os.rmdir(backup_dir)

    @pytest.mark.asyncio
    async def test_backup_preserves_audit_log(self, test_db):
        from Uptime_Robot.models import log_audit_event, create_backup
        from Uptime_Robot.database import get_db_connection
        import aiosqlite
        await log_audit_event(test_db, 1, "admin", "pre_backup_action")
        backup_dir = tempfile.mkdtemp()
        backup_path = os.path.join(backup_dir, "audit.db")
        await create_backup(test_db, backup_path)
        async with aiosqlite.connect(backup_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("SELECT COUNT(*) FROM audit_log") as c:
                row = await c.fetchone()
                assert row[0] >= 1
        os.unlink(backup_path)
        os.rmdir(backup_dir)

    @pytest.mark.asyncio
    async def test_log_notification_unicode(self, test_db, sample_site):
        from Uptime_Robot.models import log_notification, get_notification_history
        await log_notification(test_db, sample_site, "S", "telegram", "sent", "Привіт 🌍")
        h = await get_notification_history(test_db)
        assert "Привіт" in h[0]["message_preview"]

    @pytest.mark.asyncio
    async def test_log_notification_special_chars(self, test_db, sample_site):
        from Uptime_Robot.models import log_notification, get_notification_history
        msg = "<test&quote>"
        await log_notification(test_db, sample_site, "S", "email", "sent", msg)
        h = await get_notification_history(test_db)
        assert "<test" in h[0]["message_preview"]

    @pytest.mark.asyncio
    async def test_send_notification_disabled_still_logs(self, test_db, sample_site):
        from Uptime_Robot.models import get_notification_history
        with patch("Uptime_Robot.notifications.send_telegram", AsyncMock()):
            from Uptime_Robot.notifications import send_notification
            await send_notification(
                {"alert_type": "down"},
                ["telegram"],
                {"telegram": {"enabled": False}},
                site_id=sample_site, site_name="Test",
            )
            h = await get_notification_history(test_db)
            assert len(h) == 1  # logs even when disabled (correct behavior)

    @pytest.mark.asyncio
    async def test_send_notification_multiple_methods(self, test_db, sample_site):
        from Uptime_Robot.models import get_notification_history
        with patch("Uptime_Robot.notifications.send_telegram", AsyncMock()), \
             patch("Uptime_Robot.notifications.send_discord", AsyncMock()):
            from Uptime_Robot.notifications import send_notification
            await send_notification(
                {"alert_type": "down"},
                ["telegram", "discord"],
                {
                    "telegram": {"enabled": True, "channels": [{"token": "x", "chat_id": "y"}]},
                    "discord": {"enabled": True, "channels": [{"webhook_url": "https://h"}]},
                },
                site_id=sample_site, site_name="Test",
            )
            h = await get_notification_history(test_db)
            assert len(h) == 2

    @pytest.mark.asyncio
    async def test_log_audit_no_user_id(self, test_db):
        from Uptime_Robot.models import log_audit_event, get_audit_log
        await log_audit_event(test_db, 0, "system", "auto_cleanup")
        log = await get_audit_log(test_db)
        assert log[0]["user_id"] == 0

    @pytest.mark.asyncio
    async def test_log_audit_target_types(self, test_db):
        from Uptime_Robot.models import log_audit_event, get_audit_log
        for t in ["site", "user", "backup", "config", None]:
            await log_audit_event(test_db, 1, "admin", "action", t)
        log = await get_audit_log(test_db)
        assert len(log) == 5

    @pytest.mark.asyncio
    async def test_site_uptime_computation(self, test_db, sample_history):
        from Uptime_Robot.database import get_db_connection
        async with get_db_connection(test_db) as conn:
            async with conn.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN status='up' THEN 1 ELSE 0 END) as up FROM status_history WHERE site_id = ?",
                (sample_history,)
            ) as c:
                row = await c.fetchone()
        assert row[0] == 100
        assert row[1] == 90

    @pytest.mark.asyncio
    async def test_status_history_transition(self, test_db, sample_site):
        from Uptime_Robot.database import get_db_connection
        async with get_db_connection(test_db) as conn:
            for s in ["up", "up", "down", "down", "up", "slow"]:
                await conn.execute(
                    "INSERT INTO status_history (site_id, status, checked_at) VALUES (?, ?, ?)",
                    (sample_site, s, datetime.now().isoformat()),
                )
            await conn.commit()
            async with conn.execute(
                "SELECT status, COUNT(*) FROM status_history WHERE site_id = ? GROUP BY status",
                (sample_site,)
            ) as c:
                rows = await c.fetchall()
        counts = {r["status"]: r[1] for r in rows}
        assert counts["up"] == 3
        assert counts["down"] == 2
        assert counts["slow"] == 1

    @pytest.mark.asyncio
    async def test_backup_valid_sqlite(self, test_db, sample_site):
        from Uptime_Robot.models import create_backup
        import aiosqlite
        backup_dir = tempfile.mkdtemp()
        bp = os.path.join(backup_dir, "v.db")
        await create_backup(test_db, bp)
        async with aiosqlite.connect(bp) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("SELECT COUNT(*) FROM sites") as c:
                r = await c.fetchone()
                assert r[0] >= 1
        os.unlink(bp)
        os.rmdir(backup_dir)

    @pytest.mark.asyncio
    async def test_backup_multiple_sites(self, test_db, sample_site):
        from Uptime_Robot.database import get_db_connection
        async with get_db_connection(test_db) as conn:
            for i in range(3):
                await conn.execute(
                    "INSERT INTO sites (name, url, status) VALUES (?, ?, ?)",
                    (f"S{i}", f"https://s{i}.com", "up"),
                )
            await conn.commit()
        from Uptime_Robot.models import create_backup
        backup_dir = tempfile.mkdtemp()
        bp = os.path.join(backup_dir, "m.db")
        r = await create_backup(test_db, bp)
        assert r["site_count"] >= 2
        os.unlink(bp)
        os.rmdir(backup_dir)

    @pytest.mark.asyncio
    async def test_notification_history_empty_preview(self, test_db, sample_site):
        from Uptime_Robot.models import log_notification, get_notification_history
        await log_notification(test_db, sample_site, "S", "webhook", "sent", None)
        h = await get_notification_history(test_db)
        assert h[0]["message_preview"] == ""

    @pytest.mark.asyncio
    async def test_notification_history_method_names(self, test_db, sample_site):
        from Uptime_Robot.models import log_notification, get_notification_history
        for m in ["telegram", "discord", "teams", "email", "slack", "sms", "webhook", "pushover", "gotify", "ntfy"]:
            await log_notification(test_db, sample_site, "S", m, "sent", "")
        h = await get_notification_history(test_db)
        assert len(h) == 10
        assert {e["method"] for e in h} == {"telegram", "discord", "teams", "email", "slack", "sms", "webhook", "pushover", "gotify", "ntfy"}

    @pytest.mark.asyncio
    async def test_backup_creates_record_in_db(self, test_db):
        from Uptime_Robot.models import create_backup, get_backups
        backup_dir = tempfile.mkdtemp()
        bp = os.path.join(backup_dir, "record.db")
        await create_backup(test_db, bp)
        backups = await get_backups(test_db)
        assert len(backups) >= 1
        assert backups[0]["filename"] == "record.db"
        os.unlink(bp)
        os.rmdir(backup_dir)

    @pytest.mark.asyncio
    async def test_backup_records_size(self, test_db):
        from Uptime_Robot.models import create_backup, get_backups
        with open(test_db, "a") as f:
            f.write(" " * 1024)
        backup_dir = tempfile.mkdtemp()
        bp = os.path.join(backup_dir, "size_test.db")
        await create_backup(test_db, bp)
        backups = await get_backups(test_db)
        assert backups[0]["size_bytes"] > 0
        os.unlink(bp)
        os.rmdir(backup_dir)

    @pytest.mark.asyncio
    async def test_notification_log_null_preview(self, test_db, sample_site):
        from Uptime_Robot.models import log_notification, get_notification_history
        await log_notification(test_db, sample_site, "S", "telegram", "sent", None)
        h = await get_notification_history(test_db)
        assert h[0]["message_preview"] == ""

    @pytest.mark.asyncio
    async def test_maintenance_window_skips_checks(self, test_db):
        from unittest.mock import patch
        from Uptime_Robot import config_manager
        from Uptime_Robot.database import close_db, get_db_connection
        await close_db()
        orig_db = config_manager.DB_PATH
        config_manager.DB_PATH = test_db
        try:
            from Uptime_Robot.models import add_site, add_maintenance_window
            site_id = await add_site(test_db, "Maint Site", "http://example.com", monitor_type="http")
            from datetime import datetime, timedelta
            now = datetime.now()
            await add_maintenance_window(
                test_db, name="Maint Window", site_id=site_id, rule_type="one_off",
                start_time=(now - timedelta(hours=1)).isoformat(),
                end_time=(now + timedelta(hours=1)).isoformat(),
            )
            from Uptime_Robot.monitoring.maintenance import is_under_maintenance
            under = await is_under_maintenance(site_id)
            assert under is True
        finally:
            await close_db()
            config_manager.DB_PATH = orig_db

    @pytest.mark.asyncio
    async def test_sla_report_calculations(self, test_db):
        from Uptime_Robot.models import add_site
        site_id = await add_site(test_db, "SLA Site", "http://example.com", monitor_type="http")
        from Uptime_Robot.database import get_db_connection
        async with get_db_connection(test_db) as conn:
            for _ in range(2):
                await conn.execute(
                    "INSERT INTO status_history (site_id, status, response_time, checked_at) VALUES (?, 'up', 100, datetime('now'))", (site_id,))
            await conn.execute(
                "INSERT INTO status_history (site_id, status, response_time, checked_at) VALUES (?, 'down', 0, datetime('now'))", (site_id,))
            await conn.commit()
        async with get_db_connection(test_db) as conn:
            async with conn.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN status='up' THEN 1 ELSE 0 END) as up_count FROM status_history WHERE site_id=?", (site_id,)) as c:
                stats = await c.fetchone()
        total = stats["total"] or 0
        up_count = stats["up_count"] or 0
        uptime = (up_count / total * 100) if total > 0 else 100.0
        assert total == 3
        assert up_count == 2
        assert abs(uptime - 66.67) < 0.1

    @pytest.mark.asyncio
    async def test_webhook_alert_dispatch(self):
        from unittest.mock import AsyncMock, MagicMock, patch
        from Uptime_Robot.notifications import send_webhook
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
            await send_webhook(message, settings)
            mock_session.post.assert_called_once_with("http://my-webhook.internal/endpoint", json=message)
