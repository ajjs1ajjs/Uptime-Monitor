from datetime import datetime, timedelta, timezone

from ..database import get_db_connection
from ..logger import logger


async def is_under_maintenance(site_id: int) -> bool:
    current_time = datetime.now(timezone.utc)
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                """SELECT * FROM maintenance_windows
                   WHERE is_active = 1 AND (site_id = ? OR site_id IS NULL)""",
                (site_id,),
            ) as c:
                rows = await c.fetchall()
    except Exception as e:
        logger.error("Error checking maintenance windows for site %d: %s", site_id, e)
        return False

    for row in rows:
        rule_type = row["rule_type"]
        if rule_type == "one_off":
            try:
                start_str = row["start_time"].replace("Z", "")
                end_str = row["end_time"].replace("Z", "")
                start = datetime.fromisoformat(start_str)
                end = datetime.fromisoformat(end_str)
                if start <= current_time <= end:
                    return True
            except Exception:
                pass
        elif rule_type == "daily":
            try:
                start_h, start_m = map(int, row["start_hour_minute"].split(":"))
                duration = int(row["duration_minutes"])
                today_start = current_time.replace(
                    hour=start_h, minute=start_m, second=0, microsecond=0
                )
                today_end = today_start + timedelta(minutes=duration)

                if today_start <= current_time <= today_end:
                    return True

                # Check if yesterday's window spans into today (midnight crossing)
                yesterday_start = today_start - timedelta(days=1)
                yesterday_end = yesterday_start + timedelta(minutes=duration)
                if yesterday_start <= current_time <= yesterday_end:
                    return True
            except Exception:
                pass
        elif rule_type == "weekly":
            try:
                target_dow = int(row["day_of_week"])
                start_h, start_m = map(int, row["start_hour_minute"].split(":"))
                duration = int(row["duration_minutes"])

                current_dow = current_time.isoweekday()
                diff_days = (target_dow - current_dow) % 7
                target_start = (current_time + timedelta(days=diff_days)).replace(
                    hour=start_h, minute=start_m, second=0, microsecond=0
                )
                target_end = target_start + timedelta(minutes=duration)

                if target_start <= current_time <= target_end:
                    return True

                prev_start = target_start - timedelta(weeks=1)
                prev_end = prev_start + timedelta(minutes=duration)
                if prev_start <= current_time <= prev_end:
                    return True
            except Exception:
                pass
    return False
