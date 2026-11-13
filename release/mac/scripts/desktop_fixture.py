"""Local-only integration fixture. Fake responses never reach a model provider."""

import argparse
import json
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("root", type=Path)
args = parser.parse_args()
root = args.root
cc = root / "离线 CC Switch"
cc.mkdir(parents=True, exist_ok=True)
control = root / "delay"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert body["model"] == "ccs-fixture/mock-model"
        (root / "request-started").write_text("started")
        for _ in range(600):
            if not control.exists():
                break
            time.sleep(0.1)
        now = time.time()
        request_id = "fixture-" + str(time.time_ns())
        with sqlite3.connect(cc / "cc-switch.db") as c:
            c.execute(
                "INSERT INTO proxy_request_logs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    request_id,
                    "fixture-api",
                    "codex",
                    "mock-model",
                    12,
                    8,
                    0,
                    0,
                    1,
                    "0",
                    10,
                    200,
                    "codex_" + self.headers["session_id"],
                    int(now),
                    "proxy",
                ),
            )
        result = {
            "id": request_id,
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "模拟回答：桌面 App 和 Ask 客户端连接成功"}
                    ],
                }
            ],
        }
        event = "data: " + json.dumps({"type": "response.completed", "response": result}) + "\n\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        try:
            self.wfile.write(event.encode())
        except BrokenPipeError:
            pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
# Import just the schema, not fixtures or user data.
import runpy

schema = runpy.run_path(str(Path(__file__).resolve().parents[3] / "tests/conftest.py"))[
    "SOURCE_SCHEMA"
]
with sqlite3.connect(cc / "cc-switch.db") as c:
    c.executescript(schema)
    c.execute("DELETE FROM providers")
    c.execute("DELETE FROM proxy_config")
    c.execute(
        "INSERT INTO providers VALUES ('fixture-api','codex','本机模拟供应商',NULL,?, '{}')",
        (json.dumps({"config": 'model_provider="fixture"\nmodel="mock-model"'}),),
    )
    c.execute("INSERT INTO proxy_config VALUES ('codex','127.0.0.1',?,1)", (server.server_port,))
(cc / "live-state.json").write_text(
    json.dumps(
        {
            "apps": {
                "codex": {
                    "mode": "proxy",
                    "proxy_route": "fixture-api",
                    "stack": {
                        "enabled": True,
                        "members": ["fixture-api"],
                        "keys": {"fixture": "fixture-api"},
                    },
                }
            }
        }
    )
)
(root / "proxy-port").write_text(str(server.server_port))
print("Local fixture ready", server.server_port, flush=True)
server.serve_forever()
