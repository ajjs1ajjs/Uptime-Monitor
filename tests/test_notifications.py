"""Tests for all notification formatters and dispatchers"""
from unittest.mock import AsyncMock, patch

import pytest

from Uptime_Robot.notifications import (
    format_discord_message,
    format_teams_message,
    format_telegram_message,
    send_notification,
)

SAMPLE_DATA = {
    "site_name": "Test Site",
    "url": "https://test.com",
    "status_code": 500,
    "error": "Connection Timeout",
    "response_time": 150.5,
    "checked_at": "2026-05-26T10:00:00",
}


class TestTelegramFormatter:
    def test_down_message(self):
        msg = format_telegram_message(SAMPLE_DATA, "down")
        assert "Test Site" in msg
        assert "500" in msg
        assert "Connection Timeout" in msg
        assert "НЕ ПРАЦЮЄ" in msg

    def test_still_down_message(self):
        msg = format_telegram_message(SAMPLE_DATA, "still_down")
        assert "ДОСІ НЕ ПРАЦЮЄ" in msg
        assert "триває" in msg

    def test_up_message(self):
        data = {**SAMPLE_DATA, "status_code": 200, "error": "", "response_time": 150}
        msg = format_telegram_message(data, "up")
        assert "ВІДНОВЛЕНО" in msg
        assert "🟢" in msg

    def test_ssl_expired_message(self):
        data = {"site_name": "Test", "url": "https://test.com", "days_left": 0, "expire_date": "2025-01-01", "urgency": "КРИТИЧНО"}
        msg = format_telegram_message(data, "ssl")
        assert "ПРОСТРОЧЕНИЙ" in msg

    def test_ssl_warning_message(self):
        data = {"site_name": "Test", "url": "https://test.com", "days_left": 5, "expire_date": "2026-06-01", "urgency": "УВАГА"}
        msg = format_telegram_message(data, "ssl")
        assert "5 днів" in msg
        assert "🟠" in msg

    def test_ssl_ok_message(self):
        data = {"site_name": "Test", "url": "https://test.com", "days_left": 14, "expire_date": "2026-06-10", "urgency": "УВАГА"}
        msg = format_telegram_message(data, "ssl")
        assert "14 днів" in msg
        assert "🟡" in msg

    def test_unknown_type(self):
        result = format_telegram_message(SAMPLE_DATA, "unknown_type")
        assert isinstance(result, str)

    def test_default_data(self):
        msg = format_telegram_message({}, "down")
        assert "Unknown" in msg

    def test_up_with_missing_response_time(self):
        data = {"site_name": "X", "url": "x.com", "status_code": 200, "checked_at": "now"}
        msg = format_telegram_message(data, "up")
        assert "ВІДНОВЛЕНО" in msg


class TestDiscordFormatter:
    def test_down_embed(self):
        payload = format_discord_message(SAMPLE_DATA, "down")
        embed = payload["embeds"][0]
        assert embed["color"] == 16711680
        assert "НЕ ПРАЦЮЄ" in embed["title"]
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert fields["🌐 Сайт"] == "Test Site"

    def test_up_embed(self):
        data = {**SAMPLE_DATA, "status_code": 200, "error": ""}
        payload = format_discord_message(data, "up")
        assert payload["embeds"][0]["color"] == 65280

    def test_still_down_embed(self):
        payload = format_discord_message(SAMPLE_DATA, "still_down")
        assert payload["embeds"][0]["color"] == 16711680

    def test_ssl_expired_embed(self):
        data = {"site_name": "T", "url": "https://t.com", "days_left": 3, "expire_date": "2026-06-01"}
        payload = format_discord_message(data, "ssl")
        assert payload["embeds"][0]["color"] == 16711680

    def test_ssl_upcoming_embed(self):
        data = {"site_name": "T", "url": "https://t.com", "days_left": 14, "expire_date": "2026-06-10"}
        payload = format_discord_message(data, "ssl")
        assert payload["embeds"][0]["color"] == 16776960

    def test_unknown_type(self):
        result = format_discord_message(SAMPLE_DATA, "unknown")
        assert "embeds" not in result

    def test_default_data(self):
        payload = format_discord_message({}, "down")
        assert "Unknown" in payload["embeds"][0]["fields"][0]["value"]


class TestTeamsFormatter:
    def test_down_card(self):
        card = format_teams_message(SAMPLE_DATA, "down")
        assert card["@type"] == "MessageCard"
        assert card["themeColor"] == "FF0000"
        facts = {f["name"]: f["value"] for f in card["sections"][0]["facts"]}
        assert facts["🌐 Сайт:"] == "Test Site"

    def test_up_card(self):
        data = {**SAMPLE_DATA, "status_code": 200, "error": ""}
        card = format_teams_message(data, "up")
        assert card["themeColor"] == "00FF00"

    def test_unknown_type(self):
        result = format_teams_message(SAMPLE_DATA, "unknown")
        assert "MessageCard" not in str(result)

    def test_default_data(self):
        card = format_teams_message({}, "down")
        assert card["sections"][0]["facts"][0]["value"] == "Unknown"


