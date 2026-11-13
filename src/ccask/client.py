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
        memory: bool = False,
        session_id: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = 240,
    ):
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
            if bool(state["memory_enabled"]) != memory:
                self._set_memory(memory)
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

    def _set_memory(self, enabled):
        self._call("PUT", f"/api/sessions/{self._id}/memory", json={"enabled": enabled})
        self.memory = enabled

    def start_memory(self):
        self._set_memory(True)

    def stop_memory(self):
        self._set_memory(False)

    def clear_memory(self):
        self._call("POST", f"/api/sessions/{self._id}/clear")

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
