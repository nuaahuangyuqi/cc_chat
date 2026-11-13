import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

import httpx

from .errors import CCAskError, ConnectionError


def image_content(value: Union[str, Path, bytes]) -> dict:
    raw = value if isinstance(value, bytes) else Path(value).expanduser().read_bytes()
    if len(raw) > 20 * 1024 * 1024:
        raise CCAskError("每张图片最多 20 MB。", "image_too_large")
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif raw.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise CCAskError("图片格式需为 PNG、JPEG 或 WebP。", "invalid_image")
    return {
        "type": "input_image",
        "image_url": f"data:{mime};base64,{base64.b64encode(raw).decode()}",
    }


DEFAULT_MEMORY_ROUNDS = 10


def normalize_memory(memory):
    """Validate a history window; legacy booleans map to 10 or 0 rounds."""
    if isinstance(memory, bool):
        return DEFAULT_MEMORY_ROUNDS if memory else 0
    if not isinstance(memory, int) or not 0 <= memory <= 2**31 - 1:
        raise CCAskError("memory 须为非负整数，表示带入的最近问答轮数。", "invalid_memory")
    return memory


@dataclass(frozen=True)
class Reply:
    text: str
    session_id: str
    request_id: str

    def __str__(self):
        return self.text


class Ask:
    """A synchronous, persistent conversation using a project configured in CC Ask."""

    def __init__(
        self,
        project: str,
        memory: int = 0,
        session_id: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = 240,
    ):
        memory = normalize_memory(memory)
        self._resume_memory = memory or DEFAULT_MEMORY_ROUNDS
        self.base_url = base_url or os.environ.get("CCASK_URL", "http://127.0.0.1:8765")
        u = urlparse(self.base_url)
        if u.scheme != "http" or u.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise CCAskError("CC Ask 第一版仅连接本机 HTTP 服务。", "invalid_service_url")
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout, trust_env=False)
        try:
            state = self._call(
                "POST",
                "/api/sessions",
                json={
                    "project": project,
                    "memory": memory,
                    "session_id": session_id,
                },
            )
            self._id = state["id"]
            self.session_id = state["name"]
            self.memory = memory
            if "memory_rounds" not in state:
                raise CCAskError(
                    "请先将 CC Ask App 或本地服务升级到 0.1.2，再使用新版客户端。",
                    "service_upgrade_required",
                )
        except BaseException:
            self._http.close()
            raise

    def _call(self, method, path, **kwargs):
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ConnectionError(
                "无法连接 CC Ask，请打开 CC Ask App 或运行 ccask serve；长请求请检查服务日志。",
                "service_unavailable",
                503,
            ) from exc
        if response.is_error:
            try:
                detail = response.json().get("error", {})
                message, code = (
                    detail.get("message", "调用失败"),
                    detail.get("code", "request_failed"),
                )
            except (ValueError, AttributeError):
                message, code = "本地服务返回异常响应。", "invalid_service_response"
            raise CCAskError(message, code, response.status_code)
        return response.json()

    def ask(self, text: str, images=None) -> Reply:
        content = [{"type": "input_text", "text": text}]
        content.extend(image_content(i) for i in (images or []))
        return Reply(
            **self._call("POST", f"/api/sessions/{self._id}/ask", json={"content": content})
        )

    def set_memory(self, memory: int):
        """Set the number of recent completed rounds included in each request."""
        memory = normalize_memory(memory)
        self._call("PUT", f"/api/sessions/{self._id}/memory", json={"memory": memory})
        self.memory = memory
        if memory:
            self._resume_memory = memory

    def start_memory(self, rounds: Optional[int] = None):
        """Resume the last positive window (10 initially), or choose a new window."""
        self.set_memory(self._resume_memory if rounds is None else rounds)

    def stop_memory(self):
        """Send only the current question; successful rounds are still saved."""
        self.set_memory(0)

    def clear_memory(self):
        self._call("POST", f"/api/sessions/{self._id}/clear")

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
