import json
import sqlite3
import time
from types import SimpleNamespace

import httpx
import pytest

from ccask.ccswitch import CCSwitch
from ccask.config import Settings
from ccask.db import Database
from ccask.service import ConversationService
from ccask.transport import ProxyTransport

SOURCE_SCHEMA = """
CREATE TABLE providers(id TEXT PRIMARY KEY,app_type TEXT,name TEXT,category TEXT,
 settings_config TEXT,meta TEXT);
CREATE TABLE proxy_config(app_type TEXT,listen_address TEXT,listen_port INTEGER,
 enable_logging INTEGER);
CREATE TABLE proxy_request_logs(request_id TEXT PRIMARY KEY,provider_id TEXT,app_type TEXT,
 model TEXT,input_tokens INTEGER,output_tokens INTEGER,cache_read_tokens INTEGER,
 cache_creation_tokens INTEGER,input_token_semantics INTEGER,total_cost_usd TEXT,
 latency_ms INTEGER,status_code INTEGER,session_id TEXT,created_at INTEGER,data_source TEXT);
"""


def completion(text="hello", reasoning=False):
    output = [
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text}],
            "phase": "final_answer",
        }
    ]
    if reasoning:
        output.insert(0, {"type": "reasoning", "encrypted_content": "opaque-test-context"})
    return {"id": "resp-test", "status": "completed", "output": output}


@pytest.fixture
def env(tmp_path):
    settings = Settings(tmp_path / "data", tmp_path / "cc", tmp_path / "codex", sync_interval=0.05)
    settings.cc_dir.mkdir()
    settings.codex_dir.mkdir()
    db = Database(settings.db_path)
    source = settings.cc_dir / "cc-switch.db"
    with sqlite3.connect(source) as c:
        c.executescript(SOURCE_SCHEMA)
        c.execute("INSERT INTO proxy_config VALUES ('codex','127.0.0.1',15721,1)")
        for identifier, name, config, meta in [
            (
                "gpt-one",
                "GPT One",
                {"auth": {}, "config": ""},
                {"authBinding": {"authProvider": "codex_oauth", "accountId": "account-one"}},
            ),
            (
                "gpt-two",
                "GPT Two",
                {"auth": {}, "config": ""},
                {"authBinding": {"authProvider": "codex_oauth", "accountId": "account-two"}},
            ),
            (
                "api-one",
                "Acme",
                {
                    "auth": {"OPENAI_API_KEY": "sk-fixture-not-a-real-key"},
                    "config": 'model_provider="custom"\nmodel="test-model"',
                },
                {},
            ),
            (
                "api-two",
                "Beta",
                {
                    "auth": {"OPENAI_API_KEY": "sk-fixture-second-key"},
                    "config": 'model_provider="custom"\nmodel="other-model"',
                },
                {},
            ),
        ]:
            c.execute(
                "INSERT INTO providers VALUES (?,'codex',?,NULL,?,?)",
                (identifier, name, json.dumps(config), json.dumps(meta)),
            )
    live = {
        "version": 1,
        "apps": {
            "codex": {
                "mode": "proxy",
                "attached": True,
                "proxy_route": "gpt-one",
                "stack": {
                    "enabled": True,
                    "members": ["api-one", "api-two"],
                    "keys": {"acme": "api-one", "beta": "api-two"},
                },
            }
        },
    }
    (settings.cc_dir / "live-state.json").write_text(json.dumps(live))
    cc = CCSwitch(settings)
    calls = []

    class Auth:
        async def headers(self, provider):
            account = provider["meta"]["authBinding"]["accountId"]
            return {"Authorization": "Bearer fixture-access", "ChatGPT-Account-Id": account}, {
                "id": account,
                "label": account + "@example.test",
            }

    async def handler(request):
        body = json.loads(request.content)
        calls.append({"url": str(request.url), "body": body, "headers": dict(request.headers)})
        model = body["model"]
        provider = (
            "api-two"
            if model.startswith("ccs-beta/")
            else "api-one"
            if model.startswith("ccs-")
            else live["apps"]["codex"]["proxy_route"]
        )
        with sqlite3.connect(source) as c:
            c.execute(
                "INSERT INTO proxy_request_logs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "proxy-" + str(len(calls)),
                    provider,
                    "codex",
                    model.split("/", 1)[-1],
                    1000,
                    100,
                    300,
                    200,
                    1,
                    "0.0023",
                    110,
                    200,
                    "codex_" + request.headers["session_id"],
                    int(time.time()),
                    "proxy",
                ),
            )
        result = completion("answer-" + str(len(calls)), reasoning=True)
        result["id"] = "resp-test-" + str(len(calls))
        sse = 'data: {"type":"response.output_text.delta","delta":"partial"}\n\n'
        sse += "data: " + json.dumps({"type": "response.completed", "response": result}) + "\n\n"
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, text=sse)

    service = ConversationService(
        settings,
        db,
        cc=cc,
        auth=Auth(),
        transport=ProxyTransport(http_transport=httpx.MockTransport(handler)),
    )
    project = db.save_project(
        {
            "name": "研究",
            "mode": "api",
            "provider_id": "api-one",
            "model": "test-model",
            "parameters": {},
        }
    )
    session = db.session(project["id"], "experiment", True)
    return SimpleNamespace(
        settings=settings,
        db=db,
        cc=cc,
        service=service,
        calls=calls,
        project=project,
        session=session,
        source=source,
        live=live,
    )
