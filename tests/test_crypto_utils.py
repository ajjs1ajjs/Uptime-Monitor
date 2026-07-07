"""Tests for notify-secret redaction (dashboard leak fix)."""
from Uptime_Robot.crypto_utils import redact_notify_secrets


class TestRedactNotifySecrets:
    def test_blanks_secret_fields_but_keeps_shape(self):
        settings = {
            "telegram": {
                "enabled": True,
                "channels": [
                    {
                        "id": "ch_1",
                        "name": "Forum",
                        "token": "123:REALTOKEN",
                        "chat_id": "-100123",
                        "message_thread_id": "41",
                    }
                ],
            }
        }
        redacted = redact_notify_secrets(settings)
        assert redacted["telegram"]["enabled"] is True
        ch = redacted["telegram"]["channels"][0]
        assert ch["id"] == "ch_1"
        assert ch["name"] == "Forum"
        assert ch["token"] == ""
        assert ch["chat_id"] == "-100123"

    def test_leaves_non_secret_settings_untouched(self):
        settings = {"discord": {"enabled": False, "channels": []}}
        assert redact_notify_secrets(settings) == settings

    def test_does_not_mutate_input(self):
        settings = {"telegram": {"enabled": True, "channels": [{"id": "a", "token": "secret"}]}}
        redact_notify_secrets(settings)
        assert settings["telegram"]["channels"][0]["token"] == "secret"
