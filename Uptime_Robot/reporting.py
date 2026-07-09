"""SLA report generation (PDF via weasyprint)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .database import get_db_connection
from .logger import logger

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
# autoescape on so site names/URLs from the DB can't inject HTML into the report.
_JINJA_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


async def generate_sla_report(days: int = 30) -> dict:
    """Collect SLA data for the report."""
    async with get_db_connection() as conn:
        async with conn.execute("SELECT id, name, url FROM sites") as c:
            sites_raw = await c.fetchall()
            sites = [dict(s) for s in sites_raw]

        window = f"-{days} days"

        async with conn.execute(
            """SELECT site_id,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_count,
                    AVG(response_time) as avg_rt
                  FROM status_history
                  WHERE checked_at >= datetime('now', ?)
                  GROUP BY site_id""",
            (window,),
        ) as c:
            stats_rows = await c.fetchall()

        stats_map = {}
        for r in stats_rows:
            stats_map[r["site_id"]] = r

        # Bulk incident count: count transitions into down/slow per site
        async with conn.execute(
            """SELECT site_id, COUNT(*) as incidents FROM (
                   SELECT site_id, status,
                          LAG(status) OVER (PARTITION BY site_id ORDER BY checked_at) AS prev
                   FROM status_history
                   WHERE checked_at >= datetime('now', ?)
               ) sub
               WHERE sub.status IN ('down', 'slow')
                 AND (sub.prev IS NULL OR sub.prev NOT IN ('down', 'slow'))
               GROUP BY site_id""",
            (window,),
        ) as c:
            incidents_rows = await c.fetchall()

        incidents_map = {r["site_id"]: r["incidents"] for r in incidents_rows}

        report_sites = []
        total_incidents = 0
        uptime_sum = 0.0
        rt_sum = 0.0

        for s in sites:
            sid = s["id"]
            stats = stats_map.get(sid)
            total = (stats["total"] if stats else 0) or 0
            up_count = (stats["up_count"] if stats else 0) or 0
            uptime = (up_count / total * 100) if total > 0 else 100.0
            avg_rt = (stats["avg_rt"] if stats else 0) or 0
            incidents = incidents_map.get(sid, 0)

            report_sites.append(
                {
                    "name": s["name"],
                    "url": s["url"],
                    "uptime": round(uptime, 2),
                    "avg_response_time": round(avg_rt, 1),
                    "total_checks": total,
                    "incidents": incidents,
                }
            )
            total_incidents += incidents
            uptime_sum += uptime
            rt_sum += avg_rt

        now = datetime.now(timezone.utc)
        return {
            "period_days": days,
            "generated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
            "period_end": now.strftime("%Y-%m-%d %H:%M UTC"),
            "period_start": (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M UTC"),
            "total_sites": len(report_sites),
            "overall_uptime": round(uptime_sum / len(report_sites), 2) if report_sites else 100.0,
            "overall_avg_rt": round(rt_sum / len(report_sites), 1) if report_sites else 0,
            "total_incidents": total_incidents,
            "sites": report_sites,
        }


async def render_sla_pdf(days: int = 30) -> bytes:
    """Generate an SLA report PDF."""
    try:
        from weasyprint import HTML
    except ImportError:
        logger.error("weasyprint not installed — cannot generate PDF")
        return b""

    data = await generate_sla_report(days)
    html_str = _JINJA_ENV.get_template("sla_report_pdf.html").render(**data)
    pdf_bytes = HTML(string=html_str).write_pdf()
    return pdf_bytes
