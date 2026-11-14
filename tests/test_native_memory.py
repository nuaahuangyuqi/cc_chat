import asyncio
import json
import sqlite3

import httpx
import pytest
from conftest import completion
from fastapi.testclient import TestClient

from ccask import Ask, clear_sessions
from ccask.db import SCHEMA, Database
from ccask.errors import CCAskError
from ccask.service import ConversationService
from ccask.transport import ProxyTransport
from ccask.web import create_app


def content(text):
    return [{"type": "input_text", "text": text}]


async def test_native_continuation_is_incremental_persistent_and_isolated(env):
    sid = env.session["id"]
    other = env.db.session("研究", "other", 0, True)["id"]
    await env.service.set_memory(sid, 0, True)
    await env.service.ask(sid, content("my name is Hex"))
    assert env.calls[-1]["body"]["store"] is True
    assert "previous_response_id" not in env.calls[-1]["body"]
    await env.service.ask(other, content("separate conversation"))
    assert "previous_response_id" not in env.calls[-1]["body"]
    restarted = ConversationService(
        env.settings, Database(env.settings.db_path), cc=env.cc,
        auth=env.service.auth, transport=env.service.transport,
    )
    await restarted.ask(sid, content("who am I?"))
    body = env.calls[-1]["body"]
    assert body["previous_response_id"] == "resp-test-1"
    assert body["input"] == [{"role": "user", "content": content("who am I?")}]
    await restarted.ask(other, content("continue other"))
    assert env.calls[-1]["body"]["previous_response_id"] == "resp-test-2"
    assert env.calls[-1]["body"]["prompt_cache_key"] != body["prompt_cache_key"]


async def test_native_mode_preloads_window_once_and_changes_reset_chain(env):
    sid = env.session["id"]
    for i in range(4):
        await env.service.ask(sid, content(f"old-{i}"))
    await env.service.set_memory(sid, 2, True)
    await env.service.ask(sid, content("seed"))
    body = env.calls[-1]["body"]
    assert len(body["input"]) == 5
    assert body["input"][0]["content"] == content("old-2")
    await env.service.set_memory(sid, 2, True)  # Reopening with identical settings preserves the chain.
    await env.service.ask(sid, content("continue"))
    assert len(env.calls[-1]["body"]["input"]) == 1
    assert env.calls[-1]["body"]["previous_response_id"] == "resp-test-5"
    await env.service.set_memory(sid, 1)
    await env.service.ask(sid, content("new seed"))
    assert "previous_response_id" not in env.calls[-1]["body"]
    assert len(env.calls[-1]["body"]["input"]) == 3
    await env.service.set_memory(sid, 0, False)
    await env.service.ask(sid, content("independent"))
    assert env.calls[-1]["body"]["store"] is False
    assert "previous_response_id" not in env.calls[-1]["body"]
    await env.service.set_memory(sid, default_memory=True)
    await env.service.ask(sid, content("fresh native"))
    assert "previous_response_id" not in env.calls[-1]["body"]
    assert len(env.calls[-1]["body"]["input"]) == 1


@pytest.mark.parametrize("change", ["account", "instructions", "model", "effort"])
async def test_native_state_does_not_cross_identity_or_configuration_changes(env, change):
    sid = env.session["id"]
    project = dict(env.project, mode="gpt", provider_id=None, model="test-gpt")
    env.db.save_project(project, project["id"])
    await env.service.set_memory(sid, 0, True)
    await env.service.ask(sid, content("before"))
    if change == "account":
        env.live["apps"]["codex"]["proxy_route"] = "gpt-two"
        (env.settings.cc_dir / "live-state.json").write_text(json.dumps(env.live))
    else:
        key, value = {
            "instructions": ("instructions", "new instruction"),
            "model": ("model", "other-gpt"),
            "effort": ("parameters", {"reasoning": {"effort": "high"}}),
        }[change]
        env.db.save_project({**project, key: value}, project["id"])
    await env.service.ask(sid, content("after"))
    assert "previous_response_id" not in env.calls[-1]["body"]
    assert len(env.calls[-1]["body"]["input"]) == 1


