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
            return row is not None and row["csrf_token"] == token
    except Exception:
        return False


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

    - ``/api/*``: enforce a same-origin Origin/Referer (the SPA uses fetch, which
      always sends Origin on non-GET requests; SameSite=Lax cookies are the
      primary defense and this is the second layer).
    - other non-exempt routes: require the token in the ``X-CSRF-Token`` header.

    The request body is never read here (see CSRF_EXEMPT note). Form-POST routes
    validate their own ``_csrf_token`` field. NOTE: raising HTTPException from a
    Starlette HTTP middleware yields a 500, so we return a Response directly.
    """
    if request.method in ("POST", "PUT", "DELETE"):
        path = request.url.path

        if path.startswith("/api/"):
            origin = request.headers.get("Origin") or request.headers.get("Referer") or ""
            if origin:
                from urllib.parse import urlparse

                # Compare hostnames only (ignore port): TLS-terminating proxies
                # often make base_url's port differ from the public Origin.
                allowed = urlparse(str(request.base_url)).hostname
                req_origin = urlparse(origin).hostname
                if req_origin and allowed and req_origin != allowed:
                    return PlainTextResponse("Cross-origin request denied", status_code=403)
        elif path not in CSRF_EXEMPT:
            session_id = request.cookies.get("session_id")
            csrf_token = request.headers.get("X-CSRF-Token", "")
            if not await validate_csrf_token(session_id or "", csrf_token):
                return PlainTextResponse("CSRF validation failed", status_code=403)

    return await call_next(request)
