"""Модуль для відправки сповіщень"""

import asyncio
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any, Optional, Union

import aiohttp

from .logger import logger
from .metrics_store import increment_metric


def format_telegram_message(data: dict[str, Any], alert_type: str = "down") -> str:
    """Форматує повідомлення для Telegram"""
    site_name = data.get("site_name", "Unknown")
    url = data.get("url", "")
    status_code = data.get("status_code", "N/A")
    error = data.get("error", "None")
    response_time = data.get("response_time", 0)
    checked_at = data.get("checked_at", "")
    rt_str = f"{round(response_time, 2)}ms" if response_time else "N/A"

    if alert_type == "down":
        return f"""🔴 <b>⚠️ САЙТ НЕ ПРАЦЮЄ!</b>

<b>🌐 Сайт:</b> {site_name}
<b>📎 URL:</b> <code>{url}</code>
<b>📊 Статус:</b> <code>{status_code}</code>
<b>❌ Помилка:</b> <i>{error}</i>
<b>🕐 Час:</b> {checked_at}

━━━━━━━━━━━━━━━━━━
<i>Uptime Monitor</i>"""

    elif alert_type == "still_down":
        return f"""🔴 <b>⏱️ САЙТ ДОСІ НЕ ПРАЦЮЄ!</b>

<b>🌐 Сайт:</b> {site_name}
<b>📎 URL:</b> <code>{url}</code>
<b>📊 Статус:</b> <code>{status_code}</code>
<b>❌ Помилка:</b> <i>{error}</i>
<b>🕐 Час:</b> {checked_at}
<b>⚠️ Проблема триває...</b>

━━━━━━━━━━━━━━━━━━
<i>Uptime Monitor</i>"""

    elif alert_type == "up":
        return f"""🟢 <b>✅ САЙТ ВІДНОВЛЕНО!</b>

<b>🌐 Сайт:</b> {site_name}
<b>📎 URL:</b> <code>{url}</code>
<b>📊 Статус:</b> <code>{status_code}</code>
<b>⏱️ Час відповіді:</b> <code>{rt_str}</code>
<b>🕐 Час:</b> {checked_at}

━━━━━━━━━━━━━━━━━━
<i>Uptime Monitor</i>"""

    elif alert_type == "ssl":
        days = data.get("days_left", 0)
        expire_date = data.get("expire_date", "")
        urgency = data.get("urgency", "УВАГА")

        if days <= 0:
            icon = "🔴"
            status = "ПРОСТРОЧЕНИЙ"
        elif days <= 3:
            icon = "🔴"
            status = f"Закінчується через {days} днів"
        elif days <= 7:
            icon = "🟠"
            status = f"Закінчується через {days} днів"
        else:
            icon = "🟡"
            status = f"Закінчується через {days} днів"

        return f"""🔒 <b>{icon} SSL СЕРТИФІКАТ - {urgency}</b>

<b>🌐 Сайт:</b> {site_name}
<b>📎 URL:</b> <code>{url}</code>
<b>📅 Статус:</b> <i>{status}</i>
<b>📆 Дійсний до:</b> <code>{expire_date}</code>
<b>⏰ Залишилось:</b> <code>{days} днів</code>

━━━━━━━━━━━━━━━━━━
<i>Uptime Monitor</i>"""

    return str(data)


