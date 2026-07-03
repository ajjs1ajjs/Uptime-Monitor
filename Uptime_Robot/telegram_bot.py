"""Long-polls configured Telegram bots for inline-keyboard button presses
(Acknowledge / Silence 1h / Silence 6h) on DOWN alerts.

Polling (outbound-only HTTPS to api.telegram.org) is used instead of a
webhook because this app is typically deployed on a private/internal
network with no public inbound address for Telegram to call back into.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import aiohttp

from .database import get_db_connection
from .http_client import session_scope
from .logger import logger

_ACTION_PREFIXES = ("ack_", "silence1h_", "silence6h_")
_offsets: dict[str, int] = {}
_known_tokens: set[str] = set()


def _collect_telegram_tokens(notify_settings: dict[str, Any]) -> list[str]:
    tg = (notify_settings or {}).get("telegram") or {}
    if not tg.get("enabled"):
        return []
    tokens: list[str] = []
    seen: set[str] = set()
    for channel in tg.get("channels", []):
        token = channel.get("token")
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


async def _init_offset(token: str) -> None:
    """Skip any backlog of button presses that piled up while the poller
    wasn't running, so a restart doesn't replay stale silence/ack clicks."""
    try:
        async with session_scope() as session:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": -1, "limit": 1},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
        results = data.get("result") or []
        _offsets[token] = (results[-1]["update_id"] + 1) if results else 0
    except Exception as e:
        logger.error("Telegram getUpdates offset init failed: %s", e)
        _offsets[token] = 0


async def _answer_callback_query(token: str, callback_query_id: str, text: str) -> None:
    try:
        async with session_scope() as session:
            await session.post(
                f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text[:200]},
                timeout=aiohttp.ClientTimeout(total=10),
            )
    except Exception as e:
        logger.error("Telegram answerCallbackQuery failed: %s", e)


async def _apply_action(site_id: int, action: str) -> str:
    from .state import DB_PATH

    if action == "ack":
        async with get_db_connection(DB_PATH) as conn:
            await conn.execute("UPDATE sites SET acknowledged = 1 WHERE id = ?", (site_id,))
            await conn.commit()
        return "✅ Підтверджено. Повтори сповіщень вимкнено до відновлення сайту."

    hours = 1 if action == "silence1h" else 6
    until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    async with get_db_connection(DB_PATH) as conn:
        await conn.execute(
            "UPDATE sites SET silenced_until = ? WHERE id = ?", (until, site_id)
        )
        await conn.commit()
    return f"🔇 Сповіщення вимкнено на {hours} год."


async def _process_update(token: str, update: dict[str, Any]) -> None:
    callback = update.get("callback_query")
    if not callback:
        return
    callback_id = callback.get("id")
    data = callback.get("data") or ""

    action = None
    site_id_str = None
    for prefix in _ACTION_PREFIXES:
        if data.startswith(prefix):
            action = prefix[:-1]
            site_id_str = data[len(prefix) :]
            break

    if action is None or not site_id_str.isdigit():
        if callback_id:
            await _answer_callback_query(token, callback_id, "Невідома дія")
        return

    try:
        text = await _apply_action(int(site_id_str), action)
    except Exception as e:
        logger.error("Failed to apply Telegram action %s for site %s: %s", action, site_id_str, e)
        text = "Помилка обробки дії"

    if callback_id:
        await _answer_callback_query(token, callback_id, text)


async def poll_telegram_updates(get_notify_settings: Callable[[], dict[str, Any]]) -> None:
    """Background task: repeatedly long-polls every configured bot token for
    new callback_query updates and dispatches them. Runs until cancelled."""
    while True:
        try:
            tokens = _collect_telegram_tokens(get_notify_settings())
            for token in tokens:
                if token not in _known_tokens:
                    _known_tokens.add(token)
                    await _init_offset(token)

            for token in tokens:
                try:
                    async with session_scope() as session:
                        async with session.get(
                            f"https://api.telegram.org/bot{token}/getUpdates",
                            params={
                                "offset": _offsets.get(token, 0),
                                "timeout": 10,
                                "allowed_updates": '["callback_query"]',
                            },
                            timeout=aiohttp.ClientTimeout(total=15),
                        ) as resp:
                            data = await resp.json()
                except Exception as e:
                    logger.error("Telegram getUpdates failed: %s", e)
                    continue

                for update in data.get("result", []):
                    _offsets[token] = update["update_id"] + 1
                    try:
                        await _process_update(token, update)
                    except Exception as e:
                        logger.error("Failed processing Telegram update: %s", e)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Error in Telegram button poller: %s", e)
            await asyncio.sleep(5)
