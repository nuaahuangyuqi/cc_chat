import asyncio
import json

import httpx

from .ccswitch import validate_local_url
from .errors import CCAskError


class ProxyTransport:
    def __init__(self, timeout: float = 180, http_transport=None):
        self.timeout = timeout
        self.http_transport = http_transport

    async def generate(self, base_url, body, headers):
        validate_local_url(base_url)
        try:
            async with asyncio.timeout(self.timeout):
                async with (
                    httpx.AsyncClient(
                        timeout=httpx.Timeout(self.timeout, connect=3),
                        trust_env=False,
                        transport=self.http_transport,
                        follow_redirects=False,
                    ) as client,
                    client.stream(
                        "POST", base_url + "/v1/responses", json=body, headers=headers
                    ) as response,
                ):
                    if response.status_code >= 300:
                        # Upstream bodies can contain credentials or user content. Expose a
                        # controlled error instead of copying their text into logs or clients.
                        code = response.status_code
                        if code in (401, 403):
                            raise CCAskError(
                                "账号或 API 授权失败，请在 CC Switch 检查配置。",
                                "upstream_auth_failed",
                                code,
                            )
                        if code == 429:
                            raise CCAskError(
                                "模型额度或速率已达上限，请检查 CC Switch。",
                                "upstream_rate_limited",
                                429,
                            )
                        if code == 400:
                            raw = bytearray()
                            async for chunk in response.aiter_bytes():
                                raw.extend(chunk[: max(0, 8192 - len(raw))])
                                if len(raw) >= 8192:
                                    break
                            try:
                                error = json.loads(raw).get("error", {})
                            except (ValueError, AttributeError):
                                error = {}
                            if isinstance(error, dict) and error.get("code") == "model_not_found":
                                raise CCAskError(
                                    "当前账号或供应商不支持所选模型，请刷新连接并重新选择模型。",
                                    "model_unavailable",
                                    400,
                                )
                        raise CCAskError(
                            f"CC Switch 返回 HTTP {code}，请查看其请求日志。", "upstream_error", 502
                        )
                    content_type = response.headers.get("content-type", "")
                    # CC Switch's native official Responses route can omit Content-Type.
                    # The request explicitly asks for streaming, so default to SSE.
                    if content_type and "text/event-stream" not in content_type:
                        raw = await response.aread()
                        try:
                            result = json.loads(raw)
                        except ValueError as exc:
                            raise CCAskError("代理响应格式异常。", "invalid_response", 502) from exc
                        return self.complete(result)
                    event_lines = []
                    async for line in response.aiter_lines():
                        if line == "":
                            result = self.event(event_lines)
                            event_lines = []
                            if result is not None:
                                return result
                        elif line.startswith("data:"):
                            event_lines.append(line[5:].lstrip(" "))
                    if event_lines:
                        result = self.event(event_lines)
                        if result is not None:
                            return result
                    raise CCAskError("模型响应在完成前中断，请重试。", "stream_interrupted", 502)
        except CCAskError:
            raise
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise CCAskError("模型调用超时，本轮问答未加入记忆。", "request_timeout", 504) from exc
        except httpx.HTTPError as exc:
            raise CCAskError(
                "无法连接 CC Switch 代理，请确认其保持运行并已启用聚合模式。",
                "proxy_unavailable",
                503,
            ) from exc

    def event(self, lines):
        data = "\n".join(lines)
        if not data or data == "[DONE]":
            return None
        try:
            event = json.loads(data)
        except ValueError as exc:
            raise CCAskError("模型流式响应格式异常。", "invalid_response", 502) from exc
        kind = event.get("type")
        if kind == "response.completed":
            return self.complete(event.get("response", {}))
        if kind in {"error", "response.failed", "response.incomplete", "response.cancelled"}:
            raise CCAskError(
                "模型未能完整回答，请查看 CC Switch 请求日志。", "incomplete_response", 502
            )
        return None

    @staticmethod
    def complete(result):
        if result.get("error") or result.get("status") not in ("completed",):
            raise CCAskError("模型未返回完整回答。", "incomplete_response", 502)
        if not isinstance(result.get("output"), list):
            raise CCAskError("模型响应缺少输出内容。", "invalid_response", 502)
        return result
