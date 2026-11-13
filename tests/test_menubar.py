import ast
import json
import time
import zipfile
from datetime import datetime, timedelta
from email.parser import BytesParser
from pathlib import Path

from fastapi.testclient import TestClient

from ccask.menubar import monitor_snapshot, save_monitor_settings
from ccask.runtime import preferences, update_preferences
from ccask.sdk_info import SDK_WHEEL, install_command
from ccask.usage import SHANGHAI, UsageService
from ccask.web import create_app


def record(env, project, name, tokens, when=None):
    when = time.time() if when is None else when
    session = env.db.session(project["id"], "menu", False)
    env.db.execute(
        "INSERT INTO requests "
        "(id,project_id,session_id,tracking_id,snapshot,status,started_at,finished_at,usage_synced) "
        "VALUES (?,?,?,?,?,'completed',?,?,1)",
        (name, project["id"], session["id"], name, json.dumps({"model": "mock"}), when, when),
    )
    env.db.execute(
        "INSERT INTO usage (source_id,request_id,provider_id,model,fresh_input,output_tokens,"
        "cache_read,cache_write,total_tokens,cost,status_code,created_at,raw) "
        "VALUES (?,?,'api-one','mock',?,0,0,0,?,'0.0001',200,?,'{}')",
        (name, name, tokens, tokens, when),
    )


def test_monitor_aggregates_selected_projects_beyond_latest_100_records(env):
    other = env.db.save_project({**env.project, "name": "其他", "id": None})
    for index in range(125):
        record(env, env.project, "first-" + str(index), 10)
    record(env, other, "other", 777)
    usage = UsageService(env.db, env.cc)
    save_monitor_settings(env.settings, env.db, [env.project["id"]], "all")
    snapshot = monitor_snapshot(env.settings, env.db, usage)
    assert snapshot["scope"] == "所选项目"
    assert snapshot["summary"]["requests"] == 125
    assert snapshot["summary"]["total_tokens"] == 1250
    assert snapshot["summary"]["cost"] == "0.0125"
    save_monitor_settings(env.settings, env.db, [env.project["id"], other["id"]], "all")
    snapshot = monitor_snapshot(env.settings, env.db, usage)
    assert len(snapshot["rows"]) == 2
    assert snapshot["summary"]["requests"] == 126
    assert snapshot["summary"]["total_tokens"] == 2027
    save_monitor_settings(env.settings, env.db, [], "all")
    assert monitor_snapshot(env.settings, env.db, usage)["summary"]["total_tokens"] == 2027


def test_monitor_settings_validation_persistence_and_archived_fallback(env):
    update_preferences(env.settings, {"codex_path": "/saved/path"})
    with TestClient(create_app(env.settings, env.service)) as client:
        result = client.put(
            "/api/settings/menubar",
            json={"project_ids": [env.project["id"], env.project["id"]], "period": "7d"},
        )
        assert result.status_code == 200
        assert result.json() == {"project_ids": [env.project["id"]], "period": "7d"}
        assert preferences(env.settings)["codex_path"] == "/saved/path"
        assert client.get("/api/setup").json()["menubar"] == result.json()
        assert client.put(
            "/api/settings/menubar", json={"project_ids": ["missing"], "period": "today"}
        ).status_code == 400
        assert client.put(
            "/api/settings/menubar", json={"project_ids": [], "period": "invalid"}
        ).status_code == 422
        env.db.execute("UPDATE projects SET archived=1 WHERE id=?", (env.project["id"],))
        assert client.get("/api/menubar").json()["scope"] == "全局用量"
    assert (env.settings.data_dir / "preferences.json").stat().st_mode & 0o777 == 0o600


def test_monitor_time_ranges_and_zero_usage_selected_project(env):
    usage = UsageService(env.db, env.cc)
    now = datetime.now(SHANGHAI).replace(hour=12, minute=0, second=0, microsecond=0)
    record(env, env.project, "today", 10, now.timestamp())
    record(env, env.project, "three-days-ago", 20, (now - timedelta(days=3)).timestamp())
    record(env, env.project, "eight-days-ago", 30, (now - timedelta(days=8)).timestamp())
    for period, total in [("today", 10), ("7d", 30), ("30d", 60), ("all", 60)]:
        save_monitor_settings(env.settings, env.db, [], period)
        assert monitor_snapshot(env.settings, env.db, usage)["summary"]["total_tokens"] == total
    other = env.db.save_project({**env.project, "name": "空项目", "id": None})
    save_monitor_settings(env.settings, env.db, [other["id"]], "today")
    snapshot = monitor_snapshot(env.settings, env.db, usage)
    assert snapshot["summary"]["requests"] == 0
    assert snapshot["summary"]["total_tokens"] == 0
    assert snapshot["rows"][0]["label"] == "空项目"


def test_distributed_client_has_python37_compatible_source_and_dependencies(env):
    sdk = Path(__file__).resolve().parents[1] / "src/ccask/sdk" / SDK_WHEEL
    with zipfile.ZipFile(sdk) as wheel:
        metadata = BytesParser().parsebytes(wheel.read(
            next(n for n in wheel.namelist() if n.endswith("/METADATA"))
        ))
        assert metadata["Requires-Python"] == ">=3.7"
        assert 'httpx>=0.24.1,<0.25; python_version < "3.8"' in metadata.get_all("Requires-Dist")
        for name in ("ccask/__init__.py", "ccask/client.py", "ccask/errors.py"):
            ast.parse(wheel.read(name), feature_version=(3, 7))
    with TestClient(create_app(env.settings, env.service)) as client:
        setup = client.get("/api/setup").json()
        assert setup["install_command"] == install_command()
        assert SDK_WHEEL in setup["install_command"]
        assert client.get("/api/sdk/" + SDK_WHEEL).content == sdk.read_bytes()
