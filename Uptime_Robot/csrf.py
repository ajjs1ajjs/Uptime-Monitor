"""CSRF protection using session-bound tokens."""

import secrets

from fastapi import Request
from fastapi.responses import PlainTextResponse

from .database import get_db_connection
from .logger import logger


async def init_csrf_table():
    """Adds csrf_token column to sessions table if missing + creates csrf_tokens table."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute("PRAGMA table_info(sessions)") as c:
                cols = {r[1] for r in await c.fetchall()}
            if "csrf_token" not in cols:
                await conn.execute("ALTER TABLE sessions ADD COLUMN csrf_token TEXT")
            await conn.execute("""CREATE TABLE IF NOT EXISTS csrf_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                token TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )""")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_csrf_tokens_session ON csrf_tokens(session_id)"
            )
            await conn.commit()
            logger.info("CSRF tables initialized")
    except Exception as e:
        logger.error("CSRF table init failed: %s", e)


async def generate_csrf_token(session_id: str) -> str:
    """Generate and store a CSRF token for the given session (allows multiple)."""
    token = secrets.token_urlsafe(32)
    try:
        async with get_db_connection() as conn:
            # csrf_tokens is the authoritative store; commit it first.
            await conn.execute(
                "INSERT INTO csrf_tokens (session_id, token) VALUES (?, ?)",
                (session_id, token),
            )
            await conn.commit()
            # Best-effort mirror into sessions.csrf_token (legacy backward compat).
            # Must not fail token generation if that column is absent.
            try:
                await conn.execute(
                    "UPDATE sessions SET csrf_token = ? WHERE session_id = ?",
                    (token, session_id),
                )
                await conn.commit()
            except Exception:
                pass
    except Exception as e:
        logger.error("CSRF token save failed: %s", e)
        return ""
    return token


async def validate_csrf_token(session_id: str, token: str) -> bool:
    """Validate a CSRF token against stored tokens for this session."""
    if not session_id or not token:
        return False
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT token FROM csrf_tokens WHERE session_id = ? AND token = ?",
                (session_id, token),
            ) as c:
                row = await c.fetchone()
            if row:
                # Remove used token (one-time use)
                await conn.execute(
                    "DELETE FROM csrf_tokens WHERE session_id = ? AND token = ?",
                    (session_id, token),
                )
                await conn.commit()
                return True
        # Fallback: check sessions table for backward compat
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT csrf_token FROM sessions WHERE session_id = ?", (session_id,)
            ) as c:
                row = await c.fetchone()
            stored = row["csrf_token"] if row else None
            # Constant-time comparison to avoid leaking the token via timing.
            return bool(stored) and secrets.compare_digest(str(stored), token)
    except Exception:
        return False


async def cleanup_expired_csrf_tokens(max_age_hours: int = 24) -> None:
    """Delete CSRF tokens older than ``max_age_hours``.

    Unused one-time tokens (every change-password/forgot-password page render)
    otherwise accumulate forever, so they must be purged periodically.
    """
    try:
        async with get_db_connection() as conn:
            await conn.execute(
                "DELETE FROM csrf_tokens WHERE created_at < datetime('now', ?)",
                (f"-{int(max_age_hours)} hours",),
            )
            await conn.commit()
    except Exception as e:
        logger.error("CSRF token cleanup failed: %s", e)


# Paths that perform their own CSRF handling (validate a one-time token inside
# the route handler) or cannot have a token yet (/login, pre-auth).
# These form-POST routes self-validate; the middleware must NOT read their body
# here, because consuming request.form() in a Starlette HTTP middleware empties
# the body stream for the downstream handler (→ spurious 422).
CSRF_EXEMPT: set[str] = {
    "/login",
    "/change-password",
    "/forgot-password",
}


async def csrf_middleware(request: Request, call_next):
    """CSRF defense-in-depth on state-changing methods.

    - ``/api/*`` authenticated by the session cookie: enforce a same-origin
      Origin/Referer **fail-closed** — a missing Origin/Referer is rejected, not
      allowed. Browsers always send Origin on non-GET fetches, so the only
      requests lacking it are non-browser clients, which must authenticate with
      an API key instead (see below). SameSite=Lax does not block all cross-site
      top-level POSTs, so this header check is a required second layer.
    - ``/api/*`` authenticated by ``X-API-Key``: not a CSRF vector (an attacker
      cannot make the victim's browser attach the key), so the Origin check is
      skipped.
    - other non-exempt routes: require the token in the ``X-CSRF-Token`` header.

    The request body is never read here (see CSRF_EXEMPT note). Form-POST routes
    validate their own ``_csrf_token`` field. NOTE: raising HTTPException from a
    Starlette HTTP middleware yields a 500, so we return a Response directly.
    """
    if request.method in ("POST", "PUT", "DELETE"):
        path = request.url.path

        if path.startswith("/api/"):
            # API-key clients are immune to CSRF and legitimately send no Origin.
            # Only cookie-authenticated requests are a CSRF vector.
            if not request.headers.get("X-API-Key") and request.cookies.get("session_id"):
                from urllib.parse import urlparse

                origin = request.headers.get("Origin") or request.headers.get("Referer") or ""
                if not origin:
                    return PlainTextResponse(
                        "Missing Origin/Referer on state-changing request", status_code=403
                    )
                # Compare hostnames only (ignore port): TLS-terminating proxies
                # often make base_url's port differ from the public Origin.
                allowed = urlparse(str(request.base_url)).hostname
                req_origin = urlparse(origin).hostname
                if not req_origin or req_origin != allowed:
                    return PlainTextResponse("Cross-origin request denied", status_code=403)
        elif path not in CSRF_EXEMPT:
            session_id = request.cookies.get("session_id")
            csrf_token = request.headers.get("X-CSRF-Token", "")
            if not await validate_csrf_token(session_id or "", csrf_token):
                return PlainTextResponse("CSRF validation failed", status_code=403)

    return await call_next(request)
