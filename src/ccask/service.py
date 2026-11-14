import asyncio
import base64
import hashlib
import json
import time
from contextlib import asynccontextmanager

from .auth import CodexAuth
from .ccswitch import CCSwitch
from .client import image_content, normalize_default_memory, normalize_memory
from .config import Settings
from .db import Database, dumps, uid
from .errors import CCAskError
from .transport import ProxyTransport


class SessionLocks:
    """Reference-counted locks: queued operations share one lock, idle sessions use no memory."""

    def __init__(self):
        self._entries = {}

    @asynccontextmanager
    async def hold(self, key):
        entry = self._entries.setdefault(key, [asyncio.Lock(), 0])
        entry[1] += 1
        try:
            async with entry[0]:
                yield
        finally:
            entry[1] -= 1
            if not entry[1]:
                self._entries.pop(key, None)


def validate_content(content):
    if not content or len(content) > 21:
        raise CCAskError("请输入问题，每次最多附带 20 张图片。", "invalid_input")
    size = 0
    normalized = []
    for part in content:
        kind = part.get("type")
        if kind == "input_text":
            text = part.get("text")
            if not isinstance(text, str) or len(text) > 1_000_000:
                raise CCAskError("问题内容无效或过长。", "invalid_input")
            normalized.append({"type": "input_text", "text": text})
        elif kind == "input_image":
            url = part.get("image_url", "")
            if not isinstance(url, str) or not url.startswith("data:image/"):
                raise CCAskError("图片须由客户端上传为本地图片数据。", "invalid_image")
            try:
                raw = base64.b64decode(url.split(",", 1)[1], validate=True)
            except (ValueError, IndexError) as exc:
                raise CCAskError("图片编码无效。", "invalid_image") from exc
            size += len(raw)
            normalized.append(image_content(raw))
        else:
            raise CCAskError("不支持的消息内容类型。", "invalid_input")
    if size > 40 * 1024 * 1024:
        raise CCAskError("每次请求的图片总大小最多 40 MB。", "images_too_large")
    if not any(p.get("text", "").strip() or p["type"] == "input_image" for p in normalized):
        raise CCAskError("请输入问题或附带图片。", "empty_input")
    return normalized


