"""CSRF protection using session-bound tokens."""

import secrets

from fastapi import HTTPException, Request

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
            await conn.execute(
                "INSERT INTO csrf_tokens (session_id, token) VALUES (?, ?)",
                (session_id, token),
            )
            # Also keep single token in sessions table for backward compat
            await conn.execute(
                "UPDATE sessions SET csrf_token = ? WHERE session_id = ?",
                (token, session_id),
            )
            await conn.commit()
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


CSRF_EXEMPT: set[str] = {
    "/login",
    "/forgot-password",
}


async def csrf_middleware(request: Request, call_next):
    """Middleware that validates CSRF tokens on state-changing methods."""
    if request.method in ("POST", "PUT", "DELETE"):
        path = request.url.path
        if path not in CSRF_EXEMPT and not path.startswith("/api/"):
            session_id = request.cookies.get("session_id")
            csrf_token = ""
            if request.method == "POST":
                try:
                    form = await request.form()
                    csrf_token = str(form.get("_csrf_token", ""))
                except RuntimeError:
                    logger.warning("CSRF: request body already consumed for %s", path)
            else:
                csrf_token = request.headers.get("X-CSRF-Token", "")

            if not await validate_csrf_token(session_id or "", csrf_token):
                raise HTTPException(status_code=403, detail="CSRF validation failed")

        # Origin/Referer check for API endpoints (defense in depth)
        if path.startswith("/api/"):
            origin = request.headers.get("Origin") or request.headers.get("Referer") or ""
            if origin:
                from urllib.parse import urlparse

                allowed = urlparse(str(request.base_url)).netloc
                req_origin = urlparse(origin).netloc
                if req_origin and req_origin != allowed:
                    raise HTTPException(status_code=403, detail="Cross-origin request denied")

    return await call_next(request)
