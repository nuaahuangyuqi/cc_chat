# cc_chat

通过 CC Switch 调用 API 模型或 GPT 官方账号的本地工具，包含网页工作台、macOS 桌面端和 Python 调用库。应用内名称为 **CC Ask**，Python 导入名为 `ccask`。

## 功能

- 为不同项目保存供应商、模型和参数，支持文本、图片和会话记忆。
- 按项目查看调用次数、Token、估算费用及调用记录。
- macOS 菜单栏监控多个项目的用量，未选择项目时显示全局统计。
- 独立 Python 客户端支持 Python 3.7+；桌面端内置运行环境。

## 目录

```text
cc_chat/
├── src/ccask/                    # 网页端、本地服务、共享逻辑和 Python 客户端
│   ├── static/                   # HTML、CSS、JavaScript 和界面资源
│   └── sdk/                      # 可安装的独立客户端 wheel
├── release/mac/
│   ├── src/ccask_mac/            # macOS 窗口、菜单栏和应用入口源码
│   ├── packaging/               # PyInstaller 配置与应用图标
│   ├── scripts/                 # 构建和验证脚本
│   ├── CC Ask.app/              # 本地构建产物，ZIP 中包含相同应用
│   └── CC-Ask-0.1.2-macos-arm64.zip
├── tests/                       # 自动化测试
├── examples/                    # Python 调用示例
└── docs/                        # 使用及构建说明
```

## macOS 使用

从 [Releases](https://github.com/nuaahuangyuqi/cc_chat/releases) 下载 Mac 安装包，解压后把 `CC Ask.app` 拖入“应用程序”。当前构建适用于 Apple Silicon，要求 macOS 14+。

在 CC Switch 中配置供应商或官方账号，并开启 Codex 聚合模式、代理和请求日志。打开 CC Ask 后，在“连接管理”检查连接，再创建项目。详细说明见 [macOS 使用说明](docs/macos.md)。

## 网页端运行

源码环境需要 Python 3.12+ 和 uv，在项目根目录执行：

```sh
export UV_PROJECT_ENVIRONMENT="$HOME/Library/Caches/cc_chat/venv"
export PYTHONDONTWRITEBYTECODE=1
uv sync --frozen --group dev
uv run --frozen python -B -m ccask serve --open
```

也可双击根目录的 `启动.command` 和 `关闭.command` 管理后台网页服务。默认地址为 `http://127.0.0.1:8765`。网页服务与 Mac App 使用同一端口，使用其中一种启动方式即可。详见 [网页端使用说明](docs/web.md)。

## Python 调用

先打开 App 或网页服务，在自己的 Python 3.7+ 环境安装客户端：

```sh
NO_PROXY=127.0.0.1,localhost python -m pip install --upgrade "http://127.0.0.1:8765/api/sdk/ccask_client-0.1.2-py3-none-any.whl"
```

网页 Python 调用页提供安装命令和示例代码的复制按钮。

```python
from ccask import Ask

with Ask("你的项目名", memory=10, session_id="日常会话") as bot:
    print(bot.ask("你好").text)
    bot.set_memory(3)  # 改为最近 3 轮
    bot.stop_memory()
    bot.start_memory()
    bot.clear_memory()
```

默认 `memory=0`，只发送当前问题；`memory=10` 带入当前问题之前最近 10 轮完整问答。成功问答都会保存在本地数据库，关闭记忆也会保存。固定 `session_id` 可跨进程继续使用历史。

完整参数、图片、记忆控制、异常处理和升级说明见 [Python 客户端使用说明](docs/python-client.md)。升级时先更新 App 或本地服务到 0.1.2，再安装新版客户端。

## Mac 构建

在 macOS 的项目根目录运行：

```sh
./release/mac/scripts/build_macos.sh
```

脚本使用仓库外的虚拟环境和临时构建目录，执行测试、Ruff、打包和签名检查，将应用及 ZIP 输出到 `release/mac/`。项目、会话和凭据保存在用户数据目录，构建资源采用明确清单。构建产物使用本地 ad-hoc 签名。

界面使用的 Inter 和 JetBrains Mono 字体许可保存在 [`src/ccask/static/licenses/`](src/ccask/static/licenses/)，并随安装包提供。
