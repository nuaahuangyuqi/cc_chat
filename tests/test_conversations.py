import asyncio
import json
import sqlite3

import httpx
import pytest

from ccask.db import Database
from ccask.errors import CCAskError
from ccask.service import ConversationService
from ccask.transport import ProxyTransport


def content(text):
    return [{"type": "input_text", "text": text}]


async def test_memory_pause_resume_clear_and_restart(env):
    s, sid = env.service, env.session["id"]
    first = await s.ask(sid, content("remember my topic"))
    assert first["text"] == "answer-1"
    await s.ask(sid, content("continue"))
    assert not any(i.get("type") == "reasoning" for i in env.calls[-1]["body"]["input"])
    await s.set_memory(sid, False)
    await s.ask(sid, content("unrelated"))
    assert len(env.calls[-1]["body"]["input"]) == 1
    await s.set_memory(sid, True)
    await s.ask(sid, content("back to topic"))
    assert "unrelated" in json.dumps(env.calls[-1]["body"]["input"])
    restored = env.db.session("研究", "experiment", True)
    assert restored["id"] == sid
    request_count = len(env.db.rows("SELECT * FROM requests"))
    await s.clear(sid)
    assert env.db.get_session(sid)["memory_enabled"] == 1
    assert not env.db.rows("SELECT * FROM messages")
    assert len(env.db.rows("SELECT * FROM requests")) == request_count
    await s.ask(sid, content("fresh"))
    assert len(env.calls[-1]["body"]["input"]) == 1


async def test_switch_provider_preserves_portable_history_and_versions(env):
    sid = env.session["id"]
    await env.service.ask(sid, content("first"))
    p = dict(env.project, provider_id="api-two", model="other-model")
    env.db.save_project(p, p["id"])
    await env.service.ask(sid, content("second"))
    call = env.calls[-1]
    assert call["body"]["model"] == "ccs-beta/other-model"
    assert len(call["body"]["input"]) == 3
    assert not any(i.get("type") == "reasoning" for i in call["body"]["input"])
    assert len(env.db.rows("SELECT * FROM connections")) == 2
    env.db.save_project(env.project, p["id"])
    await env.service.ask(sid, content("third"))
    assert not any(i.get("type") == "reasoning" for i in env.calls[-1]["body"]["input"])


async def test_api_key_change_creates_connection_version(env):
    await env.service.ask(env.session["id"], content("first"))
    with sqlite3.connect(env.source) as c:
        row = c.execute("SELECT settings_config FROM providers WHERE id='api-one'").fetchone()
        config = json.loads(row[0])
        config["auth"]["OPENAI_API_KEY"] = "sk-fixture-updated"
        c.execute(
            "UPDATE providers SET settings_config=? WHERE id='api-one'", (json.dumps(config),)
        )
    await env.service.ask(env.session["id"], content("second"))
    assert len(env.db.rows("SELECT * FROM connections")) == 2
    assert "sk-fixture" not in env.db.path.read_bytes().decode(errors="ignore")


async def test_gpt_switch_uses_current_account_and_snapshots(env):
    env.db.save_project(
        dict(env.project, mode="gpt", provider_id=None, model="test-gpt"), env.project["id"]
    )
    await env.service.ask(env.session["id"], content("one"))
    env.live["apps"]["codex"]["proxy_route"] = "gpt-two"
    (env.settings.cc_dir / "live-state.json").write_text(json.dumps(env.live))
    await env.service.ask(env.session["id"], content("two"))
    requests = env.db.rows("SELECT snapshot FROM requests ORDER BY started_at")
    assert [json.loads(r["snapshot"])["account_id"] for r in requests] == [
        "account-one",
        "account-two",
    ]
    assert env.calls[-1]["headers"]["chatgpt-account-id"] == "account-two"
    assert not any(i.get("type") == "reasoning" for i in env.calls[-1]["body"]["input"])


