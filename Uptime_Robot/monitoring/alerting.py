from typing import Any, Dict

from ..config_manager import load_config

SENSITIVE_DEFAULTS = {
    "request_timeout_seconds": 60,
    "down_failures_threshold": 1,
    "up_success_threshold": 1,
    "still_down_repeat_seconds": 300,
    "treat_4xx_as_down": True,
    "ssl_notification_days": 14,
    "ssl_notification_cooldown_seconds": 21600,
    "ssl_check_interval_hours": 6,
    "verify_ssl": True,
}


def get_alert_policy() -> Dict[str, Any]:
    try:
        config = load_config() or {}
    except Exception:
        config = {}

    policy = (config.get("alert_policy") or {}).copy()

    result = SENSITIVE_DEFAULTS.copy()
    result.update({k: v for k, v in policy.items() if v is not None})

    try:
        result["request_timeout_seconds"] = max(1, int(result.get("request_timeout_seconds", 60)))
    except Exception:
        result["request_timeout_seconds"] = 60

    try:
        result["down_failures_threshold"] = max(1, int(result.get("down_failures_threshold", 1)))
    except Exception:
        result["down_failures_threshold"] = 1

    try:
        result["up_success_threshold"] = max(1, int(result.get("up_success_threshold", 1)))
    except Exception:
        result["up_success_threshold"] = 1

    try:
        result["still_down_repeat_seconds"] = max(
            60, int(result.get("still_down_repeat_seconds", 300))
        )
    except Exception:
        result["still_down_repeat_seconds"] = 300

    try:
        result["ssl_notification_days"] = max(1, int(result.get("ssl_notification_days", 14)))
    except Exception:
        result["ssl_notification_days"] = 14

    try:
        result["ssl_notification_cooldown_seconds"] = max(
            300, int(result.get("ssl_notification_cooldown_seconds", 21600))
        )
    except Exception:
        result["ssl_notification_cooldown_seconds"] = 21600

    try:
        result["ssl_check_interval_hours"] = max(1, int(result.get("ssl_check_interval_hours", 6)))
    except Exception:
        result["ssl_check_interval_hours"] = 6

    result["treat_4xx_as_down"] = bool(result.get("treat_4xx_as_down", True))
    return result