@pytest.mark.parametrize("failure", ["missing_id", "unsupported", "expired", "failed", "not_stored"])
async def test_native_failure_preserves_history_and_last_response(env, failure):
    sid = env.session["id"]
    await env.service.set_memory(sid, 0, True)
    await env.service.ask(sid, content("good"))
    before = env.db.get_session(sid)
    def handler(request):
        if failure in ("missing_id", "not_stored"):
            result = completion("answer")
            if failure == "missing_id":
                result.pop("id")
            else:
                result["store"] = False
            return httpx.Response(200, json=result)
        if failure == "failed":
            return httpx.Response(200, json={"status": "failed", "error": {"code": "error"}})
        return httpx.Response(
            404 if failure == "expired" else 400,
            json={"error": {"param": "previous_response_id" if failure == "expired" else "store",
                            "message": "not found" if failure == "expired" else "must be false"}},
        )
    env.service.transport = ProxyTransport(http_transport=httpx.MockTransport(handler))
    with pytest.raises(CCAskError) as info:
        await env.service.ask(sid, content("failed question"))
    assert info.value.code == {
        "missing_id": "native_memory_unsupported", "unsupported": "native_memory_unsupported",
        "expired": "native_memory_expired", "failed": "incomplete_response",
        "not_stored": "native_memory_unsupported",
    }[failure]
    assert len(env.db.rows("SELECT * FROM messages")) == 2
    assert env.db.get_session(sid)["response_id"] == before["response_id"]
    assert env.db.rows("SELECT status FROM requests ORDER BY started_at")[-1]["status"] == "failed"


async def test_clear_deletes_session_and_detaches_usage_without_resurrecting_it(env):
    sid = env.session["id"]
    await env.service.set_memory(sid, 0, True)
    await env.service.ask(sid, content("remember"))
    from ccask.usage import UsageService
    usage = UsageService(env.db, env.cc)
    usage.sync()
    before = usage.report()["summary"]
    assert (await env.service.clear(sid))["deleted_sessions"] == 1
    assert not env.db.rows("SELECT * FROM sessions")
    assert not env.db.rows("SELECT * FROM messages")
    assert env.db.one("SELECT session_id FROM requests")["session_id"] == ""
    assert usage.report()["summary"] == before
    with pytest.raises(CCAskError) as info:
        await env.service.ask(sid, content("stale client"))
    assert info.value.code == "session_not_found"
    fresh = env.db.session("研究", "experiment", 0, True)
    assert fresh["id"] != sid
    await env.service.ask(fresh["id"], content("fresh"))
    assert "previous_response_id" not in env.calls[-1]["body"]


async def test_bulk_clear_is_scoped_and_rejects_running_calls_atomically(env):
    sid = env.session["id"]
    p = env.db.save_project({**env.project, "name": "other-project"})
    other = env.db.session(p["id"], "same-name", 0, True)["id"]
    await env.service.ask(sid, content("first"))
    await env.service.ask(other, content("other"))
    entered, release = asyncio.Event(), asyncio.Event()
    original = env.service.transport
    class Blocked:
        async def generate(self, *args):
            entered.set()
            await release.wait()
            return await original.generate(*args)
    env.service.transport = Blocked()
    task = asyncio.create_task(env.service.ask(sid, content("running")))
    await entered.wait()
    try:
        with pytest.raises(CCAskError) as info:
            await env.service.clear_sessions(all_projects=True)
        assert info.value.code == "sessions_busy"
        assert len(env.db.rows("SELECT * FROM sessions")) == 2
        assert (await env.service.clear_sessions(p["id"]))["deleted_sessions"] == 1
        assert env.db.get_session(sid)
    finally:
        release.set()
        await task
    assert (await env.service.clear_sessions(all_projects=True))["deleted_sessions"] == 1
    assert not env.db.rows("SELECT * FROM sessions")
    assert len(env.db.rows("SELECT * FROM requests")) == 3


