import asyncio
import os
import sqlite3
import tempfile

import pytest

from Uptime_Robot.database import get_db_connection
from Uptime_Robot.models import init_database


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass

@pytest.mark.asyncio
async def test_no_seeding_by_default_in_tests(temp_db):
    # By default, during tests, seeding should NOT run
    if "FORCE_DB_SEED" in os.environ:
        del os.environ["FORCE_DB_SEED"]
    
    await init_database(temp_db)
    
    async with get_db_connection(temp_db) as conn:
        async with conn.execute("SELECT COUNT(*) FROM sites") as c:
            row = await c.fetchone()
            count = row[0]
    
    assert count == 0

@pytest.mark.asyncio
async def test_seeding_from_json_file(temp_db, monkeypatch):
    # Enable force seed
    monkeypatch.setenv("FORCE_DB_SEED", "True")
    
    # Run database initialization
    await init_database(temp_db)
    
    async with get_db_connection(temp_db) as conn:
        async with conn.execute("SELECT * FROM sites") as c:
            rows = await c.fetchall()
            sites = [dict(r) for r in rows]
            
    # There should be seeded sites from default_sites.json (26 sites)
    assert len(sites) == 26
    # Check one of the known default sites
    urls = {s["url"] for s in sites}
    assert "https://diia-sign.it.ua/health" in urls

@pytest.mark.asyncio
async def test_seeding_from_env_variable_comma_separated(temp_db, monkeypatch):
    monkeypatch.setenv("FORCE_DB_SEED", "True")
    # Temporarily hide/mock default_sites.json path or make sure we only add from env
    # Wait, we can test env seeding by adding new URLs. Because it runs INSERT OR IGNORE,
    # it will add the env ones too.
    # Let's set UPTIME_MONITOR_URL to a comma-separated list
    monkeypatch.setenv("UPTIME_MONITOR_URL", "https://custom1.com,https://custom2.com;https://custom3.com")
    
    await init_database(temp_db)
    
    async with get_db_connection(temp_db) as conn:
        async with conn.execute("SELECT * FROM sites") as c:
            rows = await c.fetchall()
            sites = [dict(r) for r in rows]
            
    urls = {s["url"] for s in sites}
    assert "https://custom1.com" in urls
    assert "https://custom2.com" in urls
    assert "https://custom3.com" in urls
    # Should also include the 26 default ones from JSON, so total 29
    assert len(sites) == 29

@pytest.mark.asyncio
async def test_seeding_from_env_variable_json_array(temp_db, monkeypatch):
    monkeypatch.setenv("FORCE_DB_SEED", "True")
    # Test JSON array format in env variable
    env_json = '[{"name": "Custom JSON Site", "url": "https://custom-json.com", "check_interval": 120}]'
    monkeypatch.setenv("UPTIME_MONITOR_URLS", env_json)
    
    await init_database(temp_db)
    
    async with get_db_connection(temp_db) as conn:
        async with conn.execute("SELECT * FROM sites WHERE url = ?", ("https://custom-json.com",)) as c:
            site = await c.fetchone()
            
    assert site is not None
    assert site["name"] == "Custom JSON Site"
    assert site["check_interval"] == 120

@pytest.mark.asyncio
async def test_seeding_telegram_notifications(temp_db, monkeypatch):
    import json
    monkeypatch.setenv("FORCE_DB_SEED", "True")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "12345:fake_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001234567")
    
    await init_database(temp_db)

    from Uptime_Robot.models import load_notify_settings

    async with get_db_connection(temp_db) as conn:
        async with conn.execute("SELECT config FROM notify_config WHERE id = 1") as c:
            row = await c.fetchone()
            assert row is not None
            config = json.loads(row["config"])
            assert config["telegram"]["enabled"] is True
            # Secret must be encrypted at rest, not stored as plaintext
            stored_token = config["telegram"]["channels"][0]["token"]
            assert stored_token != "12345:fake_token"
            assert stored_token.startswith("__ENC__")
            assert config["telegram"]["channels"][0]["chat_id"] == "-1001234567"

    # load_notify_settings must transparently decrypt the token back
    settings = await load_notify_settings(temp_db)
    assert settings["telegram"]["channels"][0]["token"] == "12345:fake_token"

    async with get_db_connection(temp_db) as conn:
        # Also check that seeded sites have "telegram" in notify_methods
        async with conn.execute("SELECT notify_methods FROM sites LIMIT 1") as c:
            row = await c.fetchone()
            assert row is not None
            notify_methods = json.loads(row["notify_methods"])
            assert "telegram" in notify_methods
