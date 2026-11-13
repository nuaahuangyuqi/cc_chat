"""Read-only verification of a running desktop build against temporary data."""

import argparse
import subprocess
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--app", default="/Applications/CC Ask.app")
parser.add_argument("--data-dir", required=True, type=Path)
args = parser.parse_args()
subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", args.app], check=True)
with httpx.Client(base_url="http://127.0.0.1:8765", trust_env=False, timeout=5) as client:
    assert client.get("/api/health").json()["status"] == "ok"
    setup = client.get("/api/setup").json()
    assert setup["desktop"]
    assert Path(setup["data_dir"]).resolve() == args.data_dir.resolve()
    for name in ["app.js", "style.css", "icon.png"] + [f"font-{i}.ttf" for i in range(1, 6)]:
        result = client.get("/static/" + name)
        assert result.status_code == 200 and len(result.content) > 500
    wheel = client.get("/api/sdk/" + setup["sdk_wheel"])
    assert wheel.status_code == 200 and wheel.content.startswith(b"PK")
    assert client.get("/api/projects", headers={"origin": "https://evil.test"}).status_code == 403
    assert client.get("/api/projects", headers={"host": "evil.test"}).status_code == 400
    assert client.get("/api/connection").status_code == 200
print(
    "PASS: signature, frozen runtime, data directory, health, static assets, SDK, access protection"
)
