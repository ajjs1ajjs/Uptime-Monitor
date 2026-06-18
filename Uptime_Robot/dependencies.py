import os

from fastapi import Depends, HTTPException, Request

from . import auth_module
from .state import DB_PATH

# Reverse-proxy support: only honour X-Forwarded-For when the direct peer is a
# configured trusted proxy. Empty by default → behaviour unchanged (direct IP).
_TRUSTED_PROXIES = {
    p.strip() for p in os.environ.get("UPTIME_MONITOR_TRUSTED_PROXIES", "").split(",") if p.strip()
}


def get_client_ip(request: Request) -> str:
    """Resolve the real client IP for rate-limiting/logging.

    Behind a reverse proxy every request appears to come from the proxy IP,
    which would make per-IP rate limits global. If the direct peer is a trusted
    proxy, use the first hop in X-Forwarded-For instead. X-Forwarded-For is
    spoofable, so it is ONLY trusted from configured proxy addresses.
    """
    direct = request.client.host if request.client else "unknown"
    if direct in _TRUSTED_PROXIES:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
    return direct


async def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        user = await auth_module.validate_session(session_id, DB_PATH)
        if user:
            return user

    api_key = request.headers.get("X-API-Key")
    if api_key:
        user = await auth_module.validate_api_key(DB_PATH, api_key)
        return user

    return None


def require_admin(user: dict = Depends(get_current_user)):
    """Dependency to require admin role"""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not auth_module.is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_viewer_or_higher(user: dict = Depends(get_current_user)):
    """Dependency to require viewer or admin role (read-only access)"""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not auth_module.is_viewer_or_higher(user):
        raise HTTPException(status_code=403, detail="Viewer or admin access required")
    return user