class TestNotificationDispatcher:
    @patch("Uptime_Robot.notifications.send_telegram", new_callable=AsyncMock)
    async def test_telegram_dispatched_when_enabled(self, mock_send):
        from Uptime_Robot.notifications import send_notification

        settings = {
            "telegram": {
                "enabled": True,
                "channels": [{"token": "x", "chat_id": "1"}],
            }
        }
        await send_notification("test message", ["telegram"], settings)
        mock_send.assert_awaited_once()

    @patch("Uptime_Robot.notifications.send_telegram", new_callable=AsyncMock)
    async def test_skips_disabled_channel(self, mock_send):
        from Uptime_Robot.notifications import send_notification

        settings = {"telegram": {"enabled": False, "channels": []}}
        await send_notification("test", ["telegram"], settings)
        mock_send.assert_not_awaited()

    @patch("Uptime_Robot.notifications.send_telegram", new_callable=AsyncMock)
    @patch("Uptime_Robot.notifications.send_discord", new_callable=AsyncMock)
    async def test_multiple_channels_dispatched(self, mock_discord, mock_telegram):
        from Uptime_Robot.notifications import send_notification

        settings = {
            "telegram": {
                "enabled": True,
                "channels": [{"token": "x", "chat_id": "1"}],
            },
            "discord": {
                "enabled": True,
                "channels": [{"webhook_url": "https://discord.com"}],
            },
        }
        await send_notification("test", ["telegram", "discord"], settings)
        mock_telegram.assert_awaited_once()
        mock_discord.assert_awaited_once()

    @patch("Uptime_Robot.notifications.send_telegram", new_callable=AsyncMock)
    @patch("Uptime_Robot.notifications.send_discord", new_callable=AsyncMock)
    async def test_one_failure_does_not_affect_others(self, mock_discord, mock_telegram):
        mock_telegram.side_effect = Exception("Network error")
        from Uptime_Robot.notifications import send_notification

        settings = {
            "telegram": {
                "enabled": True,
                "channels": [{"token": "x", "chat_id": "1"}],
            },
            "discord": {
                "enabled": True,
                "channels": [{"webhook_url": "https://discord.com"}],
            },
        }
        await send_notification("test", ["telegram", "discord"], settings)
        mock_telegram.assert_awaited_once()
        mock_discord.assert_awaited_once()


class TestParseMessage:
    def test_parse_down_message(self):
        from Uptime_Robot.notifications import parse_message

        msg = "\n".join([
            "🔴 Test Site - STILL DOWN",
            "🌐 https://test.com",
            "Status: 500",
            "Error: Timeout",
            "Time: 2026-05-26T10:00:00",
        ])
        data = parse_message(msg)
        assert data["site_name"] == "Test Site"
        assert data["url"] == "https://test.com"
        assert data["status_code"] == "500"
        assert data["error"] == "Timeout"

    def test_parse_up_message(self):
        from Uptime_Robot.notifications import parse_message

        msg = "\n".join([
            "🟢 Test Site - RECOVERED",
            "🌐 https://test.com",
            "Status: 200",
            "Response Time: 150ms",
            "Time: 2026-05-26T10:00:00",
        ])
        data = parse_message(msg)
        assert data["site_name"] == "Test Site"
        assert data["response_time"] == 150.0

    def test_parse_empty_message(self):
        from Uptime_Robot.notifications import parse_message
        data = parse_message("")
        assert data["site_name"] == ""
        assert data["url"] == ""

    def test_format_telegram_ssl_message(self):
        from Uptime_Robot.notifications import format_telegram_message
        ssl_data = SAMPLE_DATA.copy()
        ssl_data["days_left"] = 3
        ssl_data["expire_date"] = "2026-06-01"
        ssl_data["urgency"] = "ВАЖЛИВО"
        msg = format_telegram_message(ssl_data, "ssl")
        assert isinstance(msg, str)
        assert "3" in msg

    @pytest.mark.asyncio
    async def test_send_notification_empty_methods(self):
        with patch("Uptime_Robot.notifications.send_telegram", AsyncMock()):
            await send_notification({"alert_type": "down"}, [], {})
            # Should not crash

    @pytest.mark.asyncio
    async def test_send_notification_no_enabled_methods(self):
        with patch("Uptime_Robot.notifications.send_telegram", AsyncMock()):
            await send_notification(
                {"alert_type": "down"},
                ["telegram"],
                {"telegram": {"enabled": False}},
            )
            # Should not crash

    @pytest.mark.asyncio
    async def test_send_notification_single_channel(self):
        with patch("Uptime_Robot.notifications.send_telegram", AsyncMock()) as mock:
            await send_notification(
                {"alert_type": "down"},
                ["telegram"],
                {"telegram": {"enabled": True, "channels": [{"token": "x", "chat_id": "y"}]}},
            )
            mock.assert_awaited_once()
