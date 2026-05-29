import asyncio
import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections for real-time dashboard updates."""

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections.discard(ws)

    async def broadcast(self, message: dict[str, Any]):
        """Send a message to all connected clients."""
        dead: list[WebSocket] = []
        text = json.dumps(message, ensure_ascii=False, default=str)
        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_text(text)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.discard(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()
