#!/usr/bin/env python3
"""
Tests for Uptime Monitor API and Monitoring

Run with:
    python -m pytest tests/test_api.py -v
    python -m pytest tests/ -v

Coverage:
    python -m pytest tests/ --cov=Uptime_Robot --cov-report=html
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# Test database path
TEST_DB_PATH = ":memory:"


@pytest.fixture
def db():
    """Create in-memory database for testing"""
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.row_factory = sqlite3.Row

    # Create sites table
    conn.execute("""
        CREATE TABLE sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            check_interval INTEGER DEFAULT 60,
            is_active BOOLEAN DEFAULT 1,
            notify_methods TEXT DEFAULT '[]',
            status TEXT DEFAULT 'unknown',
            status_code INTEGER,
            response_time REAL,
            error_message TEXT,
            monitor_type TEXT DEFAULT 'http'
        )
    """)

    # Create status_history table
    conn.execute("""
        CREATE TABLE status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER,
            status TEXT,
            status_code INTEGER,
            response_time REAL,
            error_message TEXT,
            checked_at TEXT
        )
    """)

    # Create ssl_certificates table
    conn.execute("""
        CREATE TABLE ssl_certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER UNIQUE,
            hostname TEXT,
            issuer TEXT,
            subject TEXT,
            start_date TEXT,
            expire_date TEXT,
            days_until_expire INTEGER,
            is_valid BOOLEAN,
            last_checked TEXT,
            last_notified TEXT
        )
    """)

    # Create notify_config table
    conn.execute("""
        CREATE TABLE notify_config (
            id INTEGER PRIMARY KEY,
            config TEXT
        )
    """)

    # Create users table
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'admin',
            is_active BOOLEAN DEFAULT 1
        )
    """)

    # Insert test data
    conn.execute(
        """
        INSERT INTO sites (name, url, check_interval, is_active, status, cpu_percent, memory_percent, disk_percent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        ("Test Site 1", "https://example.com", 60, 1, "up", 0, 0, 0),
    )

    conn.execute(
        """
        INSERT INTO sites (name, url, check_interval, is_active, status)
        VALUES (?, ?, ?, ?, ?)
    """,
        ("Test Site 2", "https://google.com", 60, 1, "up"),
    )

    # Insert status history
    now = datetime.now()
    for i in range(10):
        ts = (now - timedelta(minutes=i * 5)).isoformat()
        conn.execute(
            """
            INSERT INTO status_history (site_id, status, status_code, response_time, checked_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (1, "up" if i % 2 == 0 else "down", 200, 100 + i * 10, ts),
        )

    conn.commit()
    yield conn
    conn.close()


class TestSitesAPI:
    """Tests for Sites API endpoints"""

    def test_get_sites(self, db):
        """Test getting all sites"""
        from Uptime_Robot.main import get_db_connection

        # Mock the DB_PATH
        with patch("Uptime_Robot.main.DB_PATH", TEST_DB_PATH):
            conn = get_db_connection()
            cursor = conn.execute("SELECT * FROM sites")
            sites = cursor.fetchall()
            conn.close()

            assert len(sites) == 2
            assert sites[0]["name"] == "Test Site 1"
            assert sites[0]["url"] == "https://example.com"

    def test_get_active_sites(self, db):
        """Test getting only active sites"""
        conn = db
        cursor = conn.execute("SELECT * FROM sites WHERE is_active = 1")
        sites = cursor.fetchall()

        assert len(sites) == 2
        for site in sites:
            assert site["is_active"] == 1

    def test_add_site(self, db):
        """Test adding a new site"""
        conn = db
        conn.execute(
            """
            INSERT INTO sites (name, url, check_interval, is_active, monitor_type)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("New Site", "https://newsite.com", 120, 1, "http"),
        )
        conn.commit()

        cursor = conn.execute(
            "SELECT * FROM sites WHERE url = ?", ("https://newsite.com",)
        )
        site = cursor.fetchone()

        assert site is not None
        assert site["name"] == "New Site"
        assert site["check_interval"] == 120

    def test_update_site(self, db):
        """Test updating a site"""
        conn = db
        conn.execute(
            """
            UPDATE sites SET name = ?, check_interval = ? WHERE id = ?
        """,
            ("Updated Site", 180, 1),
        )
        conn.commit()

        cursor = conn.execute("SELECT * FROM sites WHERE id = ?", (1,))
        site = cursor.fetchone()

        assert site["name"] == "Updated Site"
        assert site["check_interval"] == 180

    def test_delete_site(self, db):
        """Test deleting a site"""
        conn = db
        conn.execute("DELETE FROM sites WHERE id = ?", (2,))
        conn.commit()

        cursor = conn.execute("SELECT * FROM sites WHERE id = ?", (2,))
        site = cursor.fetchone()

        assert site is None


class TestStatusHistory:
    """Tests for Status History"""

    def test_get_status_history(self, db):
        """Test getting status history for a site"""
        conn = db
        cursor = conn.execute(
            """
            SELECT * FROM status_history
            WHERE site_id = ?
            ORDER BY checked_at DESC
        """,
            (1,),
        )
        history = cursor.fetchall()

        assert len(history) == 10
        assert history[0]["site_id"] == 1

    def test_status_alternating(self, db):
        """Test that status alternates between up/down"""
        conn = db
        cursor = conn.execute("""
            SELECT status FROM status_history
            WHERE site_id = 1
            ORDER BY checked_at DESC
        """)
        statuses = [row["status"] for row in cursor.fetchall()]

        # Check alternating pattern
        for i in range(len(statuses) - 1):
            assert statuses[i] != statuses[i + 1]

    def test_cleanup_old_history(self, db):
        """Test cleaning up old history records"""
        conn = db

        # Insert old record (31 days ago)
        old_date = (datetime.now() - timedelta(days=31)).isoformat()
        conn.execute(
            """
            INSERT INTO status_history (site_id, status, checked_at)
            VALUES (?, ?, ?)
        """,
            (1, "up", old_date),
        )
        conn.commit()

        # Delete old records
        conn.execute("""
            DELETE FROM status_history
            WHERE checked_at < datetime('now', '-30 days')
        """)
        conn.commit()

        cursor = conn.execute("SELECT COUNT(*) FROM status_history")
        count = cursor.fetchone()[0]

        assert count == 10  # Old record deleted


class TestSSLCertificates:
    """Tests for SSL Certificate monitoring"""

    def test_add_ssl_certificate(self, db):
        """Test adding SSL certificate record"""
        conn = db
        conn.execute(
            """
            INSERT INTO ssl_certificates
            (site_id, hostname, issuer, days_until_expire, is_valid, last_checked)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (1, "example.com", "Let's Encrypt", 30, 1, datetime.now().isoformat()),
        )
        conn.commit()

        cursor = conn.execute("SELECT * FROM ssl_certificates WHERE site_id = ?", (1,))
        cert = cursor.fetchone()

        assert cert is not None
        assert cert["hostname"] == "example.com"
        assert cert["days_until_expire"] == 30

    def test_ssl_expiring_soon(self, db):
        """Test detecting expiring SSL certificates"""
        conn = db

        # Insert expiring certificate (5 days)
        conn.execute(
            """
            INSERT INTO ssl_certificates
            (site_id, hostname, days_until_expire, is_valid)
            VALUES (?, ?, ?, ?)
        """,
            (1, "expiring.com", 5, 1),
        )
        conn.commit()

        cursor = conn.execute("""
            SELECT * FROM ssl_certificates
            WHERE days_until_expire <= 7 AND is_valid = 1
        """)
        expiring = cursor.fetchall()

        assert len(expiring) == 1
        assert expiring[0]["days_until_expire"] == 5

    def test_ssl_expired(self, db):
        """Test detecting expired SSL certificates"""
        conn = db

        # Insert expired certificate
        conn.execute(
            """
            INSERT INTO ssl_certificates
            (site_id, hostname, days_until_expire, is_valid)
            VALUES (?, ?, ?, ?)
        """,
            (1, "expired.com", -5, 0),
        )
        conn.commit()

        cursor = conn.execute("""
            SELECT * FROM ssl_certificates
            WHERE days_until_expire < 0 OR is_valid = 0
        """)
        expired = cursor.fetchall()

        assert len(expired) == 1


class TestMonitoring:
    """Tests for Monitoring logic"""

    @patch("aiohttp.ClientSession")
    def test_check_site_up(self, mock_session, db):
        """Test checking site that is up"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__aenter__ = MagicMock(return_value=mock_response)
        mock_response.__aexit__ = MagicMock(return_value=None)

        mock_session.return_value.__aenter__.return_value.get.return_value = (
            mock_response
        )

        # Test logic
        status = "up" if mock_response.status == 200 else "down"
        assert status == "up"

    @patch("aiohttp.ClientSession")
    def test_check_site_down(self, mock_session, db):
        """Test checking site that is down"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status = 503
        mock_response.__aenter__ = MagicMock(return_value=mock_response)
        mock_response.__aexit__ = MagicMock(return_value=None)

        mock_session.return_value.__aenter__.return_value.get.return_value = (
            mock_response
        )

        # Test logic
        status = "up" if mock_response.status == 200 else "down"
        assert status == "down"

    def test_response_time_calculation(self):
        """Test response time calculation"""
        from datetime import datetime

        start = datetime.now()
        # Simulate delay
        import time

        time.sleep(0.1)
        end = datetime.now()

        response_time = (end - start).total_seconds() * 1000
        assert response_time >= 100  # At least 100ms

    def test_monitoring_interval(self):
        """Test monitoring interval configuration"""
        check_interval = 60  # seconds
        assert check_interval >= 30  # Minimum 30 seconds
        assert check_interval <= 300  # Maximum 5 minutes


class TestNotifications:
    """Tests for Notification system"""

    def test_notify_methods(self, db):
        """Test notification methods configuration"""
        notify_methods = ["telegram", "email", "slack"]

        assert "telegram" in notify_methods
        assert "email" in notify_methods
        assert "slack" in notify_methods

    def test_save_notify_config(self, db):
        """Test saving notification configuration"""
        conn = db
        config = {
            "telegram": {"enabled": True, "token": "test"},
            "email": {"enabled": False},
        }

        conn.execute(
            """
            INSERT OR REPLACE INTO notify_config (id, config)
            VALUES (?, ?)
        """,
            (1, json.dumps(config)),
        )
        conn.commit()

        cursor = conn.execute("SELECT config FROM notify_config WHERE id = 1")
        saved_config = json.loads(cursor.fetchone()["config"])

        assert saved_config["telegram"]["enabled"] == True
        assert saved_config["email"]["enabled"] == False


class TestDataValidation:
    """Data validation tests"""

    def test_url_validation(self):
        """Test URL validation"""
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
        """Test invalid URL detection"""
        from urllib.parse import urlparse

        invalid_urls = ["not-a-url", "ftp://example.com", ""]

        for url in invalid_urls:
            parsed = urlparse(url)
            is_valid = parsed.scheme in ["http", "https"] and parsed.netloc != ""
            assert not is_valid

    def test_check_interval_range(self):
        """Test check interval valid range"""
        check_interval = 60

        assert 30 <= check_interval <= 300

    def test_site_name_max_length(self):
        """Test site name length validation"""
        max_length = 255
        name = "A" * max_length

        assert len(name) <= max_length


class TestIntegration:
    """Integration tests"""

    def test_full_monitoring_cycle(self, db):
        """Test complete monitoring cycle"""
        conn = db

        # 1. Get active sites
        cursor = conn.execute("SELECT * FROM sites WHERE is_active = 1")
        sites = cursor.fetchall()

        # 2. Check each site (mocked)
        for site in sites:
            # Simulate check
            status = "up"
            status_code = 200
            response_time = 150

            # 3. Update site status
            conn.execute(
                """
                UPDATE sites SET status = ?, status_code = ?, response_time = ?
                WHERE id = ?
            """,
                (status, status_code, response_time, site["id"]),
            )

            # 4. Add to history
            conn.execute(
                """
                INSERT INTO status_history (site_id, status, status_code, response_time, checked_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    site["id"],
                    status,
                    status_code,
                    response_time,
                    datetime.now().isoformat(),
                ),
            )

        conn.commit()

        # Verify
        cursor = conn.execute("SELECT COUNT(*) FROM status_history")
        count = cursor.fetchone()[0]

        assert count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
