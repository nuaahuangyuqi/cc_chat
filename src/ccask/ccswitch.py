"""Read-only integration with CC Switch 4.0.25. Never exports upstream credentials."""

import hashlib
import hmac
import json
import sqlite3
import tomllib
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import Settings
from .db import dumps
from .errors import CCAskError


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {} if default is None else default


def toml(text):
    try:
        return tomllib.loads(text or "")
    except (ValueError, TypeError):
        return {}


def binding(provider):
    b = provider["meta"].get("authBinding") or {}
    return b.get("accountId", "") if b.get("authProvider") == "codex_oauth" else ""


def official(provider):
    cfg = provider["config"]
    model_provider = toml(cfg.get("config", "")).get("model_provider", "openai")
    explicit_url = any(cfg.get(k) for k in ("base_url", "baseUrl", "baseURL"))
    return (
        not explicit_url
        and model_provider == "openai"
        and (
            bool(binding(provider))
            or provider["id"] == "codex-official"
            or provider.get("category") == "official"
        )
    )


class CCSwitch:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_path = settings.cc_dir / "cc-switch.db"

    @contextmanager
    def connect(self):
        if not self.db_path.is_file():
            raise CCAskError(
                "找不到 CC Switch 数据库，请在连接页检查数据目录。", "cc_database_missing", 503
            )
        try:
            c = sqlite3.connect(self.db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA query_only=ON")
        except sqlite3.Error as exc:
            raise CCAskError("无法读取 CC Switch 数据库。", "cc_database_unavailable", 503) from exc
        try:
            yield c
        except sqlite3.Error as exc:
            raise CCAskError(
                "CC Switch 数据结构不兼容或数据库暂时忙，请刷新连接。", "cc_schema_error", 503
            ) from exc
        finally:
            c.close()

    def state(self):
        with self.connect() as c:
            providers = []
            for row in c.execute("SELECT * FROM providers WHERE app_type='codex'"):
                r = dict(row)
                try:
                    r["config"] = json.loads(r.pop("settings_config"))
                    r["meta"] = json.loads(r["meta"] or "{}")
                except (ValueError, TypeError) as exc:
                    raise CCAskError(
                        "CC Switch 供应商配置格式异常。", "invalid_provider", 503
                    ) from exc
                providers.append(r)
            config = c.execute("SELECT * FROM proxy_config WHERE app_type='codex'").fetchone()
            proxy = dict(config) if config else {}
        device = (
            read_json(self.settings.cc_dir / "live-state.json").get("apps", {}).get("codex", {})
        )
        stack = device.get("stack", {})
        address = proxy.get("listen_address", "127.0.0.1")
        if address not in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}:
            raise CCAskError("代理地址必须是本机地址。", "invalid_proxy_address")
        host = "[::1]" if address == "::1" else "127.0.0.1"
        port = int(proxy.get("listen_port", 15721))
        if not 1 <= port <= 65535:
            raise CCAskError("代理端口配置无效。", "invalid_proxy_address")
        return {
            "providers": providers,
            "proxy": proxy,
            "device": device,
            "stack": stack,
            "base_url": f"http://{host}:{port}",
            "route_id": device.get("proxy_route"),
            "aggregation": device.get("mode") == "proxy" and bool(stack.get("enabled")),
        }

    def catalog(self):
        # Use only known local catalog/cache locations; never query an upstream directly.
        paths = [
            self.settings.codex_dir / "cc-switch-model-catalog.json",
            self.settings.codex_dir / "models_cache.json",
        ]
        config_path = self.settings.codex_dir / "config.toml"
        try:
            cfg = toml(config_path.read_text())
            if cfg.get("model_catalog_json"):
                p = Path(cfg["model_catalog_json"]).expanduser()
                paths.insert(0, p if p.is_absolute() else self.settings.codex_dir / p)
        except OSError:
            cfg = {}
        for path in paths:
            models = []
            data = read_json(path)
            for entry in data.get("models", []) if isinstance(data, dict) else []:
                if not isinstance(entry, dict):
                    continue
                if entry.get("visibility") == "hide" or entry.get("hidden"):
                    continue
                name = entry.get("slug") or entry.get("id")
                if name:
                    models.append(
                        {
                            "id": name,
                            "label": entry.get("display_name") or name,
                            "modalities": entry.get("input_modalities", []),
                            "reasoning_efforts": (
                                [level["effort"] for level in entry["supported_reasoning_levels"]
                                 if isinstance(level, dict) and isinstance(level.get("effort"), str)]
                                if isinstance(entry.get("supported_reasoning_levels"), list)
                                else None
                            ),
                            "default_reasoning_effort": entry.get("default_reasoning_level"),
                        }
                    )
            if models:
                # The active catalog reflects the current account. Merging an older account's
                # models_cache.json would advertise models that the new account cannot use.
                return list({m["id"]: m for m in models}.values())
        if cfg.get("model"):
            return [{"id": cfg["model"], "label": cfg["model"], "modalities": []}]
        return []

    def describe(self, state=None):
        s = state or self.state()
        providers = []
        keys = s["stack"].get("keys", {})
        members = s["stack"].get("members", [])
        catalog = self.catalog()
        for p in s["providers"]:
            key = next((k for k, v in keys.items() if v == p["id"]), None)
            is_official = official(p)
            routable = s["aggregation"] and (
                p["id"] == s["route_id"] or (p["id"] in members and bool(key) and not is_official)
            )
            models = []
            if key:
                models = [m for m in catalog if m["id"].startswith(f"ccs-{key}/")]
            if p["id"] == s["route_id"]:
                models += [m for m in catalog if not m["id"].startswith("ccs-")]
            default = toml(p["config"].get("config", "")).get("model")
            if default and not is_official:
                mid = f"ccs-{key}/{default}" if key else default
                if not any(m["id"] == mid for m in models):
                    models.append({"id": mid, "label": default, "modalities": []})
            providers.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "mode": "gpt" if is_official else "api",
                    "account_id": binding(p),
                    "routable": routable,
                    "default": p["id"] == s["route_id"],
                    "models": list({m["id"]: m for m in models}.values()),
                }
            )
        return {
            "aggregation": s["aggregation"],
            "proxy_url": s["base_url"],
            "logging": bool(s["proxy"].get("enable_logging")),
            "providers": providers,
            "data_directory": str(self.settings.cc_dir),
            "catalog": catalog,
        }

    async def status(self):
        try:
            s = self.state()
            result = self.describe(s)
            async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
                try:
                    r = await client.get(s["base_url"] + "/health")
                    result["proxy_online"] = r.is_success
                except httpx.HTTPError:
                    result["proxy_online"] = False
            marker = read_json(self.settings.cc_dir / "codex_managed_oauth_live_auth.json")
            auth = read_json(self.settings.codex_dir / "auth.json")
            tokens = auth.get("tokens") or {}
            active = next(
                (p for p in result["providers"] if p["default"] and p["mode"] == "gpt"), None
            )
            result["account_ready"] = bool(
                tokens.get("access_token")
                and active
                and (not active["account_id"] or marker.get("account_id") == active["account_id"])
            )
            result["ready"] = all(result[k] for k in ["aggregation", "proxy_online", "logging"])
            return result
        except (CCAskError, OSError, ValueError, TypeError) as exc:
            return {
                "ready": False,
                "proxy_online": False,
                "aggregation": False,
                "logging": False,
                "providers": [],
                "catalog": [],
                "account_ready": False,
                "data_directory": str(self.settings.cc_dir),
                "error": str(exc)
                if isinstance(exc, CCAskError)
                else "CC Switch 配置读取失败，请检查数据目录和配置格式。",
                "error_code": exc.code if isinstance(exc, CCAskError) else "cc_config_error",
            }

    def resolve(self, project, salt):
        s = self.state()
        if not s["aggregation"]:
            raise CCAskError("请在 CC Switch 的 Codex 页面启用聚合模式。", "aggregation_off", 503)
        if not s["proxy"].get("enable_logging"):
            raise CCAskError(
                "请在 CC Switch 开启代理请求日志，以便统计项目用量。", "logging_off", 503
            )
        if project["mode"] == "gpt":
            p = next((p for p in s["providers"] if p["id"] == s["route_id"] and official(p)), None)
            if not p:
                raise CCAskError(
                    "请将当前 GPT 官方账号设为 CC Switch 聚合模式的默认供应商。",
                    "official_route_required",
                    503,
                )
            wire_model = project["model"]
            if wire_model.startswith("ccs-"):
                raise CCAskError("GPT 项目需要选择官方模型。", "invalid_model")
        else:
            p = next((p for p in s["providers"] if p["id"] == project["provider_id"]), None)
            if not p or official(p):
                raise CCAskError(
                    "API 供应商已移除或类型已改变，请编辑项目。", "provider_removed", 409
                )
            key = next((k for k, v in s["stack"].get("keys", {}).items() if v == p["id"]), None)
            if p["id"] not in s["stack"].get("members", []) or not key:
                raise CCAskError(
                    "请将项目的 API 供应商加入 CC Switch 聚合名单。", "provider_not_aggregated", 409
                )
            prefix = f"ccs-{key}/"
            model = project["model"]
            if model.startswith("ccs-") and not model.startswith(prefix):
                raise CCAskError("模型不属于项目选择的供应商，请重新选择。", "invalid_model")
            wire_model = model if model.startswith(prefix) else prefix + model
        fingerprint = hmac.new(
            salt, dumps({"config": p["config"], "binding": binding(p)}).encode(), hashlib.sha256
        ).hexdigest()
        return s, p, wire_model, fingerprint

    def logs_for(self, tracking_ids):
        if not tracking_ids:
            return []
        ids = ["codex_" + i for i in tracking_ids]
        marks = ",".join("?" for _ in ids)
        with self.connect() as c:
            return [
                dict(r)
                for r in c.execute(
                    f"SELECT * FROM proxy_request_logs WHERE data_source='proxy' "
                    f"AND app_type='codex' AND session_id IN ({marks})",
                    ids,
                )
            ]


def validate_local_url(url):
    p = urlparse(url)
    if p.scheme != "http" or p.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise CCAskError("模型请求只能发送到本机 CC Switch 代理。", "invalid_proxy_address")
