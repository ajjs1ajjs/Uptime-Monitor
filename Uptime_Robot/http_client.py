"""Shared aiohttp session pool.

Creating a fresh ``aiohttp.ClientSession`` for every uptime check and every
notification throws away connection pooling, keep-alive and the DNS cache. This
module hands out one long-lived session per event loop instead, so repeated
requests to the same host reuse connections.

Sessions are keyed by the running event loop (the web server and the standalone
worker each run their own loop, and tests spin up a fresh loop per case), and a
closed session is transparently recreated.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

import aiohttp

_sessions: dict[int, aiohttp.ClientSession] = {}


async def get_session() -> aiohttp.ClientSession:
    """Return a shared ClientSession bound to the current event loop."""
    loop = asyncio.get_running_loop()
    key = id(loop)
    session = _sessions.get(key)
    if session is None or session.closed:
        session = aiohttp.ClientSession()
        _sessions[key] = session
    return session


@asynccontextmanager
async def session_scope():
    """``async with session_scope() as session:`` — yields the pooled session.

    A drop-in replacement for ``async with aiohttp.ClientSession() as session:``
    that does NOT close the session on exit (it is shared and long-lived).
    """
    yield await get_session()


async def close_sessions(loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
    """Close pooled sessions (call on shutdown).

    With no argument, closes the session for the current loop; this keeps the
    pool from leaking sessions across process lifetime.
    """
    if loop is None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
    keys = [id(loop)] if loop is not None else list(_sessions.keys())
    for key in keys:
        session = _sessions.pop(key, None)
        if session is not None and not session.closed:
            try:
                await session.close()
            except Exception:
                pass