async def test_failed_stream_does_not_commit_memory(env):
    env.service.transport = ProxyTransport(
        http_transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text='data: {"type":"response.output_text.delta","delta":"partial"}\n\n',
            )
        )
    )
    with pytest.raises(CCAskError, match="中断"):
        await env.service.ask(env.session["id"], content("lost"))
    assert not env.db.rows("SELECT * FROM messages")
    assert env.db.one("SELECT status FROM requests")["status"] == "failed"


async def test_clear_waits_for_inflight_answer(env):
    entered, release = asyncio.Event(), asyncio.Event()
    original = env.service.transport

    class Blocked:
        async def generate(self, *args):
            entered.set()
            await release.wait()
            return await original.generate(*args)

    env.service.transport = Blocked()
    task = asyncio.create_task(env.service.ask(env.session["id"], content("question")))
    await entered.wait()
    clear = asyncio.create_task(env.service.clear(env.session["id"]))
    await asyncio.sleep(0)
    assert not clear.done()
    release.set()
    await asyncio.gather(task, clear)
    assert not env.db.rows("SELECT * FROM messages")
    assert not env.service.locks._entries


async def test_same_session_serializes_and_separate_sessions_can_run(env):
    sid = env.session["id"]
    await asyncio.gather(env.service.ask(sid, content("one")), env.service.ask(sid, content("two")))
    assert len(env.calls[-1]["body"]["input"]) == 3  # previous user, previous answer, current user
    other = env.db.session("研究", None, False)
    await asyncio.gather(
        env.service.ask(sid, content("three")), env.service.ask(other["id"], content("independent"))
    )
    assert len(env.db.rows("SELECT * FROM requests")) == 4


async def test_proxy_preflight_error_recorded_and_no_fallback(env):
    env.live["apps"]["codex"]["stack"]["enabled"] = False
    (env.settings.cc_dir / "live-state.json").write_text(json.dumps(env.live))
    with pytest.raises(CCAskError) as info:
        await env.service.ask(env.session["id"], content("hello"))
    assert info.value.code == "aggregation_off"
    assert env.calls == []
    assert env.db.one("SELECT error_code FROM requests")["error_code"] == "aggregation_off"


async def test_project_rename_keeps_live_session_and_usage(env):
    env.db.save_project(dict(env.project, name="新名字"), env.project["id"])
    await env.service.ask(env.session["id"], content("hello"))
    assert env.db.one("SELECT project_id FROM requests")["project_id"] == env.project["id"]


async def test_server_restart_restores_persisted_memory(env):
    sid = env.session["id"]
    await env.service.ask(sid, content("persistent-topic"))
    reopened = Database(env.settings.db_path)
    restarted = ConversationService(
        env.settings, reopened, cc=env.cc, auth=env.service.auth, transport=env.service.transport
    )
    await restarted.ask(sid, content("continue-after-restart"))
    assert "persistent-topic" in json.dumps(env.calls[-1]["body"]["input"])
    assert len(reopened.rows("SELECT * FROM messages")) == 4


async def test_instruction_change_uses_portable_history(env):
    await env.service.ask(env.session["id"], content("before"))
    env.db.save_project(dict(env.project, instructions="new instruction"), env.project["id"])
    await env.service.ask(env.session["id"], content("after"))
    body = env.calls[-1]["body"]
    assert body["instructions"] == "new instruction"
    assert "before" in json.dumps(body["input"])
    assert not any(item.get("type") == "reasoning" for item in body["input"])


async def test_cancelled_call_leaves_memory_unchanged_and_releases_queue(env):
    entered = asyncio.Event()

    class NeverCompletes:
        async def generate(self, *args):
            entered.set()
            await asyncio.Event().wait()

    env.service.transport = NeverCompletes()
    task = asyncio.create_task(env.service.ask(env.session["id"], content("cancel")))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert env.db.one("SELECT status FROM requests")["status"] == "interrupted"
    assert not env.db.rows("SELECT * FROM messages")
    assert not env.service.locks._entries


