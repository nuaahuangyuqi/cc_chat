"""Menu bar monitoring data shared by the native menu and settings page."""

from datetime import datetime, timedelta
from decimal import Decimal

from .errors import CCAskError
from .runtime import preferences, update_preferences
from .usage import SHANGHAI

PERIODS = {"today": "今日", "7d": "近 7 天", "30d": "近 30 天", "all": "全部时间"}


def monitor_settings(settings):
    data = preferences(settings)
    period = data.get("menubar_period", "today")
    return {
        "project_ids": data.get("menubar_project_ids", []),
        "period": period if period in PERIODS else "today",
    }


def save_monitor_settings(settings, db, project_ids, period):
    available = {p["id"] for p in db.rows("SELECT id FROM projects WHERE archived=0")}
    if set(project_ids) - available:
        raise CCAskError("所选项目已归档或删除，请重新选择。", "invalid_monitor_projects")
    ids = list(dict.fromkeys(project_ids))
    update_preferences(settings, {"menubar_project_ids": ids, "menubar_period": period})
    return monitor_settings(settings)


def aggregate(groups):
    result = {}
    for field in ("requests", "successes", "pending", "unknown_usage"):
        result[field] = sum(g[field] for g in groups)
    for field in ("fresh_input", "output_tokens", "cache_read", "cache_write", "total_tokens"):
        known = [g[field] for g in groups if g[field] is not None]
        result[field] = sum(known) if known else None
    costs = [Decimal(g["cost"]) for g in groups if g["cost"] is not None]
    result["cost"] = str(sum(costs)) if costs else None
    if not result["requests"]:
        for field in ("fresh_input", "output_tokens", "cache_read", "cache_write", "total_tokens"):
            result[field] = 0
        result["cost"] = "0"
    result["success_rate"] = (
        result["successes"] / result["requests"] if result["requests"] else None
    )
    return result


def monitor_snapshot(settings, db, usage):
    config = monitor_settings(settings)
    projects = {p["id"]: p for p in db.rows("SELECT id,name FROM projects WHERE archived=0")}
    ids = [p for p in config["project_ids"] if p in projects]
    now = datetime.now(SHANGHAI)
    days = {"today": 1, "7d": 7, "30d": 30}.get(config["period"])
    start = (
        (now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1))
        .timestamp()
        if days else None
    )
    report = usage.report(start=start, group_by="project")
    by_id = {g["key"]: g for g in report["groups"]}
    empty = aggregate([])
    rows = (
        [{**by_id.get(p, empty), "key": p, "label": projects[p]["name"]} for p in ids]
        if ids else sorted(report["groups"], key=lambda g: g["total_tokens"] or 0, reverse=True)
    )
    return {
        "scope": "所选项目" if ids else "全局用量",
        "period": config["period"],
        "period_label": PERIODS[config["period"]],
        "project_ids": ids,
        "summary": aggregate(rows) if ids else aggregate([report["summary"]]),
        "rows": rows,
        "last_sync": report["last_sync"],
        "sync_error": report["sync_error"],
    }
