# CC Ask 启动说明

## 双击启动和关闭

1. 打开 CC Switch，在 Codex 中启用聚合模式和请求日志，配置好 API 供应商或 GPT 官方账号。
2. 双击根目录的 `启动.command`，服务会在后台运行，并自动打开网页。
3. 在网页的“连接管理”中刷新连接，再创建项目。
4. 使用完毕后，双击 `关闭.command` 停止后台服务。

网页地址：<http://127.0.0.1:8765>。关闭网页或启动时打开的终端窗口后，后台服务继续运行。重复双击启动脚本会打开现有服务；重复双击关闭脚本也可以。

先安装 uv。脚本自动安装锁定依赖，使用仓库外的 `~/Library/Caches/cc_chat/venv` 环境，无需手动激活虚拟环境。首次运行若 macOS 提示无法打开，请右键脚本选择“打开”。

## 在终端中运行

先进入本项目根目录：

```sh
./启动.command
./关闭.command
```

如需更换端口：

```sh
CCASK_PORT=8766 ./启动.command
./关闭.command
```

更换端口前先关闭现有服务。Python 客户端也要使用对应地址，例如 `Ask(project="论文助手", base_url="http://127.0.0.1:8766")`。

需要在终端前台运行、直接查看输出时：

```sh
export UV_PROJECT_ENVIRONMENT="$HOME/Library/Caches/cc_chat/venv"
export PYTHONDONTWRITEBYTECODE=1
uv run --frozen python -B -m ccask serve --open
```

前台启动后按 `Ctrl+C` 关闭；`关闭.command` 管理通过 `启动.command` 启动的后台服务。

## Python 调用

在网页创建“论文助手”项目后，保持服务和 CC Switch 运行：

```python
from ccask import Ask

with Ask(project="论文助手", memory=10, session_id="实验设计") as bot:
    print(bot.ask("建议三个实验方向").text)
```

默认两个记忆开关为 `default_memory=False, memory=0`；`memory=10` 带入最近 10 轮，支持续接的接口可设置 `default_memory=True`。`clear_memory()` 同时删除会话及名称。项目设置可选择“思考强度”。完整用法见 [Python 客户端使用说明](python-client.md)。

可使用 `uv run python -B examples/basic.py` 运行源码示例。桌面版及其他 Python 项目的客户端安装方式见 [macOS 说明](macos.md)。

## 数据、日志和排查

- 项目、会话和用量数据库：`~/.local/share/ccask/ccask.db`。
- CC Switch 配置目录：`~/.cc-switch`；Codex 配置目录：`~/.codex`。
- 后台日志及进程记录：`~/Library/Caches/ccask/<项目路径标识>/`。启动脚本会打印具体日志路径。
- 启动提示端口占用：关闭占用该端口的服务，或使用 `CCASK_PORT` 更换端口。
- 检查连接状态：`uv run python -B -m ccask doctor`。
- 模型调用需要 CC Switch 保持运行，GPT 项目需要默认供应商为已登录的官方账号。

可用环境变量：`CCASK_DATA_DIR`（数据库目录）、`CCASK_CC_DIR`、`CCASK_CODEX_DIR`、`CCASK_TIMEOUT`（调用超时秒数，默认 180）、`CCASK_PORT`（后台服务端口，默认 8765）。客户端可用 `CCASK_URL` 指定服务地址。

## 项目文件

- `src/`：Python 源码及网页静态资源，含后台服务管理代码。
- `tests/`：自动化测试源码。
- `examples/`：Python 调用示例。
- `release/mac/`：Mac 端源码、构建脚本、应用与 ZIP 安装包。
- `pyproject.toml`、`uv.lock`、`.python-version`：依赖、锁定版本及 Python 版本配置。
- `.git/`、`.gitignore`：版本管理文件。

源码服务需要 Python 3.12 或更高版本；独立客户端支持 Python 3.7+。在根目录设置上述 `UV_PROJECT_ENVIRONMENT` 后运行 `uv sync --frozen --group dev` 可安装开发依赖。

开发检查：

```sh
uv run python -B -m pytest -p no:cacheprovider
uv run ruff check --no-cache src tests examples release/mac/src release/mac/scripts release/mac/packaging/desktop_entry.py
```