class ConversationService:
    def __init__(self, settings: Settings, db: Database, cc=None, auth=None, transport=None):
        self.settings = settings
        self.db = db
        self.cc = cc or CCSwitch(settings)
        self.auth = auth or CodexAuth(settings)
        self.transport = transport or ProxyTransport(settings.timeout)
        self.locks = SessionLocks()

    async def set_memory(self, session_id, memory=None, default_memory=None):
        if memory is not None:
            memory = normalize_memory(memory)
        if default_memory is not None:
            default_memory = normalize_default_memory(default_memory)
        async with self.locks.hold(session_id):
            session = self.db.get_session(session_id)
            memory = session["memory_rounds"] if memory is None else memory
            native = session["default_memory"] if default_memory is None else int(default_memory)
            changed = session["memory_rounds"] != memory or session["default_memory"] != native
            self.db.execute(
                "UPDATE sessions SET memory_enabled=?,memory_rounds=?,default_memory=?,"
                "response_id=CASE WHEN ? THEN NULL ELSE response_id END,"
                "response_context=CASE WHEN ? THEN NULL ELSE response_context END WHERE id=?",
                (int(memory > 0), memory, native, changed, changed, session_id),
            )
            return {
                "memory_enabled": memory > 0, "memory_rounds": memory,
                "default_memory": bool(native),
            }

    async def clear(self, session_id):
        async with self.locks.hold(session_id):
            return self.db.delete_sessions(session_id=session_id)

    async def clear_sessions(self, project=None, *, all_projects=False):
        # Synchronous transaction: rejects running calls before deleting anything.
        return self.db.delete_sessions(project, all_projects=all_projects)

    async def ask(self, session_id, content):
        content = validate_content(content)
        async with self.locks.hold(session_id):
            session = self.db.get_session(session_id)
            project = self.db.project(session["project_id"])
            request_id, tracking_id = uid(), uid()
            snapshot = {
                k: project[k] for k in ["id", "name", "mode", "provider_id", "model", "revision"]
            }
            self.db.execute(
                "INSERT INTO requests(id,project_id,session_id,tracking_id,snapshot,status,"
                "started_at) VALUES (?,?,?,?,?,'running',?)",
                (request_id, project["id"], session_id, tracking_id, dumps(snapshot), time.time()),
            )
            try:
                state, provider, wire_model, fingerprint = self.cc.resolve(project, self.db.salt)
                headers = {
                    "Authorization": "Bearer PROXY_MANAGED",
                    "session_id": tracking_id,
                    "Accept": "text/event-stream",
                    "User-Agent": "ccask/0.1.0",
                }
                account = {}
                if project["mode"] == "gpt":
                    native_headers, account = await self.auth.headers(provider)
                    headers.update(native_headers)
                connection = self.db.connection(provider, account, fingerprint)
                snapshot.update(
                    {
                        "provider_id": provider["id"],
                        "provider_name": provider["name"],
                        "account_id": account.get("id", ""),
                        "account_label": account.get("label", ""),
                        "wire_model": wire_model,
                        "connection_version": connection,
                    }
                )
                self.db.execute(
                    "UPDATE requests SET snapshot=?,connection_version=? WHERE id=?",
                    (dumps(snapshot), connection, request_id),
                )
                # Keep cache prefixes scoped to the same connection and project configuration.
                context_key = hashlib.sha256(
                    dumps(
                        [
                            connection,
                            wire_model,
                            session["generation"],
                            project["instructions"],
                            project["parameters"],
                        ]
                    ).encode()
                ).hexdigest()
                history = []
                native = bool(session["default_memory"])
                previous = (
                    session["response_id"]
                    if native and session["response_context"] == context_key else None
                )
                if session["memory_rounds"] and not previous:
                    # Successful rounds are committed as pairs in one transaction. Fetch
                    # the newest N pairs, then restore chronological order. Replay only
                    # visible messages: opaque reasoning may carry older state outside
                    # the selected window.
                    rows = self.db.rows(
                        "SELECT role,content FROM (SELECT id,role,content FROM messages "
                        "WHERE session_id=? AND generation=? ORDER BY id DESC LIMIT ?) "
                        "ORDER BY id",
                        (session_id, session["generation"], 2 * session["memory_rounds"]),
                    )
                    history = [
                        {"role": row["role"], "content": json.loads(row["content"])}
                        for row in rows
                    ]
                history.append({"role": "user", "content": content})
                body = {
                    **project["parameters"],
                    "model": wire_model,
                    "input": history,
                    "instructions": project["instructions"],
                    "store": native,
                    "stream": True,
                    "prompt_cache_key": hashlib.sha256(
                        (session_id + context_key).encode()
                    ).hexdigest(),
                }
                if previous:
                    body["previous_response_id"] = previous
                output = await self.transport.generate(state["base_url"], body, headers)
                parts = [
                    p
                    for item in output["output"]
                    if item.get("type") == "message"
                    and item.get("role", "assistant") == "assistant"
                    for p in item.get("content", [])
                ]
                text = "".join(
                    p.get("text", p.get("refusal", ""))
                    for p in parts
                    if p.get("type") in {"output_text", "refusal"}
                )
                if not text:
                    raise CCAskError("模型没有返回文字回答。", "empty_response", 502)
                response_id = output.get("id") if native else None
                if native and (not isinstance(response_id, str) or not response_id):
                    raise CCAskError(
                        "当前供应商没有返回会话续接标识，请关闭 default_memory 或更换支持续接的接口。",
                        "native_memory_unsupported", 502,
                    )
                now = time.time()
                with self.db.connect() as c:
                    c.execute(
                        "UPDATE sessions SET response_id=?,response_context=? WHERE id=?",
                        (response_id, context_key if native else None, session_id),
                    )
                    for role, message in [("user", content), ("assistant", text)]:
                        c.execute(
                            "INSERT INTO messages(session_id,generation,role,content,raw_output,"
                            "connection_version,request_id,created_at) VALUES (?,?,?,?,?,?,?,?)",
                            (
                                session_id,
                                session["generation"],
                                role,
                                dumps(message),
                                None,
                                context_key,
                                request_id,
                                now,
                            ),
                        )
                    c.execute(
                        "UPDATE requests SET status='completed',finished_at=? WHERE id=?",
                        (now, request_id),
                    )
                return {"text": text, "session_id": session["name"], "request_id": request_id}
            except BaseException as exc:
                code = exc.code if isinstance(exc, CCAskError) else "internal_error"
                status = "interrupted" if isinstance(exc, asyncio.CancelledError) else "failed"
                self.db.execute(
                    "UPDATE requests SET status=?,error_code=?,finished_at=? WHERE id=?",
                    (status, code, time.time(), request_id),
                )
                raise
