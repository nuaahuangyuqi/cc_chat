import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .client import normalize_memory
from .errors import CCAskError


def uid() -> str:
    return str(uuid4())


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, mode TEXT NOT NULL, provider_id TEXT,
 model TEXT NOT NULL, instructions TEXT NOT NULL DEFAULT '', parameters TEXT NOT NULL DEFAULT '{}',
 revision INTEGER NOT NULL DEFAULT 1, archived INTEGER NOT NULL DEFAULT 0,
 created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS projects_name ON projects(name) WHERE archived=0;
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), name TEXT NOT NULL,
 memory_enabled INTEGER NOT NULL DEFAULT 0, generation INTEGER NOT NULL DEFAULT 0,
 memory_rounds INTEGER NOT NULL DEFAULT 0,
 created_at REAL NOT NULL, UNIQUE(project_id,name)
);
CREATE TABLE IF NOT EXISTS messages (
 id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), generation INTEGER NOT NULL,
 role TEXT NOT NULL, content TEXT NOT NULL, raw_output TEXT, connection_version TEXT,
 request_id TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id, id);
CREATE TABLE IF NOT EXISTS connections (
 id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, provider_name TEXT NOT NULL,
 account_id TEXT, account_label TEXT, fingerprint TEXT NOT NULL, created_at REAL NOT NULL,
 UNIQUE(provider_id,account_id,fingerprint)
);
CREATE TABLE IF NOT EXISTS requests (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), session_id TEXT NOT NULL,
 tracking_id TEXT NOT NULL UNIQUE, snapshot TEXT NOT NULL, connection_version TEXT,
 status TEXT NOT NULL, error_code TEXT, started_at REAL NOT NULL, finished_at REAL,
 usage_synced INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS requests_project ON requests(project_id, started_at);
