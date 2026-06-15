"""CSRF protection using session-bound tokens."""
import secrets
from typing import Optional

from fastapi import HTTPException, Request

from .database import get_db_connection
from .logger import logger


async def init_csrf_table():
    """Adds csrf_token column to sessions table if missing."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute("PRAGMA table_info(sessions)") as c:
                cols = {r[1] for r in await c.fetchall()}
            if "csrf_token" not in cols:
                await conn.execute("ALTER TABLE sessions ADD COLUMN csrf_token TEXT")
                await conn.commit()
                logger.info("Added csrf_token column to sessions table")
    except Exception as e:
        logger.error("CSRF table init failed: %s", e)


async def generate_csrf_token(session_id: str) -> str:
    """Generate and store a CSRF token for the given session."""
    token = secrets.token_urlsafe(32)
    try:
        async with get_db_connection() as conn:
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
    """Validate a CSRF token against the stored one for this session."""
    if not session_id or not token:
        return False
    try:
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
            if request.method == "POST":
                form = await request.form()
                csrf_token = form.get("_csrf_token", "")
            else:
                csrf_token = request.headers.get("X-CSRF-Token", "")

            if not await validate_csrf_token(session_id or "", csrf_token):
                raise HTTPException(status_code=403, detail="CSRF validation failed")
    return await call_next(request)
