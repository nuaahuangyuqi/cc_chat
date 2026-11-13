import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from ccask import Ask
from ccask.auth import CodexAuth
from ccask.client import image_content
from ccask.errors import CCAskError
from ccask.web import create_app

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aFOsAAAAASUVORK5CYII="
)


def test_project_crud_and_input_validation(env):
    with TestClient(create_app(env.settings, env.service)) as c:
        r = c.post(
            "/api/projects",
            json={"name": "新项目", "mode": "api", "provider_id": "api-two", "model": "test"},
        )
        assert r.status_code == 201
        project = r.json()
        r = c.put(
            "/api/projects/" + project["id"],
            json={**project, "name": "改名", "parameters": {"input": []}},
        )
        assert r.status_code == 422
        r = c.put("/api/projects/" + project["id"], json={**project, "name": "改名"})
        assert r.json()["revision"] == 2
        assert c.post("/api/projects/" + project["id"] + "/archive").status_code == 200
        assert len(c.get("/api/projects").json()) == 1
        assert len(c.get("/api/projects?include_archived=true").json()) == 2
        assert c.get("/").status_code == 200
        assert c.get("/static/app.js").status_code == 200
        assert c.get("/api/usage?start=5&end=1").status_code == 400
        assert c.post("/api/sessions", json={"project": "missing"}).status_code == 404


def test_project_description_and_connection_test_usage(env):
    with TestClient(create_app(env.settings, env.service)) as c:
        project = c.post(
            "/api/projects",
            json={
                "name": "连接验证",
                "description": "分析图片和研究资料",
                "mode": "api",
                "provider_id": "api-one",
                "model": "test-model",
            },
        ).json()
        assert project["description"] == "分析图片和研究资料"
        result = c.post(f"/api/projects/{project['id']}/test")
        assert result.status_code == 200
        assert result.json()["text"] == "answer-1"
        assert result.json()["latency_ms"] >= 0
        report = c.get("/api/usage", params={"project_id": project["id"]}).json()
        assert report["summary"]["requests"] == 1
        assert report["summary"]["total_tokens"] == 1100
        assert report["currency"] == "USD"
        assert report["rollups"][0]["provider_id"] == "api-one"
        assert report["rollups"][0]["cost"] == "0.0023"
        assert not env.db.rows("SELECT * FROM messages")
        assert c.post("/api/projects/missing/test").status_code == 404


def test_description_migration_preserves_existing_projects(tmp_path):
    import sqlite3

    from ccask.db import SCHEMA, Database

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as c:
        c.executescript(SCHEMA)
        c.execute(
            "INSERT INTO projects VALUES ('old','已有项目','gpt',NULL,'model','','{}',1,0,1,1)"
        )
    db = Database(path)
    assert db.project("old")["description"] == ""
    saved = db.save_project({**db.project("old"), "description": "新增描述"}, "old")
    assert saved["description"] == "新增描述"
    assert saved["revision"] == 2


def test_sdk_memory_and_image_against_real_service_routes(env, monkeypatch):
    original_client = httpx.Client
    with TestClient(create_app(env.settings, env.service)) as web:

        def forward(request):
            response = web.request(
                request.method,
                request.url.path,
                content=request.content,
                headers={"content-type": "application/json"},
            )
            return httpx.Response(response.status_code, json=response.json())

        monkeypatch.setattr(
            "ccask.client.httpx.Client",
            lambda **kw: original_client(
                base_url="http://testserver", transport=httpx.MockTransport(forward)
            ),
        )
        with Ask("研究", memory=True, session_id="sdk") as bot:
            reply = bot.ask("image", images=[PNG])
            assert reply.text == "answer-1"
            assert reply.session_id == "sdk"
            assert env.calls[-1]["body"]["input"][0]["content"][1]["type"] == "input_image"
            bot.stop_memory()
            bot.ask("independent")
            assert len(env.calls[-1]["body"]["input"]) == 1
            bot.start_memory()
            bot.ask("continue")
            assert "independent" not in json.dumps(env.calls[-1]["body"]["input"])
            bot.clear_memory()
            assert not env.db.rows("SELECT * FROM messages")


def test_origin_host_protection(env):
    with TestClient(create_app(env.settings, env.service)) as c:
        assert c.get("/api/projects", headers={"origin": "https://evil.test"}).status_code == 403
        assert c.get("/api/projects", headers={"host": "evil.test"}).status_code == 400
        assert c.get("/api/projects", headers={"origin": "http://testserver"}).status_code == 200


