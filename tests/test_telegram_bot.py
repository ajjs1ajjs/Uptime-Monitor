"""Tests for the Telegram button-polling helpers."""
from Uptime_Robot.telegram_bot import _collect_telegram_tokens


class TestCollectTelegramTokens:
    def test_disabled_returns_empty(self):
        settings = {"telegram": {"enabled": False, "channels": [{"token": "t1"}]}}
        assert _collect_telegram_tokens(settings) == []

    def test_missing_telegram_key_returns_empty(self):
        assert _collect_telegram_tokens({}) == []

    def test_dedupes_shared_bot_token(self):
        settings = {
            "telegram": {
                "enabled": True,
                "channels": [
                    {"token": "shared", "chat_id": "-1"},
                    {"token": "shared", "chat_id": "-2"},
                    {"token": "other", "chat_id": "-3"},
                ],
            }
        }
        assert _collect_telegram_tokens(settings) == ["shared", "other"]

    def test_skips_channels_without_token(self):
        settings = {"telegram": {"enabled": True, "channels": [{"chat_id": "-1"}]}}
        assert _collect_telegram_tokens(settings) == []