def format_discord_message(data: dict[str, Any], alert_type: str = "down") -> dict[str, Any]:
    """Форматує повідомлення для Discord (embed)"""
    site_name = data.get("site_name", "Unknown")
    url = data.get("url", "")
    status_code = data.get("status_code", "N/A")
    error = data.get("error", "None")
    response_time = data.get("response_time", 0)
    checked_at = data.get("checked_at", "")
    rt_str = f"{round(response_time, 2)}ms" if response_time else "N/A"

    if alert_type == "down":
        return {
            "embeds": [
                {
                    "title": "🔴 ⚠️ САЙТ НЕ ПРАЦЮЄ!",
                    "color": 16711680,
                    "fields": [
                        {"name": "🌐 Сайт", "value": site_name, "inline": True},
                        {"name": "📎 URL", "value": f"`{url}`", "inline": False},
                        {
                            "name": "📊 Статус",
                            "value": f"`{status_code}`",
                            "inline": True,
                        },
                        {"name": "❌ Помилка", "value": f"_{error}_", "inline": False},
                        {"name": "🕐 Час", "value": checked_at, "inline": True},
                    ],
                    "footer": {
                        "text": "Uptime Monitor",
                        "icon_url": "https://i.imgur.com/AfFp7pu.png",
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ]
        }

    elif alert_type == "still_down":
        return {
            "embeds": [
                {
                    "title": "🔴 ⏱️ САЙТ ДОСІ НЕ ПРАЦЮЄ!",
                    "color": 16711680,
                    "fields": [
                        {"name": "🌐 Сайт", "value": site_name, "inline": True},
                        {"name": "📎 URL", "value": f"`{url}`", "inline": False},
                        {
                            "name": "📊 Статус",
                            "value": f"`{status_code}`",
                            "inline": True,
                        },
                        {
                            "name": "⚠️ Проблема триває...",
                            "value": f"_{error}_",
                            "inline": False,
                        },
                        {"name": "🕐 Час", "value": checked_at, "inline": True},
                    ],
                    "footer": {"text": "Uptime Monitor"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ]
        }

    elif alert_type == "up":
        return {
            "embeds": [
                {
                    "title": "🟢 ✅ САЙТ ВІДНОВЛЕНО!",
                    "color": 65280,
                    "fields": [
                        {"name": "🌐 Сайт", "value": site_name, "inline": True},
                        {"name": "📎 URL", "value": f"`{url}`", "inline": False},
                        {
                            "name": "📊 Статус",
                            "value": f"`{status_code}`",
                            "inline": True,
                        },
                        {
                            "name": "⏱️ Час відповіді",
                            "value": f"`{rt_str}`",
                            "inline": True,
                        },
                        {"name": "🕐 Час", "value": checked_at, "inline": True},
                    ],
                    "footer": {"text": "Uptime Monitor"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ]
        }

    elif alert_type == "ssl":
        days = data.get("days_left", 0)
        expire_date = data.get("expire_date", "")

        if days <= 3:
            color = 16711680
            icon = "🔴"
        elif days <= 7:
            color = 16744448
            icon = "🟠"
        else:
            color = 16776960
            icon = "🟡"

        return {
            "embeds": [
                {
                    "title": f"{icon} 🔒 SSL СЕРТИФІКАТ",
                    "color": color,
                    "fields": [
                        {"name": "🌐 Сайт", "value": site_name, "inline": True},
                        {"name": "📎 URL", "value": f"`{url}`", "inline": False},
                        {"name": "📆 Дійсний до", "value": expire_date, "inline": True},
                        {
                            "name": "⏰ Залишилось",
                            "value": f"`{days} днів`",
                            "inline": True,
                        },
                    ],
                    "footer": {"text": "Uptime Monitor"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ]
        }

    return {"content": str(data)}


def format_teams_message(data: dict[str, Any], alert_type: str = "down") -> dict[str, Any]:
    """Форматує повідомлення для Microsoft Teams"""
    site_name = data.get("site_name", "Unknown")
    url = data.get("url", "")
    status_code = data.get("status_code", "N/A")
    error = data.get("error", "None")

    if alert_type == "down":
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "FF0000",
            "summary": "Uptime Alert",
            "sections": [
                {
                    "activityTitle": "🔴 ⚠️ САЙТ НЕ ПРАЦЮЄ!",
                    "facts": [
                        {"name": "🌐 Сайт:", "value": site_name},
                        {"name": "📎 URL:", "value": url},
                        {"name": "📊 Статус:", "value": str(status_code)},
                        {"name": "❌ Помилка:", "value": error},
                    ],
                    "markdown": True,
                }
            ],
        }

    elif alert_type == "up":
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "00FF00",
            "summary": "Uptime Alert",
            "sections": [
                {
                    "activityTitle": "🟢 ✅ САЙТ ВІДНОВЛЕНО!",
                    "facts": [
                        {"name": "🌐 Сайт:", "value": site_name},
                        {"name": "📎 URL:", "value": url},
                        {"name": "📊 Статус:", "value": str(status_code)},
                    ],
                    "markdown": True,
                }
            ],
        }

    return {"text": str(data)}


def parse_message(message: str) -> dict[str, Any]:
    """Парсить просте повідомлення на частини"""
    data = {
        "site_name": "",
        "url": "",
        "status_code": "",
        "error": "",
        "checked_at": "",
        "alert_type": "up",
    }

    lines = message.split("\n")
    for line in lines:
        if line.startswith("🔴 "):
            data["site_name"] = line.replace("🔴 ", "").replace(" - STILL DOWN", "").strip()
            data["alert_type"] = "still_down" if "STILL DOWN" in line else "down"
        elif line.startswith("🟢 "):
            data["site_name"] = line.replace("🟢 ", "").replace(" - RECOVERED", "").strip()
            data["alert_type"] = "up"
        elif line.startswith("🌐 "):
            data["url"] = line.replace("🌐 ", "").strip()
        elif line.startswith("Status: "):
            data["status_code"] = line.replace("Status: ", "").strip()
        elif line.startswith("Error: "):
            data["error"] = line.replace("Error: ", "").strip()
        elif line.startswith("Response Time: "):
            try:
                data["response_time"] = float(
                    line.replace("Response Time: ", "").replace("ms", "").strip()
                )
            except (ValueError, AttributeError):
                pass
        elif line.startswith("Time: "):
            data["checked_at"] = line.replace("Time: ", "").strip()

    return data


class NotificationService:
    """Сервіс для відправки сповіщень"""

    def __init__(self, settings: dict[str, Any]):
        """Ініціалізація сервісу сповіщень"""
        self.settings = settings

    async def send(self, message: str, methods: list[str]):
        """Відправляє сповіщення через вказані методи"""
        tasks = []
        for method in methods:
            if method == "telegram" and self.settings.get("telegram", {}).get("enabled"):
                tasks.append(send_telegram(message, self.settings["telegram"]))
            elif method == "teams" and self.settings.get("teams", {}).get("enabled"):
                tasks.append(send_teams(message, self.settings["teams"]))
            elif method == "discord" and self.settings.get("discord", {}).get("enabled"):
                tasks.append(send_discord(message, self.settings["discord"]))
            elif method == "slack" and self.settings.get("slack", {}).get("enabled"):
                tasks.append(send_slack(message, self.settings["slack"]))
            elif method == "email" and self.settings.get("email", {}).get("enabled"):
                tasks.append(send_email(message, self.settings["email"]))
            elif method == "sms" and self.settings.get("sms", {}).get("enabled"):
                tasks.append(send_sms(message, self.settings["sms"]))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


async def send_notification(
    message: Union[str, dict],
    methods: list[str],
    notify_settings: dict[str, Any],
    site_id: Optional[int] = None,
    site_name: Optional[str] = None,
):
    """Відправляє сповіщення через вказані методи"""
    tasks = []
    site_name_val = site_name or (
        message.get("site_name", "Unknown") if isinstance(message, dict) else "Unknown"
    )
    for method in methods:
        method_config = notify_settings.get(method, {})

        if not method_config.get("enabled", False):
            continue

        if method == "telegram":
            channels = method_config.get("channels", [])
            for channel in channels:
                if channel.get("token") and channel.get("chat_id"):
                    tasks.append(send_telegram(message, channel))

        elif method == "discord":
            channels = method_config.get("channels", [])
            for channel in channels:
                if channel.get("webhook_url"):
                    tasks.append(send_discord(message, channel))

        elif method == "teams":
            channels = method_config.get("channels", [])
            for channel in channels:
                if channel.get("webhook_url"):
                    tasks.append(send_teams(message, channel))

        elif method == "email":
            channels = method_config.get("channels", [])
            for channel in channels:
                if channel.get("smtp_server") and channel.get("username"):
                    tasks.append(send_email(message, channel))

        elif method == "slack":
            channels = method_config.get("channels", [])
            for channel in channels:
                if channel.get("webhook_url"):
                    tasks.append(send_slack(message, channel))

        elif method == "sms":
            tasks.append(send_sms(message, method_config))

        elif method == "webhook":
            channels = method_config.get("channels", [])
            for channel in channels:
                if channel.get("webhook_url"):
                    tasks.append(send_webhook(message, channel))

        elif method == "pushover":
            channels = method_config.get("channels", [])
            for channel in channels:
                if channel.get("user_key") and channel.get("token"):
                    tasks.append(send_pushover(message, channel))

        elif method == "gotify":
            channels = method_config.get("channels", [])
            for channel in channels:
                if channel.get("server_url") and channel.get("token"):
                    tasks.append(send_gotify(message, channel))

        elif method == "ntfy":
            channels = method_config.get("channels", [])
            for channel in channels:
                if channel.get("topic"):
                    tasks.append(send_ntfy(message, channel))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                increment_metric("notifications_failed")
            else:
                increment_metric("notifications_sent")

    if site_id is not None:
        try:
            from . import models
            from .state import DB_PATH

            for method in methods:
                await models.log_notification(
                    DB_PATH,
                    site_id,
                    site_name_val,
                    method,
                    "sent",
                    str(message)[:100],
                )
        except Exception:
            pass


async def send_telegram(message: Union[str, dict], settings: dict[str, Any]):
    """Відправляє повідомлення в Telegram"""
    token = settings.get("token")
    chat_id = settings.get("chat_id")

    if not token or not chat_id:
        return

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        if isinstance(message, dict):
            alert_type = message.get("alert_type", "down")
            text = format_telegram_message(message, alert_type)
        else:
            data = parse_message(message)
            alert_type = data.get("alert_type", "down")
            text = format_telegram_message(data, alert_type)

        payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

        if settings.get("message_thread_id"):
            payload["message_thread_id"] = int(settings["message_thread_id"])

        if alert_type in ("down", "still_down"):
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [
                        {
                            "text": "✅ Acknowledge",
                            "callback_data": f"ack_{message.get('site_name', '')}"[:64],
                        },
                        {
                            "text": "🔇 Silence 1h",
                            "callback_data": f"silence1h_{message.get('site_name', '')}"[:64],
                        },
                        {
                            "text": "🔕 Silence 6h",
                            "callback_data": f"silence6h_{message.get('site_name', '')}",
                        },
                    ]
                ]
            }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error("Telegram API error: %s - %s", response.status, error_text)
    except Exception as e:
        logger.error("Telegram error: %s", e)


async def send_teams(message: Union[str, dict], settings: dict[str, Any]):
    """Відправляє повідомлення в Microsoft Teams"""
    webhook_url = settings.get("webhook_url")
    if not webhook_url:
        return

    try:
        if isinstance(message, dict):
            alert_type = message.get("alert_type", "down")
            payload = format_teams_message(message, alert_type)
        else:
            data = parse_message(message)
            alert_type = "down" if "🔴" in message else "up"
            if "STILL DOWN" in message:
                alert_type = "still_down"
            payload = format_teams_message(data, alert_type)

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status not in [200, 204]:
                    logger.error("Teams API error: %s", response.status)
    except Exception as e:
        logger.error("Teams error: %s", e)


async def send_discord(message: Union[str, dict], settings: dict[str, Any]):
    """Відправляє повідомлення в Discord"""
    webhook_url = settings.get("webhook_url")
    if not webhook_url:
        return

    try:
        if isinstance(message, dict):
            alert_type = message.get("alert_type", "down")
            payload = format_discord_message(message, alert_type)
        else:
            data = parse_message(message)
            alert_type = "down" if "🔴" in message else "up"
            if "STILL DOWN" in message:
                alert_type = "still_down"
            payload = format_discord_message(data, alert_type)

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status not in [200, 204]:
                    logger.error("Discord API error: %s", response.status)
    except Exception as e:
        logger.error("Discord error: %s", e)


async def send_slack(message: Union[str, dict], settings: dict[str, Any]):
    """Відправляє повідомлення в Slack"""
    webhook_url = settings.get("webhook_url")
    if not webhook_url:
        return

    try:
        if isinstance(message, dict):
            text = message.get("error", str(message))
        else:
            text = message
        payload = {"text": text}
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status not in [200, 204]:
                    logger.error("Slack API error: %s", response.status)
    except Exception as e:
        logger.error("Slack error: %s", e)


async def send_email(message: Union[str, dict], settings: dict[str, Any]):
    """Відправляє email"""
    if isinstance(message, dict):
        message = f"Uptime Monitor Alert ({message.get('alert_type', 'unknown')}): {message.get('site_name', 'N/A')} - {message.get('error', '')}"
    smtp_server = settings.get("smtp_server")
    smtp_port = settings.get("smtp_port", 587)
    username = settings.get("username")
    password = settings.get("password")
    to_email = settings.get("to_email")

    if not all([smtp_server, username, password, to_email]):
        return

    try:
        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = "Uptime Monitor Alert"
        msg["From"] = username
        msg["To"] = to_email

        def _send():
            with smtplib.SMTP(str(smtp_server), int(smtp_port), timeout=15) as server:
                server.starttls()
                server.login(str(username), str(password))
                server.send_message(msg)

        await asyncio.to_thread(_send)
    except Exception as e:
        logger.error("Email error: %s", e)


async def send_sms(message: Union[str, dict], settings: dict[str, Any]):
    """Відправляє SMS через Twilio"""
    account_sid = settings.get("account_sid")
    auth_token = settings.get("auth_token")
    from_number = settings.get("from_number")
    to_number = settings.get("to_number")

    if not all([account_sid, auth_token, from_number, to_number]):
        return

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        auth = aiohttp.BasicAuth(str(account_sid), str(auth_token))
        payload = {
            "From": str(from_number),
            "To": str(to_number),
            "Body": message[:1600],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload, auth=auth) as response:
                if response.status not in [200, 201]:
                    logger.error("SMS API error: %s", response.status)
    except Exception as e:
        logger.error("SMS error: %s", e)


async def send_webhook(message: Union[str, dict], settings: dict[str, Any]):
    """Відправляє кастомне POST-сповіщення (webhook)"""
    webhook_url = settings.get("webhook_url")
    if not webhook_url:
        return

    try:
        if isinstance(message, dict):
            payload = message
        else:
            payload = {
                "alert_type": "info",
                "message": message,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status not in [200, 201, 202, 204]:
                    logger.error("Webhook HTTP error: %s", response.status)
    except Exception as e:
        logger.error("Webhook error: %s", e)


async def send_pushover(message: Union[str, dict], settings: dict[str, Any]):
    """Відправляє Pushover сповіщення"""
    user_key = settings.get("user_key")
    token = settings.get("token")

    if not user_key or not token:
        return

    try:
        if isinstance(message, dict):
            title = f"Uptime Monitor — {message.get('site_name', 'Alert')}"
            text = message.get("error") or message.get("alert_type", "unknown")
        else:
            title = "Uptime Monitor"
            text = message[:1024]

        payload = {
            "token": token,
            "user": user_key,
            "title": title,
            "message": text,
            "priority": 1,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.pushover.net/1/messages.json",
                data=payload,
            ) as response:
                if response.status not in [200, 201]:
                    logger.error("Pushover API error: %s", response.status)
    except Exception as e:
        logger.error("Pushover error: %s", e)


async def send_gotify(message: Union[str, dict], settings: dict[str, Any]):
    """Відправляє Gotify сповіщення"""
    server_url = settings.get("server_url", "").rstrip("/")
    token = settings.get("token")

    if not server_url or not token:
        return

    try:
        if isinstance(message, dict):
            title = message.get("site_name", "Uptime Monitor")
            text = message.get("error") or message.get("alert_type", "unknown")
        else:
            title = "Uptime Monitor"
            text = message

        payload = {"title": title, "message": text, "priority": 5}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{server_url}/message?token={token}",
                json=payload,
            ) as response:
                if response.status not in [200, 201]:
                    logger.error("Gotify API error: %s", response.status)
    except Exception as e:
        logger.error("Gotify error: %s", e)


async def send_ntfy(message: Union[str, dict], settings: dict[str, Any]):
    """Відправляє ntfy.sh сповіщення"""
    topic = settings.get("topic")
    server_url = settings.get("server_url", "https://ntfy.sh").rstrip("/")

    if not topic:
        return

    try:
        if isinstance(message, dict):
            title = message.get("site_name", "Uptime Monitor")
            text = message.get("error") or message.get("alert_type", "unknown")
        else:
            title = "Uptime Monitor"
            text = message

        payload = {"topic": topic, "title": title, "message": text}
        headers = {"Title": title}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{server_url}/{topic}",
                json=payload,
                headers=headers,
            ) as response:
                if response.status not in [200, 201, 202]:
                    logger.error("ntfy API error: %s", response.status)
    except Exception as e:
        logger.error("ntfy error: %s", e)