def test_sdk_both_controls_clear_and_lazy_new_session(env, monkeypatch):
    original = httpx.Client
    with TestClient(create_app(env.settings, env.service)) as web:
        def forward(request):
            response = web.request(request.method, request.url.path, content=request.content,
                                   headers={"content-type": "application/json"})
            return httpx.Response(response.status_code, json=response.json())
        monkeypatch.setattr("ccask.client.httpx.Client", lambda **kw: original(
            base_url="http://testserver", transport=httpx.MockTransport(forward)))
        with Ask("研究", default_memory=True, memory=0, session_id="sdk-native") as bot:
            old_id = bot._id
            bot.ask("I am Hex")
            bot.ask("who am I")
            assert env.calls[-1]["body"]["previous_response_id"] == "resp-test-1"
            assert bot.clear_memory()["deleted_sessions"] == 1
            assert bot.session_id is None
            assert bot._id is None
            assert env.db.one("SELECT id FROM sessions WHERE id=?", (old_id,)) is None
            assert bot.clear_memory()["deleted_sessions"] == 0
            bot.set_memory(2)
            assert bot._id is None
            reply = bot.ask("new conversation")
            assert bot._id != old_id
            assert bot.session_id == reply.session_id != "sdk-native"
            assert "previous_response_id" not in env.calls[-1]["body"]
            bot.set_default_memory(False)
            bot.stop_memory()
            bot.ask("independent")
            assert len(env.calls[-1]["body"]["input"]) == 1
            assert env.calls[-1]["body"]["store"] is False
        result = clear_sessions(project="研究")
        assert result["deleted_sessions"] == 2
        assert not env.db.rows("SELECT * FROM sessions")
        assert clear_sessions(all_projects=True)["deleted_sessions"] == 0


@pytest.mark.parametrize("value", [1, 0, "true", None, [], {}])
def test_invalid_default_memory_sdk_and_api(env, value):
    with pytest.raises(CCAskError) as info:
        Ask("研究", default_memory=value)
    assert info.value.code == "invalid_default_memory"
    with TestClient(create_app(env.settings, env.service)) as c:
        assert c.post("/api/sessions", json={"project": "研究", "default_memory": value}).status_code == 422
        assert c.put(f"/api/sessions/{env.session['id']}/memory",
                     json={"default_memory": value}).status_code == 422


@pytest.mark.parametrize("scope", [{}, {"all_projects": False}, {"project": "研究", "all_projects": True},
                                   {"project": ""}, {"project": " "}, {"all_projects": 1}])
def test_invalid_bulk_scope_never_deletes_sessions(env, scope):
    with pytest.raises(CCAskError):
        clear_sessions(**scope)
    with TestClient(create_app(env.settings, env.service)) as c:
        assert c.post("/api/sessions/clear", json=scope).status_code == 422
    assert env.db.get_session(env.session["id"])


def test_upgrade_from_window_schema_preserves_settings_and_history(env):
    path = env.settings.data_dir / "window.db"
    old = SCHEMA.replace(" default_memory INTEGER NOT NULL DEFAULT 0,\n", "").replace(
        " response_id TEXT, response_context TEXT,\n", "")
    with sqlite3.connect(path) as c:
        c.executescript(old)
        c.execute("ALTER TABLE projects ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        c.execute("INSERT INTO projects(id,name,mode,model,created_at,updated_at) VALUES ('p','old','gpt','m',1,1)")
        c.execute("INSERT INTO sessions VALUES ('s','p','old',1,0,7,1)")
    db = Database(path)
    session = db.get_session("s")
    assert session["memory_rounds"] == 7
    assert session["default_memory"] == 0
    assert session["response_id"] is None
    assert len(list((path.parent / "backups").glob("*.db"))) == 1
    Database(path)
    assert len(list((path.parent / "backups").glob("*.db"))) == 1
