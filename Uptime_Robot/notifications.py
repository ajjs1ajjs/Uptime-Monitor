"""Модуль для відправки сповіщень"""

import asyncio
import aiohttp
import smtplib
import json
import os
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
try:
    from .logger import logger
except ImportError:
    from logger import logger


def format_telegram_message(data: Dict[str, Any], alert_type: str = "down") -> str:
    """Форматує повідомлення для Telegram"""
    site_name = data.get("site_name", "Unknown")
    url = data.get("url", "")
    status_code = data.get("status_code", "N/A")
    error = data.get("error", "None")
    response_time = data.get("response_time", 0)
    checked_at = data.get("checked_at", "")

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
<b>⏱️ Час відповіді:</b> <code>{round(response_time, 2) if response_time else 0}ms</code>
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


def format_discord_message(
    data: Dict[str, Any], alert_type: str = "down"
) -> Dict[str, Any]:
    """Форматує повідомлення для Discord (embed)"""
    site_name = data.get("site_name", "Unknown")
    url = data.get("url", "")
    status_code = data.get("status_code", "N/A")
    error = data.get("error", "None")
    response_time = data.get("response_time", 0)
    checked_at = data.get("checked_at", "")

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
                    "timestamp": datetime.now().isoformat(),
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
                    "timestamp": datetime.now().isoformat(),
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
                            "value": f"`{round(response_time, 2) if response_time else 0}ms`",
                            "inline": True,
                        },
                        {"name": "🕐 Час", "value": checked_at, "inline": True},
                    ],
                    "footer": {"text": "Uptime Monitor"},
                    "timestamp": datetime.now().isoformat(),
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
                    "timestamp": datetime.now().isoformat(),
                }
            ]
        }

    return {"content": str(data)}


def format_teams_message(
    data: Dict[str, Any], alert_type: str = "down"
) -> Dict[str, Any]:
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


def parse_message(message: str) -> Dict[str, Any]:
    """Парсить просте повідомлення на частини"""
    data = {
        "site_name": "",
        "url": "",
        "status_code": "",
        "error": "",
        "checked_at": "",
    }

    lines = message.split("\n")
    for line in lines:
        if line.startswith("🔴 "):
            data["site_name"] = (
                line.replace("🔴 ", "").replace(" - STILL DOWN", "").strip()
            )
        elif line.startswith("🟢 "):
            data["site_name"] = (
                line.replace("🟢 ", "").replace(" - RECOVERED", "").strip()
            )
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
            except:
                pass
        elif line.startswith("Time: "):
            data["checked_at"] = line.replace("Time: ", "").strip()

    return data


class NotificationService:
    """Сервіс для відправки сповіщень"""

    def __init__(self, settings: Dict[str, Any]):
        """Ініціалізація сервісу сповіщень"""
        self.settings = settings

    async def send(self, message: str, methods: List[str]):
        """Відправляє сповіщення через вказані методи"""
        tasks = []
        for method in methods:
            if method == "telegram" and self.settings.get("telegram", {}).get(
                "enabled"
            ):
                tasks.append(send_telegram(message, self.settings["telegram"]))
            elif method == "teams" and self.settings.get("teams", {}).get("enabled"):
                tasks.append(send_teams(message, self.settings["teams"]))
            elif method == "discord" and self.settings.get("discord", {}).get(
                "enabled"
            ):
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
    message: Union[str, Dict], methods: List[str], notify_settings: Dict[str, Any]
):
    """Відправляє сповіщення через вказані методи"""
    tasks = []
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

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def send_telegram(message: Union[str, Dict], settings: Dict[str, Any]):
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
            alert_type = "down" if "🔴" in message else "up"
            if "STILL DOWN" in message:
                alert_type = "still_down"
            text = format_telegram_message(data, alert_type)

        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(
                        f"Telegram API error: {response.status} - {error_text}"
                    )
    except Exception as e:
        logger.error(f"Telegram error: {e}")


async def send_teams(message: Union[str, Dict], settings: Dict[str, Any]):
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
                    logger.error(f"Teams API error: {response.status}")
    except Exception as e:
        logger.error(f"Teams error: {e}")


async def send_discord(message: Union[str, Dict], settings: Dict[str, Any]):
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
                    logger.error(f"Discord API error: {response.status}")
    except Exception as e:
        logger.error(f"Discord error: {e}")


async def send_slack(message: str, settings: Dict[str, Any]):
    """Відправляє повідомлення в Slack"""
    webhook_url = settings.get("webhook_url")
    if not webhook_url:
        return

    try:
        payload = {"text": message}
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status not in [200, 204]:
                    logger.error(f"Slack API error: {response.status}")
    except Exception as e:
        logger.error(f"Slack error: {e}")


async def send_email(message: str, settings: Dict[str, Any]):
    """Відправляє email"""
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
            with smtplib.SMTP(str(smtp_server), int(smtp_port)) as server:
                server.starttls()
                server.login(str(username), str(password))
                server.send_message(msg)

        await asyncio.to_thread(_send)
    except Exception as e:
        logger.error(f"Email error: {e}")


async def send_sms(message: str, settings: Dict[str, Any]):
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
                    logger.error(f"SMS API error: {response.status}")
    except Exception as e:
        logger.error(f"SMS error: {e}")
