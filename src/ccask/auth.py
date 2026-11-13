import asyncio
import base64
import json
import sys
import time

from .ccswitch import binding, read_json
from .config import Settings
from .errors import CCAskError
from .runtime import codex_path, executable_env


def claims(token):
    try:
        part = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except (ValueError, IndexError, TypeError):
        return {}


class CodexAuth:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = asyncio.Lock()

    async def _refresh(self):
        executable = codex_path(self.settings)
        if not executable:
            raise CCAskError(
                "登录已过期，请在 CC Switch 重新激活账号，或安装 Codex CLI 自动刷新。",
                "login_expired",
                401,
            )
        command = (
            [sys.executable]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "ccask.desktop"]
        )
        proc = await asyncio.create_subprocess_exec(
            *command,
            "--codex-guard",
            executable,
            str(self.settings.codex_dir),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={**executable_env(executable), "CODEX_HOME": str(self.settings.codex_dir)},
        )

        async def send(message):
            proc.stdin.write((json.dumps(message) + "\n").encode())
            await proc.stdin.drain()

        async def response(identifier):
            while line := await proc.stdout.readline():
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if message.get("id") == identifier:
                    if message.get("error"):
                        raise CCAskError(
                            "登录刷新失败，请在 CC Switch 重新激活账号。",
                            "login_refresh_failed",
                            401,
                        )
                    return message.get("result")
            raise CCAskError("Codex 登录服务已退出。", "login_refresh_failed", 401)

        try:
            async with asyncio.timeout(30):
                await send(
                    {
                        "id": 1,
                        "method": "initialize",
                        "params": {"clientInfo": {"name": "ccask", "version": "0.1.0"}},
                    }
                )
                await response(1)
                await send({"method": "initialized"})
                await send({"id": 2, "method": "account/read", "params": {"refreshToken": True}})
                await response(2)
        except (TimeoutError, BrokenPipeError) as exc:
            raise CCAskError(
                "登录刷新超时，请在 CC Switch 检查账号。", "login_refresh_failed", 401
            ) from exc
        finally:
            if proc.returncode is None:
                proc.stdin.close()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except TimeoutError:
                    proc.kill()
                    await proc.wait()

    async def headers(self, provider):
        async with self._lock:
            path = self.settings.codex_dir / "auth.json"
            tokens = read_json(path).get("tokens") or {}
            access = tokens.get("access_token", "")
            if not access:
                raise CCAskError(
                    "请在 CC Switch 激活 GPT 账号，并确认 Codex 已完成登录。", "login_required", 401
                )
            exp = claims(access).get("exp")
            if exp and exp <= time.time() + 60:
                await self._refresh()
                tokens = read_json(path).get("tokens") or {}
                access = tokens.get("access_token", "")
            marker = read_json(self.settings.cc_dir / "codex_managed_oauth_live_auth.json")
            local_id = binding(provider)
            account_id = tokens.get("account_id")
            if local_id and (
                marker.get("account_id") != local_id
                or marker.get("chatgpt_account_id") != account_id
            ):
                raise CCAskError(
                    "当前登录与默认 GPT 账号不一致，请在 CC Switch 重新激活账号。",
                    "account_mismatch",
                    409,
                )
            if not access or not account_id:
                raise CCAskError("GPT 登录信息不完整，请重新登录。", "login_required", 401)
            identity = claims(tokens.get("id_token", ""))
            account = {
                "id": local_id or account_id,
                "label": identity.get("email") or provider["name"],
            }
            return {
                "Authorization": "Bearer " + access,
                "ChatGPT-Account-Id": account_id,
                "originator": "codex_cli_rs",
                "version": "0.167.0",
            }, account
