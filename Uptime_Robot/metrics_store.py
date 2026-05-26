"""Shared metrics store to avoid circular imports between main and monitoring."""

import time

_monitor_last_heartbeat: float = 0.0

_metrics = {
    "notifications_sent": 0,
    "notifications_failed": 0,
    "checks_total": 0,
    "checks_failed": 0,
}


def get_metrics() -> dict:
    return dict(_metrics)


def get_heartbeat_age() -> float:
    if _monitor_last_heartbeat > 0:
        return time.time() - _monitor_last_heartbeat
    return -1.0


def update_monitor_heartbeat():
    global _monitor_last_heartbeat
    _monitor_last_heartbeat = time.time()


def increment_metric(key: str, count: int = 1):
    if key in _metrics:
        _metrics[key] += count