def test_delete_project_removes_usage_and_memory_but_preserves_other_projects(env):
    with TestClient(create_app(env.settings, env.service)) as c:
        original = env.project["id"]
        c.post(
            f"/api/sessions/{env.session['id']}/ask",
            json={"content": [{"type": "input_text", "text": "remember"}]},
        )
        other = c.post(
            "/api/projects",
            json={"name": "其他项目", "mode": "api", "provider_id": "api-two", "model": "other"},
        ).json()["id"]
        assert c.post(f"/api/projects/{other}/test").status_code == 200
        assert c.get("/api/usage").json()["summary"]["requests"] == 2
        # Archived projects can be permanently deleted as well.
        assert c.post(f"/api/projects/{original}/archive").status_code == 200
        assert c.get("/api/usage").json()["summary"]["requests"] == 2
        assert c.delete(f"/api/projects/{original}").json() == {"deleted": True}
        c.post("/api/usage/sync")
        report = c.get("/api/usage").json()
        assert report["summary"]["requests"] == 1
        assert report["summary"]["total_tokens"] == 1100
        assert report["summary"]["cost"] == "0.0023"
        assert {r["project_id"] for r in report["rollups"]} == {other}
        assert not env.db.rows("SELECT * FROM messages")
        assert not env.db.rows("SELECT * FROM sessions WHERE project_id=?", (original,))
        assert not env.db.rows("SELECT * FROM requests WHERE project_id=?", (original,))
        assert len(env.db.rows("SELECT * FROM connections")) == 1
        assert len(c.get("/api/projects?include_archived=true").json()) == 1
        assert c.delete(f"/api/projects/{original}").status_code == 404


def test_delete_project_rejects_running_calls_atomically(env):
    with TestClient(create_app(env.settings, env.service)) as c:
        project = env.project["id"]
        env.db.execute(
            "INSERT INTO requests(id,project_id,session_id,tracking_id,snapshot,status,started_at) "
            "VALUES ('running',?,?,'tracking','{}','running',1)",
            (project, env.session["id"]),
        )
        result = c.delete(f"/api/projects/{project}")
        assert result.status_code == 409
        assert result.json()["error"]["code"] == "project_busy"
        assert env.db.project(project)
        assert env.db.get_session(env.session["id"])
        assert env.db.one("SELECT id FROM requests WHERE id='running'")


def test_public_connection_does_not_return_keys(env):
    data = json.dumps(env.cc.describe())
    assert "sk-fixture" not in data
    assert "OPENAI_API_KEY" not in data
    assert "routable" in data


async def test_native_auth_checks_selected_account(env):
    def token(payload):
        return (
            "header."
            + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
            + ".sig"
        )

    (env.settings.codex_dir / "auth.json").write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": token({"exp": 9999999999}),
                    "account_id": "workspace",
                    "id_token": token({"email": "alice@example.test"}),
                }
            }
        )
    )
    marker = env.settings.cc_dir / "codex_managed_oauth_live_auth.json"
    marker.write_text(json.dumps({"account_id": "account-one", "chatgpt_account_id": "workspace"}))
    p = next(p for p in env.cc.state()["providers"] if p["id"] == "gpt-one")
    headers, account = await CodexAuth(env.settings).headers(p)
    assert account["id"] == "account-one"
    assert headers["ChatGPT-Account-Id"] == "workspace"
    marker.write_text(json.dumps({"account_id": "other", "chatgpt_account_id": "workspace"}))
    with pytest.raises(CCAskError) as info:
        await CodexAuth(env.settings).headers(p)
    assert info.value.code == "account_mismatch"


def test_image_validation():
    assert image_content(PNG)["image_url"].startswith("data:image/png;base64,")
    with pytest.raises(CCAskError):
        image_content(b"not an image")


def test_current_catalog_wins_over_old_account_cache(env):
    (env.settings.codex_dir / "cc-switch-model-catalog.json").write_text(
        json.dumps(
            {
                "models": [
                    {"slug": "current-model", "visibility": "list"},
                    {"slug": "gpt-reserve", "visibility": "hide"},
                ]
            }
        )
    )
    (env.settings.codex_dir / "models_cache.json").write_text(
        json.dumps(
            {
                "models": [
                    {"slug": "old-account-only-model", "visibility": "list"},
                ]
            }
        )
    )
    assert [m["id"] for m in env.cc.catalog()] == ["current-model"]
