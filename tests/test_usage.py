import json
import sqlite3
import time

import pytest

from ccask.usage import UsageService, normalize


@pytest.mark.parametrize(
    "semantics,inp,expected", [(0, 1000, 700), (1, 1000, 500), (2, 500, 500), (1, 100, 100)]
)
def test_cache_semantics(semantics, inp, expected):
    value = normalize(
        {
            "input_tokens": inp,
            "output_tokens": 100,
            "cache_read_tokens": 300,
            "cache_creation_tokens": 200,
            "input_token_semantics": semantics,
        }
    )
    assert value["fresh_input"] == expected
    assert value["total_tokens"] == expected + 600


async def test_usage_idempotent_and_survives_source_deletion(env):
    await env.service.ask(env.session["id"], [{"type": "input_text", "text": "hello"}])
    usage = UsageService(env.db, env.cc)
    usage.sync()
    usage.sync()
    assert len(env.db.rows("SELECT * FROM usage")) == 1
    report = usage.report()
    assert report["summary"]["total_tokens"] == 1100
    assert report["summary"]["cost"] == "0.0023"
    assert report["summary"]["pending"] == 0
    with sqlite3.connect(env.source) as c:
        c.execute("DELETE FROM proxy_request_logs")
    await env.service.clear(env.session["id"])
    env.db.execute("UPDATE projects SET archived=1")
    usage.sync()
    assert usage.report()["summary"]["total_tokens"] == 1100
    assert usage.report()["requests"][0]["archived"]


async def test_account_and_project_breakdowns_sum_to_total(env):
    draft = dict(env.project, mode="gpt", provider_id=None)
    env.db.save_project(draft, draft["id"])
    await env.service.ask(env.session["id"], [{"type": "input_text", "text": "one"}])
    env.live["apps"]["codex"]["proxy_route"] = "gpt-two"
    (env.settings.cc_dir / "live-state.json").write_text(json.dumps(env.live))
    await env.service.ask(env.session["id"], [{"type": "input_text", "text": "two"}])
    usage = UsageService(env.db, env.cc)
    usage.sync()
    report = usage.report(group_by="account")
    assert len(report["groups"]) == 2
    assert sum(g["total_tokens"] for g in report["groups"]) == report["summary"]["total_tokens"]
    assert usage.report(account_id="account-one")["summary"]["requests"] == 1
    assert usage.report(start=time.time() + 10)["summary"]["requests"] == 0


async def test_delayed_log_and_source_filter(env):
    await env.service.ask(env.session["id"], [{"type": "input_text", "text": "one"}])
    with sqlite3.connect(env.source) as c:
        c.execute("UPDATE proxy_request_logs SET data_source='codex_session'")
    usage = UsageService(env.db, env.cc)
    usage.sync()
    assert usage.report()["summary"]["total_tokens"] is None
    assert usage.report()["summary"]["pending"] == 1
    with sqlite3.connect(env.source) as c:
        c.execute("UPDATE proxy_request_logs SET data_source='proxy'")
    usage.sync()
    assert usage.report()["summary"]["total_tokens"] == 1100


def test_missing_usage_is_not_zero():
    assert normalize({"input_tokens": 0, "output_tokens": 0})["total_tokens"] is None


async def test_rollups_cover_requests_beyond_record_limit(env):
    await env.service.ask(env.session["id"], [{"type": "input_text", "text": "one"}])
    usage = UsageService(env.db, env.cc)
    usage.sync()
    with env.db.connect() as c:
        for i in range(105):
            c.execute(
                "INSERT INTO requests SELECT ?,project_id,session_id,?,snapshot,connection_version,"
                "status,error_code,started_at,finished_at,usage_synced FROM requests LIMIT 1",
                (f"extra-{i}", f"tracking-{i}"),
            )
            c.execute(
                "INSERT INTO usage SELECT ?,?,provider_id,model,fresh_input,output_tokens,"
                "cache_read,cache_write,total_tokens,cost,latency_ms,status_code,created_at,raw "
                "FROM usage LIMIT 1",
                (f"usage-{i}", f"extra-{i}"),
            )
    report = usage.report()
    assert len(report["requests"]) == 100
    assert sum(r["requests"] for r in report["rollups"]) == 106
    assert sum(r["total_tokens"] for r in report["rollups"]) == 106 * 1100
    assert report["rollups"][0]["connection_id"]
