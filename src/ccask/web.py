import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .config import Settings
from .db import Database
from .errors import CCAskError
from .menubar import monitor_settings, monitor_snapshot, save_monitor_settings
from .runtime import codex_path, preferences, save_codex_path
from .sdk_info import SDK_WHEEL, install_command
from .service import ConversationService
from .usage import UsageService


class ProjectDraft(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=120)
    mode: Literal["api", "gpt"]
    provider_id: str | None = None
    model: str = Field(min_length=1, max_length=300)
    instructions: str = Field(default="", max_length=100_000)
    parameters: dict = Field(default_factory=dict)

    @field_validator("name", "model")
    @classmethod
    def trim(cls, value):
        if not value.strip():
            raise ValueError("内容不能为空")
        return value.strip()

    @model_validator(mode="after")
    def validate_config(self):
        if self.mode == "api" and not self.provider_id:
            raise ValueError("请选择 API 供应商")
        if self.mode == "gpt":
            self.provider_id = None
        allowed = {"temperature", "top_p", "max_output_tokens", "reasoning", "text"}
        if set(self.parameters) - allowed:
            raise ValueError("参数仅支持 temperature、top_p、max_output_tokens、reasoning 和 text")
        for key, maximum in [("temperature", 2), ("top_p", 1)]:
            if key in self.parameters:
                v = self.parameters[key]
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= maximum:
                    raise ValueError(f"{key} 参数无效")
        if "max_output_tokens" in self.parameters:
            v = self.parameters["max_output_tokens"]
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError("max_output_tokens 必须为正整数")
        if "reasoning" in self.parameters:
            r = self.parameters["reasoning"]
            if not isinstance(r, dict) or set(r) - {"effort", "summary"}:
                raise ValueError("reasoning 参数无效")
        if "text" in self.parameters:
            r = self.parameters["text"]
            if not isinstance(r, dict) or set(r) - {"verbosity"}:
                raise ValueError("text 仅支持 verbosity")
        return self


class SessionDraft(BaseModel):
    project: str = Field(min_length=1, max_length=200)
    memory: bool = False
    session_id: str | None = Field(default=None, min_length=1, max_length=200)


class MemoryDraft(BaseModel):
    enabled: bool


class RuntimeDraft(BaseModel):
    codex_path: str = Field(default="", max_length=4096)


class MonitorDraft(BaseModel):
    project_ids: list[str] = Field(default_factory=list, max_length=100)
    period: Literal["today", "7d", "30d", "all"] = "today"


class AskDraft(BaseModel):
    content: list[dict] = Field(min_length=1, max_length=21)


