import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ccask.db import SCHEMA, Database
from ccask.runtime import codex_path, executable_env, save_codex_path
from ccask.web import create_app
from ccask_mac.desktop import Backend, Instance


def test_finder_discovery_and_manual_path(env, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.delenv("CCASK_CODEX_EXECUTABLE", raising=False)
    home = tmp_path / "中文 用户"
    binary = home / ".local/bin/codex"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o700)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr("ccask.runtime.shutil.which", lambda _: None)
    # Manual paths survive restarts and work with spaces and Chinese names.
    save_codex_path(env.settings, str(binary))
    assert codex_path(env.settings) == str(binary)
    assert executable_env(str(binary))["PATH"].split(os.pathsep)[0] == str(binary.parent)
    assert (env.settings.data_dir / "preferences.json").stat().st_mode & 0o777 == 0o600
    binary.unlink()
    assert codex_path(env.settings) is None


def test_runtime_routes_and_offline_diagnostics(env):
    env.source.unlink()
    with TestClient(create_app(env.settings, env.service)) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        offline = client.get("/api/connection").json()
        assert offline["ready"] is False
        assert "数据" in offline["error"]
        assert offline["data_directory"] == str(env.settings.cc_dir)
        assert client.put("/api/settings", json={"codex_path": "/missing"}).status_code == 400
        wheel = client.get("/api/setup").json()["sdk_wheel"]
        assert wheel
        assert client.get("/api/sdk/" + wheel).content.startswith(b"PK")
        assert client.get("/api/sdk/auth.json").status_code == 404
        for font in range(1, 6):
            assert len(client.get(f"/static/font-{font}.ttf").content) > 1000


def test_single_instance_lock(tmp_path, monkeypatch):
    monkeypatch.setattr("ccask_mac.desktop.activate", lambda _: None)
    first, second = Instance(tmp_path), Instance(tmp_path)
    try:
        assert first.acquire()
        assert not second.acquire()
    finally:
        second.close()
        first.close()
    third = Instance(tmp_path)
    try:
        assert third.acquire()
    finally:
        third.close()


def test_backend_port_conflict_never_kills_existing_server(env, monkeypatch):
    import socket

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    monkeypatch.setattr("ccask_mac.desktop.PORT", listener.getsockname()[1])
    monkeypatch.setattr("ccask_mac.desktop.URL", f"http://127.0.0.1:{listener.getsockname()[1]}")
    backend = Backend(env.settings)
    try:
        with pytest.raises(RuntimeError, match="占用"):
            backend.start()
        backend.stop()
        assert listener.getsockname()[1] > 0
    finally:
        listener.close()


def test_migration_backup_contains_original_data(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as c:
        c.executescript(SCHEMA)
        c.execute("INSERT INTO projects VALUES ('old','原项目','gpt',NULL,'x','','{}',1,0,1,1)")
    Database(path)
    backups = list((tmp_path / "backups").glob("*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as c:
        assert c.execute("SELECT name FROM projects").fetchone()[0] == "原项目"
        assert "description" not in {r[1] for r in c.execute("PRAGMA table_info(projects)")}
