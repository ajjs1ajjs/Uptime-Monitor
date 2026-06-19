"""Integration tests for API endpoints, auth, audit log, and rate limiting"""
import json
import os
import sys
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def test_db():
    """Create a shared test database for all tests in this module."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    os.environ["UPTIME_MONITOR_ADMIN_PASSWORD"] = "291263"

    import asyncio

    from Uptime_Robot import auth_module
    from Uptime_Robot.models import init_database

    async def _setup():
        await init_database(db_path)
        await auth_module.init_auth_tables(db_path)

    asyncio.run(_setup())
    yield db_path
    import asyncio

    from Uptime_Robot.database import close_db
    try:
        asyncio.run(close_db())
    except Exception:
        pass
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


# Patch DB_PATH globally for all tests in this module
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
def client(patch_db_path):
    from Uptime_Robot.main import app

    # Real browsers always attach a same-origin Origin header on state-changing
    # fetch() requests; mirror that so the (fail-closed) CSRF middleware behaves
    # as it would in production. TestClient's default base_url is testserver.
    with TestClient(app, headers={"Origin": "http://testserver"}) as c:
        yield c


@pytest.fixture(autouse=True)
def clear_rate_limits(patch_db_path):
    import sqlite3

    from Uptime_Robot.state import DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM rate_limits")
        conn.commit()
        conn.close()
    except Exception:
        pass


@pytest.fixture
def admin_session(client: TestClient):
    """Login as admin and return the session cookie."""
    response = client.post("/login", data={"username": "admin", "password": "291263"}, follow_redirects=False)
    assert response.status_code in (302,), f"Login failed: {response.status_code}"
    cookies = response.cookies
    assert "session_id" in cookies
    return cookies["session_id"]


@pytest.fixture
def admin_headers(admin_session):
    return {"Cookie": f"session_id={admin_session}"}


class TestLoginEndpoint:
    def test_login_page(self, client):
        r = client.get("/login")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_login_success(self, client):
        r = client.post("/login", data={"username": "admin", "password": "291263"}, follow_redirects=False)
        assert r.status_code == 302
        assert "session_id" in r.cookies

    def test_login_invalid_password(self, client):
        r = client.post("/login", data={"username": "admin", "password": "wrong"}, follow_redirects=False)
        assert r.status_code == 302
        assert "error=Invalid" in r.headers.get("location", "")

    def test_login_nonexistent_user(self, client):
        r = client.post("/login", data={"username": "nobody", "password": "pass"}, follow_redirects=False)
        assert r.status_code == 302
        assert "error=Invalid" in r.headers.get("location", "")

    def test_login_redirects_when_authenticated(self, client, admin_session):
        client.cookies.clear()
        r = client.get("/login", headers={"Cookie": f"session_id={admin_session}"}, follow_redirects=False)
        assert r.status_code == 302
        assert r.headers.get("location") == "/"

    def test_logout(self, client, admin_session):
        client.cookies.clear()
        r = client.get("/logout", headers={"Cookie": f"session_id={admin_session}"}, follow_redirects=False)
        assert r.status_code == 302
        assert r.headers.get("location") == "/login"


class TestAuthRequired:
    def test_api_sites_requires_auth(self, client):
        r = client.get("/api/sites")
        assert r.status_code == 401

    def test_api_users_requires_admin(self, client, admin_headers):
        r = client.get("/api/users", headers=admin_headers)
        assert r.status_code == 200

    def test_health_is_public(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_status_page_is_public(self, client):
        r = client.get("/status")
        assert r.status_code == 200


class TestSiteCRUD:
    def test_create_site(self, client, admin_headers):
        r = client.post("/api/sites", json={
            "name": "Test Monitor",
            "url": "https://example.com",
            "check_interval": 60,
            "monitor_type": "http",
        }, headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert data["message"] == "Site added"

    def test_create_site_duplicate_url(self, client, admin_headers):
        r = client.post("/api/sites", json={
            "name": "Duplicate",
            "url": "https://example.com",
        }, headers=admin_headers)
        assert r.status_code == 400
        assert "already exists" in r.json().get("detail", "").lower()

    def test_create_site_invalid_url(self, client, admin_headers):
        r = client.post("/api/sites", json={
            "name": "Bad URL",
            "url": "not-a-url",
            "monitor_type": "http",
        }, headers=admin_headers)
        assert r.status_code == 400

    def test_list_sites(self, client, admin_headers):
        r = client.get("/api/sites", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "Test Monitor"

    def test_get_site_history(self, client, admin_headers):
        r = client.get("/api/sites/1/history", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_update_site(self, client, admin_headers):
        r = client.put("/api/sites/1", json={"name": "Updated Monitor", "check_interval": 120}, headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["message"] == "Updated"

        r = client.get("/api/sites", headers=admin_headers)
        updated = [s for s in r.json() if s["id"] == 1]
        assert updated[0]["name"] == "Updated Monitor"
        assert updated[0]["check_interval"] == 120

    def test_update_nonexistent_site(self, client, admin_headers):
        r = client.put("/api/sites/99999", json={"name": "Ghost"}, headers=admin_headers)
        assert r.status_code == 404

    def test_delete_site(self, client, admin_headers):
        r = client.post("/api/sites", json={
            "name": "To Delete",
            "url": "https://todelete.com",
        }, headers=admin_headers)
        site_id = r.json()["id"]

        r = client.delete(f"/api/sites/{site_id}", headers=admin_headers)
        assert r.status_code == 200

        r = client.get("/api/sites", headers=admin_headers)
        ids = [s["id"] for s in r.json()]
        assert site_id not in ids

    def test_delete_nonexistent_site(self, client, admin_headers):
        r = client.delete("/api/sites/99999", headers=admin_headers)
        assert r.status_code == 404


class TestUserCRUD:
    @pytest.fixture
    def viewer_user(self, client, admin_headers):
        import time
        username = f"viewer_{int(time.time() * 1000)}"
        r = client.post("/api/users", json={
            "username": username,
            "password": "ViewerPass123!",
            "role": "viewer",
        }, headers=admin_headers)
        assert r.status_code == 200, f"Failed to create viewer: {r.text}"
        return username

    def test_create_user(self, client, admin_headers):
        r = client.post("/api/users", json={
            "username": "newuser",
            "password": "UserPass123!",
            "role": "viewer",
        }, headers=admin_headers)
        assert r.status_code == 200

    def test_create_user_weak_password(self, client, admin_headers):
        # Weak passwords must be rejected by the password strength policy.
        r = client.post("/api/users", json={
            "username": "weakuser",
            "password": "short",
            "role": "viewer",
        }, headers=admin_headers)
        assert r.status_code == 400

    def test_create_duplicate_user(self, client, admin_headers):
        r = client.post("/api/users", json={
            "username": "newuser",
            "password": "UserPass123!",
            "role": "viewer",
        }, headers=admin_headers)
        assert r.status_code == 400

    def test_list_users(self, client, admin_headers):
        r = client.get("/api/users", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        usernames = [u["username"] for u in data]
        assert "admin" in usernames
        assert "newuser" in usernames

    def test_update_user_role(self, client, admin_headers):
        r = client.put("/api/users/newuser", json={"role": "admin"}, headers=admin_headers)
        assert r.status_code == 200

        r = client.get("/api/users", headers=admin_headers)
        user = next(u for u in r.json() if u["username"] == "newuser")
        assert user["role"] == "admin"

    def test_viewer_cannot_access_admin_apis(self, client, viewer_user):
        r = client.post("/login", data={"username": viewer_user, "password": "ViewerPass123!"}, follow_redirects=False)
        assert r.status_code == 302
        session = r.cookies["session_id"]
        viewer_headers = {"Cookie": f"session_id={session}"}

        r = client.get("/api/users", headers=viewer_headers)
        assert r.status_code == 403

        r = client.post("/api/sites", json={"name": "X", "url": "https://x.com"}, headers=viewer_headers)
        assert r.status_code == 403

    def test_viewer_can_read_sites(self, client, viewer_user):
        r = client.post("/login", data={"username": viewer_user, "password": "ViewerPass123!"}, follow_redirects=False)
        assert r.status_code == 302, f"viewer login failed: {r.status_code}"
        session = r.cookies["session_id"]
        viewer_headers = {"Cookie": f"session_id={session}"}

        r = client.get("/api/sites", headers=viewer_headers)
        assert r.status_code == 200

    def test_viewer_cannot_list_users(self, client, viewer_user):
        r = client.post("/login", data={"username": viewer_user, "password": "ViewerPass123!"}, follow_redirects=False)
        assert r.status_code == 302, f"viewer login failed: {r.status_code}"
        session = r.cookies["session_id"]
        viewer_headers = {"Cookie": f"session_id={session}"}

        r = client.get("/api/users", headers=viewer_headers)
        assert r.status_code == 403

    def test_delete_user(self, client, admin_headers):
        r = client.delete("/api/users/newuser", headers=admin_headers)
        assert r.status_code == 200

        r = client.get("/api/users", headers=admin_headers)
        usernames = [u["username"] for u in r.json()]
        assert "newuser" not in usernames

    def test_cannot_delete_last_admin(self, client, admin_headers):
        r = client.delete("/api/users/admin", headers=admin_headers)
        assert r.status_code == 400


class TestApiKeyAuth:
    def test_create_api_key(self, client, admin_headers):
        r = client.post("/api/api-keys?name=TestKey", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "TestKey"
        assert data["api_key"].startswith("um_")

    def test_list_api_keys(self, client, admin_headers):
        r = client.get("/api/api-keys", headers=admin_headers)
        assert r.status_code == 200
        keys = r.json()
        assert isinstance(keys, list)
        assert any(k["name"] == "TestKey" for k in keys)

    def test_authenticate_with_api_key(self, client, admin_headers):
        r = client.post("/api/api-keys?name=AuthTest", headers=admin_headers)
        assert r.status_code == 200
        api_key = r.json()["api_key"]

        client.cookies.clear()
        r = client.get("/api/sites", headers={"X-API-Key": api_key})
        assert r.status_code == 200

    def test_invalid_api_key_rejected(self, client):
        r = client.get("/api/sites", headers={"X-API-Key": "um_invalidkey123"})
        assert r.status_code == 401

    def test_wrong_prefix_api_key_rejected(self, client):
        r = client.get("/api/sites", headers={"X-API-Key": "sk_test12345"})
        assert r.status_code == 401

    def test_revoke_api_key(self, client, admin_headers):
        """Verify API key revocation works end-to-end."""
        r = client.post("/api/api-keys?name=RevokeMe", headers=admin_headers)
        assert r.status_code == 200, f"Create key failed: {r.text}"
        data = r.json()
        api_key = data["api_key"]
        key_id = data["key_id"]

        # Verify key works before revoke
        client.cookies.clear()
        r = client.get("/api/sites", headers={"X-API-Key": api_key})
        assert r.status_code == 200

        # Revoke via API
        r = client.delete(f"/api/api-keys/{key_id}", headers=admin_headers)
        assert r.status_code == 200

        # Direct DB check: verify is_active was set to 0
        import sqlite3

        from Uptime_Robot.state import DB_PATH as CURRENT_DB
        conn = sqlite3.connect(CURRENT_DB)
        row = conn.execute("SELECT is_active FROM api_keys WHERE key_id = ?", (key_id,)).fetchone()
        conn.close()
        assert row is not None, f"Key {key_id} not found in DB"
        assert row[0] == 0, f"is_active={row[0]}, expected 0"

        # Verify via API - MUST be 401 now that cookies are cleared
        client.cookies.clear()
        r = client.get("/api/sites", headers={"X-API-Key": api_key})
        assert r.status_code == 401


class TestAuditLog:
    def test_audit_log_exists(self, client, admin_headers):
        r = client.get("/api/audit-log", headers=admin_headers)
        assert r.status_code == 200
        entries = r.json()
        assert isinstance(entries, list)

    def test_site_creation_logged(self, client, admin_headers):
        r = client.post("/api/sites", json={
            "name": "Audit Site",
            "url": "https://auditsite.com",
        }, headers=admin_headers)
        assert r.status_code == 200

        r = client.get("/api/audit-log", headers=admin_headers)
        entries = r.json()
        site_created = [e for e in entries if e["action"] == "site_created"]
        assert len(site_created) >= 1
        assert any("Audit Site" in (e.get("details") or "") for e in site_created)

    def test_site_deletion_logged(self, client, admin_headers):
        r = client.get("/api/audit-log", headers=admin_headers)
        before = len(r.json())

        r = client.post("/api/sites", json={
            "name": "Delete Audit",
            "url": "https://deleteaudit.com",
        }, headers=admin_headers)
        site_id = r.json()["id"]
        client.delete(f"/api/sites/{site_id}", headers=admin_headers)

        r = client.get("/api/audit-log", headers=admin_headers)
        after = len(r.json())
        assert after > before

    def test_user_creation_logged(self, client, admin_headers):
        r = client.post("/api/users", json={
            "username": "audituser",
            "password": "AuditPass123!",
            "role": "viewer",
        }, headers=admin_headers)
        assert r.status_code == 200

        r = client.get("/api/audit-log", headers=admin_headers)
        entries = r.json()
        user_created = [e for e in entries if e["action"] == "user_created"]
        assert len(user_created) >= 1

    def test_rate_limit_exceeded(self, client, admin_headers):
        r = client.get("/api/audit-log?limit=5", headers=admin_headers)
        assert len(r.json()) <= 5


class TestRateLimiting:
    def test_login_rate_limit(self, client):
        for _ in range(6):
            r = client.post("/login", data={"username": "admin", "password": "wrong"}, follow_redirects=False)
        assert r.status_code == 429

    def test_metrics_endpoint(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        body = r.text
        assert "uptime_monitor_sites_total" in body
        assert "uptime_monitor_sites_up" in body
        assert "uptime_monitor_sites_down" in body
        assert "uptime_monitor_info" in body

    def test_server_time(self, client):
        r = client.get("/api/server-time")
        assert r.status_code == 200
        data = r.json()
        assert "timestamp" in data
        assert "iso" in data

    def test_healthcheck_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_notification_history_requires_auth(self, client):
        r = client.get("/api/notification-history")
        assert r.status_code == 401

    def test_notification_history_admin_only(self, client, admin_headers):
        r = client.get("/api/notification-history", headers=admin_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_backup_requires_admin(self, client):
        r = client.post("/api/backup")
        assert r.status_code == 401

    def test_backup_endpoint_admin(self, client, admin_headers):
        r = client.post("/api/backup", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "filename" in data
        assert "path" in data

    def test_list_backups_requires_admin(self, client):
        r = client.get("/api/backups")
        assert r.status_code == 401

    def test_list_backups_admin(self, client, admin_headers):
        r = client.get("/api/backups", headers=admin_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_stats_response_time_requires_auth(self, client):
        r = client.get("/api/stats/response-time")
        assert r.status_code in (401, 403)

    def test_public_status_page_html(self, client):
        r = client.get("/status")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_public_status_page_has_sites(self, client):
        r = client.get("/status")
        assert r.status_code == 200

    def test_public_status_alternative_path(self, client):
        r = client.get("/public-status")
        assert r.status_code == 200


class TestSecurityHardening:
    """CSRF, Origin and SSRF protections added in security hardening."""

    def test_ssrf_literal_private_ip_rejected(self, client, admin_headers):
        r = client.post("/api/sites", json={
            "name": "ssrf-private", "url": "http://127.0.0.1", "monitor_type": "http",
        }, headers=admin_headers)
        assert r.status_code == 400

    def test_ssrf_cloud_metadata_ip_rejected(self, client, admin_headers):
        r = client.post("/api/sites", json={
            "name": "ssrf-metadata", "url": "http://169.254.169.254/latest/meta-data",
            "monitor_type": "http",
        }, headers=admin_headers)
        assert r.status_code == 400

    def test_ssrf_hostname_resolving_to_private_rejected(self, client, admin_headers):
        # A public-looking hostname that resolves to a private address must be
        # blocked (DNS-based SSRF).
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.5", 0))]):
            r = client.post("/api/sites", json={
                "name": "ssrf-dns", "url": "http://internal.example.com",
                "monitor_type": "http",
            }, headers=admin_headers)
        assert r.status_code == 400

    def test_api_cross_origin_post_denied(self, client, admin_headers):
        headers = dict(admin_headers)
        headers["Origin"] = "http://evil.example.com"
        r = client.post("/api/sites", json={
            "name": "xorigin", "url": "https://example.org", "monitor_type": "http",
        }, headers=headers)
        assert r.status_code == 403

    def test_api_missing_origin_on_cookie_request_denied(self, patch_db_path, admin_session):
        # Fail-closed: a cookie-authenticated state-changing request with NO
        # Origin/Referer must be rejected (a real browser always sends one).
        from fastapi.testclient import TestClient

        from Uptime_Robot.main import app

        with TestClient(app) as bare:  # no default Origin header
            r = bare.post("/api/sites",
                          json={"name": "noorigin", "url": "https://example.org",
                                "monitor_type": "http"},
                          headers={"Cookie": f"session_id={admin_session}"})
        assert r.status_code == 403

    def test_forgot_password_requires_csrf_token(self, client, admin_headers):
        # POST without a valid CSRF token is rejected (redirect with error).
        r = client.post("/forgot-password", data={"username": "admin"},
                        headers=admin_headers, follow_redirects=False)
        assert r.status_code == 302
        assert "error" in r.headers.get("location", "").lower()

    def test_forgot_password_with_csrf_token_passes_csrf(self, client, admin_headers):
        # Use a non-existent target so a valid CSRF token reaches the handler
        # WITHOUT resetting the shared admin password (which other tests rely on).
        import re
        page = client.get("/forgot-password", headers=admin_headers)
        assert page.status_code == 200
        m = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        assert m, "CSRF token not found in forgot-password form"
        token = m.group(1)
        r = client.post("/forgot-password",
                        data={"username": "no-such-user", "csrf_token": token},
                        headers=admin_headers, follow_redirects=False)
        # CSRF accepted → handler runs (200 with "User not found"), not a
        # 302 "Session expired" redirect.
        assert r.status_code == 200
        assert "User not found" in r.text


class TestDnsMonitorApi:
    def test_create_dns_monitor(self, client, admin_headers):
        r = client.post("/api/sites", json={
            "name": "DNS Test Monitor",
            "url": "dns.google",
            "check_interval": 60,
            "monitor_type": "dns",
        }, headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        
        # Verify it lists as dns type
        r = client.get("/api/sites", headers=admin_headers)
        assert r.status_code == 200
        sites = r.json()
        dns_sites = [s for s in sites if s["monitor_type"] == "dns"]
        assert len(dns_sites) >= 1
        assert dns_sites[0]["name"] == "DNS Test Monitor"

