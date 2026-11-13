import asyncio
import json

import httpx
import pytest
from conftest import completion

from ccask.errors import CCAskError
from ccask.transport import ProxyTransport


@pytest.mark.parametrize(
    "url", ["https://api.openai.com", "http://example.com", "http://127.0.0.1.example.com"]
)
async def test_rejects_nonlocal_destination(url):
    with pytest.raises(CCAskError) as info:
        await ProxyTransport().generate(url, {}, {})
    assert info.value.code == "invalid_proxy_address"


@pytest.mark.parametrize(
    "code,expected",
    [
        (401, "upstream_auth_failed"),
        (403, "upstream_auth_failed"),
        (429, "upstream_rate_limited"),
        (500, "upstream_error"),
        (302, "upstream_error"),
    ],
)
async def test_http_errors_are_controlled_and_redirects_not_followed(code, expected):
    t = ProxyTransport(
        http_transport=httpx.MockTransport(
            lambda r: httpx.Response(
                code, text="sk-sensitive-error", headers={"location": "https://example.com"}
            )
        )
    )
    with pytest.raises(CCAskError) as info:
        await t.generate("http://127.0.0.1:15721", {}, {})
    assert info.value.code == expected
    assert "sk-sensitive" not in str(info.value)


async def test_sse_multiline_and_final_frame_without_blank_line():
    body = json.dumps({"type": "response.completed", "response": completion("done")})
    t = ProxyTransport(
        http_transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text="event: response.completed\ndata: " + body,
            )
        )
    )
    result = await t.generate("http://localhost:15721", {}, {})
    assert result["output"][0]["content"][0]["text"] == "done"


async def test_connection_error():
    def handler(request):
        raise httpx.ConnectError("offline")

    with pytest.raises(CCAskError) as info:
        await ProxyTransport(http_transport=httpx.MockTransport(handler)).generate(
            "http://localhost:15721", {}, {}
        )
    assert info.value.code == "proxy_unavailable"


async def test_official_proxy_stream_without_content_type():
    body = json.dumps({"type": "response.completed", "response": completion("native")})
    t = ProxyTransport(
        http_transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, content=("event: response.completed\ndata: " + body + "\n\n").encode()
            )
        )
    )
    result = await t.generate("http://127.0.0.1:15721", {"stream": True}, {})
    assert result["output"][0]["content"][0]["text"] == "native"


async def test_model_unavailable_error():
    t = ProxyTransport(
        http_transport=httpx.MockTransport(
            lambda r: httpx.Response(
                400, json={"error": {"code": "model_not_found", "message": "private detail"}}
            )
        )
    )
    with pytest.raises(CCAskError) as info:
        await t.generate("http://127.0.0.1:15721", {}, {})
    assert info.value.code == "model_unavailable"
    assert "private detail" not in str(info.value)


async def test_total_timeout_is_reported():
    async def slow(request):
        await asyncio.Event().wait()

    t = ProxyTransport(timeout=0.01, http_transport=httpx.MockTransport(slow))
    with pytest.raises(CCAskError) as info:
        await t.generate("http://127.0.0.1:15721", {}, {})
    assert info.value.code == "request_timeout"