CREATE TABLE IF NOT EXISTS usage (
 source_id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(id),
 provider_id TEXT NOT NULL, model TEXT NOT NULL, fresh_input INTEGER,
 output_tokens INTEGER, cache_read INTEGER, cache_write INTEGER, total_tokens INTEGER,
 cost TEXT, latency_ms INTEGER, status_code INTEGER, created_at REAL NOT NULL,
 raw TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS usage_request ON usage(request_id);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_file():
            # Backup with SQLite's online API so WAL contents are included before migration.
            with sqlite3.connect(path) as source:
                columns = {r[1] for r in source.execute("PRAGMA table_info(projects)")}
                sessions = {r[1] for r in source.execute("PRAGMA table_info(sessions)")}
                if columns and (
                    "description" not in columns or (sessions and "memory_rounds" not in sessions)
                ):
                    backup_dir = path.parent / "backups"
                    backup_dir.mkdir(exist_ok=True, mode=0o700)
                    backup = backup_dir / f"ccask-before-migration-{time.time_ns()}.db"
                    with sqlite3.connect(backup) as target:
                        source.backup(target)
                    backup.chmod(0o600)
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)
            columns = {row[1] for row in c.execute("PRAGMA table_info(projects)")}
            if "description" not in columns:
                c.execute("ALTER TABLE projects ADD COLUMN description TEXT NOT NULL DEFAULT ''")
            columns = {row[1] for row in c.execute("PRAGMA table_info(sessions)")}
            if "memory_rounds" not in columns:
                c.execute("ALTER TABLE sessions ADD COLUMN memory_rounds INTEGER NOT NULL DEFAULT 0")
                c.execute("UPDATE sessions SET memory_rounds=10 WHERE memory_enabled=1")
            c.execute(
                "INSERT OR IGNORE INTO metadata VALUES ('fingerprint_salt', ?)",
                (secrets.token_hex(32),),
            )
            # A server restart cannot resume an in-flight HTTP response.
            c.execute(
                "UPDATE requests SET status='interrupted',error_code='server_restarted', "
                "finished_at=? WHERE status='running'",
                (time.time(),),
            )
        path.chmod(0o600)

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def rows(self, sql: str, args=()):
        with self.connect() as c:
            return [dict(r) for r in c.execute(sql, args)]

    def one(self, sql: str, args=()):
        rows = self.rows(sql, args)
        return rows[0] if rows else None

    def execute(self, sql: str, args=()):
        with self.connect() as c:
            c.execute(sql, args)

    @property
    def salt(self) -> bytes:
        return self.one("SELECT value FROM metadata WHERE key='fingerprint_salt'")["value"].encode()

    def project(self, identifier: str):
        p = self.one(
            "SELECT * FROM projects WHERE (id=? OR name=?) AND archived=0", (identifier, identifier)
        )
        if not p:
            raise CCAskError("项目不存在，请先在网页创建项目。", "project_not_found", 404)
        return self.decode_project(p)

    @staticmethod
    def decode_project(p):
        return {**p, "parameters": json.loads(p["parameters"])}

    def save_project(self, data, project_id=None):
        now = time.time()
        try:
            if project_id:
                self.project(project_id)
                self.execute(
                    "UPDATE projects SET name=?,mode=?,provider_id=?,model=?,instructions=?,"
                    "parameters=?,description=?,revision=revision+1,updated_at=? WHERE id=?",
                    (
                        data["name"],
                        data["mode"],
                        data.get("provider_id"),
                        data["model"],
                        data.get("instructions", ""),
                        dumps(data.get("parameters", {})),
                        data.get("description", ""),
                        now,
                        project_id,
                    ),
                )
            else:
                project_id = uid()
                self.execute(
                    "INSERT INTO projects(id,name,mode,provider_id,model,instructions,parameters,"
                    "created_at,updated_at,description) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        project_id,
                        data["name"],
                        data["mode"],
                        data.get("provider_id"),
                        data["model"],
                        data.get("instructions", ""),
                        dumps(data.get("parameters", {})),
                        now,
                        now,
                        data.get("description", ""),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise CCAskError("项目名已经存在。", "project_name_exists", 409) from exc
        return self.project(project_id)

    def session(self, project: str, name: str | None, memory: int = 0):
        memory = normalize_memory(memory)
        p = self.project(project)
        name = name or uid()
        with self.connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO sessions"
                "(id,project_id,name,memory_enabled,generation,memory_rounds,created_at) "
                "VALUES (?,?,?,?,0,?,?)",
                (uid(), p["id"], name, int(memory > 0), memory, time.time()),
            )
            row = dict(
                c.execute(
                    "SELECT * FROM sessions WHERE project_id=? AND name=?", (p["id"], name)
                ).fetchone()
            )
        return row

    def delete_project(self, project_id: str):
        with self.connect() as c:
            # Serialize the running-request check and deletion with request creation.
            c.execute("BEGIN IMMEDIATE")
            project = c.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project:
                raise CCAskError("项目不存在。", "project_not_found", 404)
            if c.execute(
                "SELECT 1 FROM requests WHERE project_id=? AND status='running' LIMIT 1",
                (project_id,),
            ).fetchone():
                raise CCAskError(
                    "项目还有正在进行的调用，请等调用结束后再删除。", "project_busy", 409
                )
            connections = c.execute(
                "SELECT DISTINCT connection_version FROM requests "
                "WHERE project_id=? AND connection_version IS NOT NULL",
                (project_id,),
            ).fetchall()
            c.execute(
                "DELETE FROM usage WHERE request_id IN "
                "(SELECT id FROM requests WHERE project_id=?)",
                (project_id,),
            )
            c.execute(
                "DELETE FROM messages WHERE session_id IN "
                "(SELECT id FROM sessions WHERE project_id=?)",
                (project_id,),
            )
            c.execute("DELETE FROM requests WHERE project_id=?", (project_id,))
            c.execute("DELETE FROM sessions WHERE project_id=?", (project_id,))
            c.execute("DELETE FROM projects WHERE id=?", (project_id,))
            for connection in connections:
                c.execute(
                    "DELETE FROM connections WHERE id=? AND NOT EXISTS "
                    "(SELECT 1 FROM requests WHERE connection_version=connections.id)",
                    (connection[0],),
                )
        return {"deleted": True}

    def get_session(self, session_id: str):
        s = self.one("SELECT * FROM sessions WHERE id=?", (session_id,))
        if not s:
            raise CCAskError("会话不存在。", "session_not_found", 404)
        self.project(s["project_id"])
        return s

    def connection(self, provider, account, fingerprint):
        account_id = account.get("id", "")
        existing = self.one(
            "SELECT id FROM connections WHERE provider_id=? AND account_id=? AND fingerprint=?",
            (provider["id"], account_id, fingerprint),
        )
        if existing:
            return existing["id"]
        key = uid()
        self.execute(
            "INSERT INTO connections VALUES (?,?,?,?,?,?,?)",
            (
                key,
                provider["id"],
                provider["name"],
                account_id,
                account.get("label", ""),
                fingerprint,
                time.time(),
            ),
        )
        return key
