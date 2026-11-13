import json
import sqlite3
import threading
import time
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from .db import dumps
from .errors import CCAskError

SHANGHAI = ZoneInfo("Asia/Shanghai")


def normalize(row):
    inp = row.get("input_tokens")
    out = row.get("output_tokens")
    read = row.get("cache_read_tokens") or 0
    write = row.get("cache_creation_tokens") or 0
    fresh = inp
    # Match CC Switch services/sql_helpers.rs exactly for Codex proxy rows.
    semantics = row.get("input_token_semantics", 0)
    if inp is not None and semantics == 1 and inp >= read + write:
        fresh = inp - read - write
    elif inp is not None and semantics == 0 and inp >= read:
        fresh = inp - read
    known = inp is not None and out is not None and inp + out + read + write > 0
    return {
        "fresh_input": fresh if known else None,
        "output_tokens": out if known else None,
        "cache_read": read if known else None,
        "cache_write": write if known else None,
        "total_tokens": fresh + out + read + write if known else None,
    }


class UsageService:
    def __init__(self, db, cc):
        self.db = db
        self.cc = cc
        self.last_sync = None
        self.error = None
        self._last_scan = 0.0
        self._sync_lock = threading.Lock()

    def sync(self):
        with self._sync_lock:
            return self._sync()

    def delete_project(self, project_id):
        # A sync that already read this project's request IDs must finish first.
        with self._sync_lock:
            return self.db.delete_project(project_id)

    def _sync(self):
        # Revisit pending requests and a rolling overlap; delayed inserts and corrections are
        # upserted, rather than relying on timestamp high-water marks or insertion order.
        rows = self.db.rows(
            "SELECT * FROM requests WHERE usage_synced=0 OR started_at>=?", (self._last_scan - 60,)
        )
        count = 0
        try:
            for offset in range(0, len(rows), 200):
                requests = {r["tracking_id"]: r for r in rows[offset : offset + 200]}
                for log in self.cc.logs_for(list(requests)):
                    tracking = log.get("session_id", "").removeprefix("codex_")
                    request = requests.get(tracking)
                    if not request:
                        continue
                    normalized = normalize(log)
                    with self.db.connect() as c:
                        c.execute(
                            "INSERT INTO usage VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                            "ON CONFLICT(source_id) DO UPDATE SET fresh_input=excluded.fresh_input,"
                            "output_tokens=excluded.output_tokens,cache_read=excluded.cache_read,"
                            "cache_write=excluded.cache_write,total_tokens=excluded.total_tokens,"
                            "cost=excluded.cost,latency_ms=excluded.latency_ms,"
                            "status_code=excluded.status_code,raw=excluded.raw",
                            (
                                log["request_id"],
                                request["id"],
                                log["provider_id"],
                                log["model"],
                                normalized["fresh_input"],
                                normalized["output_tokens"],
                                normalized["cache_read"],
                                normalized["cache_write"],
                                normalized["total_tokens"],
                                log.get("total_cost_usd"),
                                log.get("latency_ms"),
                                log.get("status_code"),
                                log["created_at"],
                                dumps({k: v for k, v in log.items() if k != "error_message"}),
                            ),
                        )
                        c.execute("UPDATE requests SET usage_synced=1 WHERE id=?", (request["id"],))
                    count += 1
            self.last_sync = time.time()
            self._last_scan = self.last_sync
            self.error = None
        except (CCAskError, sqlite3.Error, OSError, ValueError, TypeError, KeyError):
            # CC Switch can be closed, busy or upgrading. Its detailed exceptions must not
            # escape the background worker or disclose upstream data.
            self.error = "暂时无法同步 CC Switch 用量，请检查连接。"
        return {"rows": count, "last_sync": self.last_sync, "error": self.error}

    def report(
        self,
        project_id=None,
        start=None,
        end=None,
        group_by="connection",
        account_id=None,
        model=None,
        connection_id=None,
    ):
        clauses, args = [], []
        for field, value in [("r.project_id", project_id), ("r.connection_version", connection_id)]:
            if value:
                clauses.append(field + "=?")
                args.append(value)
        if start is not None:
            clauses.append("r.started_at>=?")
            args.append(start)
        if end is not None:
            clauses.append("r.started_at<?")
            args.append(end)
        sql = (
            "SELECT r.*,p.name AS project_name,p.archived,c.provider_name,c.account_id,c.account_label "
            "FROM requests r JOIN projects p ON p.id=r.project_id "
            "LEFT JOIN connections c ON c.id=r.connection_version"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        requests = self.db.rows(sql + " ORDER BY r.started_at DESC", args)
        usage = defaultdict(list)
        ids = [r["id"] for r in requests]
        for offset in range(0, len(ids), 500):
            batch = ids[offset : offset + 500]
            if batch:
                marks = ",".join("?" for _ in batch)
                for row in self.db.rows(
                    f"SELECT * FROM usage WHERE request_id IN ({marks})", batch
                ):
                    usage[row["request_id"]].append(row)
        records = []
        for r in requests:
            snapshot = json.loads(r["snapshot"])
            logs = usage[r["id"]]
            actual_model = logs[-1]["model"] if logs else snapshot.get("model", "")
            if account_id and r["account_id"] != account_id:
                continue
            if model and actual_model != model:
                continue
            values = {}
            for field in [
                "fresh_input",
                "output_tokens",
                "cache_read",
                "cache_write",
                "total_tokens",
            ]:
                known = [x[field] for x in logs if x[field] is not None]
                values[field] = sum(known) if known else None
            costs = []
            for log in logs:
                if log["cost"] is not None:
                    try:
                        costs.append(Decimal(log["cost"]))
                    except InvalidOperation:
                        pass
            elapsed = ((r["finished_at"] or time.time()) - r["started_at"]) * 1000
            values.update(
                {
                    "id": r["id"],
                    "project_id": r["project_id"],
                    "project_name": r["project_name"],
                    "archived": bool(r["archived"]),
                    "mode": snapshot.get("mode"),
                    "provider_id": snapshot.get("provider_id"),
                    "provider_name": r["provider_name"]
                    or snapshot.get("provider_name")
                    or "连接前失败",
                    "connection_id": r["connection_version"],
                    "account_id": r["account_id"] or "",
                    "account_label": r["account_label"] or "",
                    "model": actual_model,
                    "status": r["status"],
                    "error_code": r["error_code"],
                    "started_at": r["started_at"],
                    "cost": str(sum(costs)) if costs else None,
                    "latency_ms": round(elapsed),
                    "usage_status": "synced" if logs else "pending",
                }
            )
            records.append(values)
        groups = defaultdict(list)
        daily = defaultdict(list)
        for r in records:
            key = {
                "project": r["project_id"],
                "connection": r["connection_id"] or "unresolved",
                "account": r["account_id"] or "api",
                "model": r["model"],
                "provider": r["provider_id"] or "unresolved",
            }[group_by]
            groups[key].append(r)
            daily[datetime.fromtimestamp(r["started_at"], SHANGHAI).strftime("%Y-%m-%d")].append(r)
        output_groups = []
        for key, rows in groups.items():
            r = rows[0]
            label = {
                "project": r["project_name"],
                "connection": r["provider_name"],
                "account": r["account_label"] or "API 调用",
                "model": r["model"],
                "provider": r["provider_name"],
            }[group_by]
            output_groups.append(
                {
                    "key": key,
                    "label": label,
                    "detail": (r["account_label"] or "API")
                    + (" · " + key[:8] if group_by == "connection" else ""),
                    **summarize(rows),
                }
            )
        # These aggregates cover all matching requests, including those beyond the
        # latest-records table. The dashboard can combine projects and channels exactly.
        buckets = defaultdict(list)
        for r in records:
            day = datetime.fromtimestamp(r["started_at"], SHANGHAI).strftime("%Y-%m-%d")
            buckets[
                (r["project_id"], r["provider_id"], r["connection_id"], r["model"], day)
            ].append(r)
        rollups = []
        for (project, provider, connection, model_id, day), rows in buckets.items():
            rollups.append(
                {
                    "project_id": project,
                    "provider_id": provider,
                    "provider_name": rows[0]["provider_name"],
                    "connection_id": connection,
                    "account_label": rows[0]["account_label"],
                    "model": model_id,
                    "date": day,
                    "last_used_at": max(r["started_at"] for r in rows),
                    **summarize(rows),
                }
            )
        return {
            "currency": "USD",
            "rollups": rollups,
            "summary": summarize(records),
            "groups": output_groups,
            "daily": [{"date": d, **summarize(rows)} for d, rows in sorted(daily.items())],
            "requests": records[:100],
            "last_sync": self.last_sync,
            "sync_error": self.error,
            "options": {
                "accounts": list(
                    {
                        r["account_id"]: {"id": r["account_id"], "label": r["account_label"]}
                        for r in records
                        if r["account_id"]
                    }.values()
                ),
                "models": sorted({r["model"] for r in records}),
            },
        }


def summarize(records):
    result = {
        "requests": len(records),
        "successes": sum(r["status"] == "completed" for r in records),
        "pending": sum(r["usage_status"] == "pending" for r in records),
        "unknown_usage": sum(r["total_tokens"] is None for r in records),
    }
    result["success_rate"] = result["successes"] / len(records) if records else None
    result["avg_latency_ms"] = (
        round(sum(r["latency_ms"] for r in records) / len(records)) if records else None
    )
    for field in ["fresh_input", "output_tokens", "cache_read", "cache_write", "total_tokens"]:
        values = [r[field] for r in records if r[field] is not None]
        result[field] = sum(values) if values else None
    costs = [Decimal(r["cost"]) for r in records if r["cost"] is not None]
    result["cost"] = str(sum(costs)) if costs else None
    return result