def create_app(settings=None, service=None):
    settings = settings or Settings.from_env()
    if service is None:
        db = Database(settings.db_path)
        service = ConversationService(settings, db)
    db = service.db
    usage = UsageService(db, service.cc)

    @asynccontextmanager
    async def lifespan(app):
        async def sync_loop():
            while True:
                await asyncio.to_thread(usage.sync)
                await asyncio.sleep(settings.sync_interval)

        task = asyncio.create_task(sync_loop())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    app = FastAPI(title="CC Ask", version=__version__, lifespan=lifespan)
    app.state.service = service
    app.state.usage = usage
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"]
    )

    @app.middleware("http")
    async def local_browser(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme != "http" or parsed.netloc != request.headers.get("host"):
                return JSONResponse(
                    {"error": {"code": "origin_denied", "message": "请从本机 CC Ask 网页访问。"}},
                    403,
                )
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse(
                {"error": {"code": "invalid_input", "message": "请求长度无效。"}}, 400
            )
        if length > 60 * 1024 * 1024:
            return JSONResponse(
                {"error": {"code": "body_too_large", "message": "请求内容过大。"}}, 413
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "style-src-attr 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(CCAskError)
    async def domain_error(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": str(exc)}}, exc.status)

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        # Only exception type: database drivers / HTTP libraries may embed confidential inputs.
        logging.getLogger("ccask").error("Request failed (%s)", type(exc).__name__)
        return JSONResponse(
            {"error": {"code": "internal_error", "message": "本地服务处理失败，请重试。"}}, 500
        )

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/setup")
    async def setup():
        return {
            "install_path": str(Path(__file__).resolve().parents[2]),
            "desktop": bool(getattr(sys, "frozen", False)),
            "sdk_wheel": SDK_WHEEL if (Path(__file__).parent / "sdk" / SDK_WHEEL).is_file() else None,
            "sdk_python": ">=3.7",
            "install_command": install_command(),
            "menubar": monitor_settings(settings),
            "codex_path": codex_path(settings),
            "configured_codex_path": preferences(settings).get("codex_path", ""),
            "data_dir": str(settings.data_dir),
            "cc_dir": str(settings.cc_dir),
        }

    @app.put("/api/settings")
    async def runtime_settings(draft: RuntimeDraft):
        return save_codex_path(settings, draft.codex_path)

    @app.put("/api/settings/menubar")
    async def save_menubar(draft: MonitorDraft):
        return await asyncio.to_thread(
            save_monitor_settings, settings, db, draft.project_ids, draft.period
        )

    @app.get("/api/menubar")
    async def menubar_usage():
        return await asyncio.to_thread(monitor_snapshot, settings, db, usage)

    @app.get("/api/sdk/{filename}")
    async def sdk(filename: str):
        path = Path(__file__).parent / "sdk" / filename
        if Path(filename).name != filename or not filename.endswith(".whl") or not path.is_file():
            raise CCAskError("客户端安装包不存在，请重新打包 App。", "sdk_missing", 404)
        return FileResponse(path, filename=filename)

    @app.get("/api/connection")
    async def connection():
        return await service.cc.status()

    @app.get("/api/projects")
    async def projects(include_archived: bool = False):
        sql = "SELECT * FROM projects" + ("" if include_archived else " WHERE archived=0")
        return [db.decode_project(r) for r in db.rows(sql + " ORDER BY created_at DESC")]

    def check_provider(draft):
        if draft.mode == "api":
            state = service.cc.state()
            if not any(p["id"] == draft.provider_id for p in state["providers"]):
                raise CCAskError("请选择 CC Switch 中已有的供应商。", "provider_not_found")

    @app.post("/api/projects", status_code=201)
    async def create_project(draft: ProjectDraft):
        check_provider(draft)
        return db.save_project(draft.model_dump())

    @app.put("/api/projects/{project_id}")
    async def update_project(project_id: str, draft: ProjectDraft):
        check_provider(draft)
        return db.save_project(draft.model_dump(), project_id)

    @app.post("/api/projects/{project_id}/archive")
    async def archive_project(project_id: str):
        p = db.project(project_id)
        db.execute("UPDATE projects SET archived=1 WHERE id=?", (p["id"],))
        return {"archived": True}

    @app.delete("/api/projects/{project_id}")
    async def delete_project(project_id: str):
        return await asyncio.to_thread(usage.delete_project, project_id)

    @app.post("/api/projects/{project_id}/test")
    async def test_project(project_id: str):
        project = db.project(project_id)
        session = db.session(project["id"], None, False)
        started = time.monotonic()
        reply = await service.ask(
            session["id"], [{"type": "input_text", "text": "请只回复：连接成功。"}]
        )
        await asyncio.to_thread(usage.sync)
        return {**reply, "latency_ms": round((time.monotonic() - started) * 1000)}

    @app.post("/api/sessions", status_code=201)
    async def create_session(draft: SessionDraft):
        result = db.session(draft.project, draft.session_id, draft.memory)
        # Initialization and memory mutations use the same queue as model calls.
        await service.set_memory(result["id"], draft.memory)
        return db.get_session(result["id"])

    @app.put("/api/sessions/{session_id}/memory")
    async def memory(session_id: str, draft: MemoryDraft):
        return await service.set_memory(session_id, draft.enabled)

    @app.post("/api/sessions/{session_id}/clear")
    async def clear(session_id: str):
        return await service.clear(session_id)

    @app.post("/api/sessions/{session_id}/ask")
    async def ask(session_id: str, draft: AskDraft):
        return await service.ask(session_id, draft.content)

    @app.post("/api/usage/sync")
    async def sync():
        return await asyncio.to_thread(usage.sync)

    @app.get("/api/usage")
    async def usage_report(
        project_id: str | None = None,
        start: float | None = None,
        end: float | None = None,
        group_by: Literal["project", "connection", "account", "model", "provider"] = "connection",
        account_id: str | None = None,
        model: str | None = None,
        connection_id: str | None = None,
    ):
        if start is not None and end is not None and start >= end:
            raise CCAskError("结束日期需晚于开始日期。", "invalid_date_range")
        return await asyncio.to_thread(
            usage.report, project_id, start, end, group_by, account_id, model, connection_id
        )

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(static / "index.html")

    return app