async def test_memory_window_rolls_forward_and_can_read_saved_independent_rounds(env):
    sid = env.session["id"]
    await env.service.set_memory(sid, 0)
    for i in range(4):
        await env.service.ask(sid, content(f"question-{i}"))
        assert env.calls[-1]["body"]["input"] == [{"role": "user", "content": content(f"question-{i}")}]
    assert len(env.db.rows("SELECT * FROM messages")) == 8
    await env.service.set_memory(sid, 2)
    await env.service.ask(sid, content("question-4"))
    assert env.calls[-1]["body"]["input"] == [
        {"role": "user", "content": content("question-2")},
        {"role": "assistant", "content": "answer-3"},
        {"role": "user", "content": content("question-3")},
        {"role": "assistant", "content": "answer-4"},
        {"role": "user", "content": content("question-4")},
    ]
    await env.service.ask(sid, content("question-5"))
    window = env.calls[-1]["body"]["input"]
    assert len(window) == 5
    assert window[0]["content"] == content("question-3")
    reopened = Database(env.settings.db_path)
    assert reopened.get_session(sid)["memory_rounds"] == 2
    await env.service.clear(sid)
    assert env.db.get_session(sid)["memory_rounds"] == 2
    await env.service.ask(sid, content("fresh"))
    assert len(env.calls[-1]["body"]["input"]) == 1


async def test_legacy_true_is_bounded_and_sessions_are_isolated(env):
    sid = env.session["id"]
    for i in range(13):
        await env.service.ask(sid, content(f"turn-{i}"))
    window = env.calls[-1]["body"]["input"]
    assert len(window) == 21
    assert window[0]["content"] == content("turn-2")
    other = env.db.session(env.project["id"], "other", 10)
    await env.service.ask(other["id"], content("separate"))
    assert len(env.calls[-1]["body"]["input"]) == 1
    assert len(env.db.rows("SELECT * FROM messages WHERE session_id=?", (sid,))) == 26


async def test_old_encrypted_state_is_not_replayed(env):
    sid = env.session["id"]
    await env.service.ask(sid, content("first"))
    env.db.execute(
        "UPDATE messages SET raw_output=? WHERE role='assistant'",
        (json.dumps([{"type": "reasoning", "encrypted_content": "old-secret-state"}]),),
    )
    await env.service.ask(sid, content("second"))
    window = env.calls[-1]["body"]["input"]
    assert window[1] == {"role": "assistant", "content": "answer-1"}
    assert "old-secret-state" not in json.dumps(window)


def test_memory_migration_preserves_history_and_is_idempotent(env):
    path = env.settings.data_dir / "legacy.db"
    with sqlite3.connect(path) as c:
        from ccask.db import SCHEMA

        c.executescript(SCHEMA.replace(" memory_rounds INTEGER NOT NULL DEFAULT 0,\n", ""))
        c.execute("ALTER TABLE projects ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        c.execute(
            "INSERT INTO projects(id,name,mode,model,created_at,updated_at) "
            "VALUES ('p','legacy','gpt','model',1,1)"
        )
        c.execute("INSERT INTO sessions VALUES ('on','p','on',1,0,1)")
        c.execute("INSERT INTO sessions VALUES ('off','p','off',0,0,1)")
        c.execute("INSERT INTO messages VALUES (1,'on',0,'user','[]',NULL,NULL,'r',1)")
    db = Database(path)
    assert db.get_session("on")["memory_rounds"] == 10
    assert db.get_session("off")["memory_rounds"] == 0
    assert len(db.rows("SELECT * FROM messages")) == 1
    db.execute("UPDATE sessions SET memory_rounds=3 WHERE id='on'")
    assert Database(path).get_session("on")["memory_rounds"] == 3
    backups = list((path.parent / "backups").glob("*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as c:
        assert "memory_rounds" not in {r[1] for r in c.execute("PRAGMA table_info(sessions)")}
