import time
from typing import Any

from ..config_manager import load_config

SENSITIVE_DEFAULTS = {
    "request_timeout_seconds": 30,
    "grace_period_seconds": 0,
    "up_success_threshold": 2,
    "still_down_repeat_seconds": 600,
    "treat_4xx_as_down": True,
    "ssl_notification_days": [30, 14, 7, 5, 3, 1],
    "ssl_notification_cooldown_seconds": 21600,
    "ssl_check_interval_hours": 6,
    "verify_ssl": True,
    "retry_delays": [30, 30],
    "max_retries": 2,
    "flapping_threshold": 3,
    "flapping_window_seconds": 300,
    "flapping_suppression_seconds": 600,
}

_cache: dict[str, Any] | None = None
_cache_time: float = 0
_CACHE_TTL: int = 30


def _clamp(val, low, high, default):
    try:
        v = int(val)
        return max(low, min(v, high))
    except Exception:
        return default


def _migrate_old_policy(policy: dict) -> dict:
    out = dict(policy)
    if "down_failures_threshold" in out and "grace_period_seconds" not in out:
        old = int(out.pop("down_failures_threshold"))
        out["grace_period_seconds"] = old * 30
    old_days = out.get("ssl_notification_days")
    if isinstance(old_days, (int, float)):
        out["ssl_notification_days"] = [old_days]
    return out


def get_alert_policy() -> dict[str, Any]:
    global _cache, _cache_time
    now = time.time()
    if _cache is not None and (now - _cache_time) < _CACHE_TTL:
        return _cache

    try:
        config = load_config() or {}
    except Exception:
        config = {}

    raw = (config.get("alert_policy") or {}).copy()
    raw = _migrate_old_policy(raw)

    result = SENSITIVE_DEFAULTS.copy()
    result.update(raw)

    result["request_timeout_seconds"] = _clamp(result.get("request_timeout_seconds"), 1, 300, 30)
    result["grace_period_seconds"] = _clamp(result.get("grace_period_seconds"), 0, 3600, 0)
    result["up_success_threshold"] = _clamp(result.get("up_success_threshold"), 1, 20, 2)
    result["still_down_repeat_seconds"] = _clamp(
        result.get("still_down_repeat_seconds"), 60, 86400, 600
    )
    result["ssl_notification_cooldown_seconds"] = _clamp(
        result.get("ssl_notification_cooldown_seconds"), 300, 86400, 21600
    )
    result["ssl_check_interval_hours"] = _clamp(result.get("ssl_check_interval_hours"), 1, 168, 6)
    result["flapping_threshold"] = _clamp(result.get("flapping_threshold"), 2, 20, 3)
    result["flapping_window_seconds"] = _clamp(result.get("flapping_window_seconds"), 60, 3600, 300)
    result["flapping_suppression_seconds"] = _clamp(
        result.get("flapping_suppression_seconds"), 60, 7200, 600
    )
    result["max_retries"] = _clamp(result.get("max_retries"), 0, 10, 2)

    delays = result.get("retry_delays")
    if not isinstance(delays, list) or not delays:
        delays = [30, 30]
    result["retry_delays"] = [max(1, min(int(d), 300)) for d in delays[:10]]

    ssl_days = result.get("ssl_notification_days")
    if not isinstance(ssl_days, list) or not ssl_days:
        ssl_days = [30, 14, 7, 5, 3, 1]
    result["ssl_notification_days"] = sorted({int(d) for d in ssl_days if d > 0}, reverse=True)

    result["treat_4xx_as_down"] = bool(result.get("treat_4xx_as_down", True))
    result["verify_ssl"] = bool(result.get("verify_ssl", True))

    _cache = result
    _cache_time = now
    return result
