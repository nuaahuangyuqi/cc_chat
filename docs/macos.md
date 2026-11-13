# CC Ask macOS 桌面版

发布包：`release/mac/CC-Ask-0.1.1-macos-arm64.zip`。解压，将 `CC Ask.app` 拖入“应用程序”，双击打开。桌面版已内置 Python 3.12 和依赖，日常打开 App 无需终端、Python 或 uv。

当前发布包适用于 Apple Silicon（arm64），最低系统版本设置为 macOS 14；实际验证机器为 arm64 / macOS 27.2。Intel Mac 需在 Intel 机器重新构建，本包不是 universal 应用。采用本地 ad-hoc 签名。

关闭窗口、菜单“退出”或 Command+Q 都会退出 App 并停止自身服务。正在调用时会先询问，选择“退出并中断”会终止请求。再次打开 App 会唤起现有窗口。服务固定监听 `127.0.0.1:8765`；若已有 CLI 服务或其他程序占用，App 会提示先停止原服务。

数据沿用 `~/.local/share/ccask`，替换 App 会保留项目、会话与统计。旧数据库需要补 description 字段时，先以 SQLite backup API 备份至同目录 `backups/`。日志在 `~/Library/Logs/CC Ask/desktop.log`，可从 App 菜单“查看日志…”打开。日志只记录安全事件和异常类型。

CC Switch 的账号、供应商、聚合、代理和请求日志由 CC Switch 管理。连接管理页会显示中文指引。GPT 使用本机 Codex 的登录，过期时通过 Codex CLI 刷新；支持 Homebrew、npm、nvm、fnm、常见用户路径及手动填写 Codex 路径。App 的退出不影响原有 CC Switch。

## 其他 Python 项目使用 Ask

先打开 App，再在对应 Python 3.7+ 环境安装一次：

```sh
NO_PROXY=127.0.0.1,localhost python -m pip install --upgrade "http://127.0.0.1:8765/api/sdk/ccask_client-0.1.1-py3-none-any.whl"
```

Python 调用页的安装框右上角有“复制安装命令”按钮。该 wheel 内只有 Ask 客户端、错误类型和依赖声明，无需源码目录。若原环境装过开发版 `ccask`，先在新虚拟环境使用客户端，避免同名模块混装。客户端在 Python 3.7 使用 HTTPX 0.24.1 系列，在较新 Python 上使用 HTTPX 0.28+，pip 会自动选择对应依赖。App 的内置服务和源码开发环境使用 Python 3.12。

```python
from ccask import Ask
with Ask("你的项目名", memory=True, session_id="日常会话") as bot:
    print(bot.ask("你好").text)
```

## 菜单栏监控

App 启动后，macOS 顶部菜单栏显示图表图标和监控范围内的 Token 用量。点击图标可查看统计表，包含项目、调用次数、Token、估算费用（美元）和成功率，以及合计和同步时间；每 5 秒刷新。表格最多显示前 10 个项目，合计覆盖整个监控范围。

从图标菜单选择“监控设置…”或在主窗口侧栏打开“设置”，可多选项目，并选择今日、近 7 天、近 30 天或全部时间。保存后自动生效并在下次启动保留。未选项目时显示全局用量，包含已归档项目的历史记录。选中的项目全部归档或删除后，也会回到全局用量。

图标菜单还提供“打开主窗口”“复制 Python 安装命令”“隐藏主窗口”和“退出 CC Ask”。隐藏窗口后本地服务和菜单栏监控继续运行；关闭窗口或退出 App 会停止服务。App 菜单中的“菜单栏用量”和“监控设置…”也可打开对应入口。

## 重新构建

构建机需要 uv 和 macOS；安装依赖的版本由 `uv.lock` 固定：

```sh
cd cc_chat
./release/mac/scripts/build_macos.sh
```

脚本自动检查当前架构、生成图标和独立客户端 wheel、运行测试与 Ruff、用 PyInstaller 构建、校验本地签名，最后用 ditto 生成 ZIP。打包资源使用明确清单，用户配置、账号、密钥和数据库不作为输入。

## 临时数据验证

```sh
export UV_PROJECT_ENVIRONMENT="$HOME/Library/Caches/cc_chat/venv"
export PYTHONDONTWRITEBYTECODE=1
uv run python release/mac/scripts/desktop_fixture.py '/tmp/CC Ask 验证'
open -n '/Applications/CC Ask.app' \
  --env 'CCASK_DATA_DIR=/tmp/CC Ask 验证/用户 数据' \
  --env 'CCASK_CC_DIR=/tmp/CC Ask 验证/离线 CC Switch' \
  --env 'CCASK_CODEX_DIR=/tmp/CC Ask 验证/Codex' \
  --env 'PATH=/usr/bin:/bin'
uv run python release/mac/scripts/verify_macos.py --data-dir '/tmp/CC Ask 验证/用户 数据'
```

fixture 只在本机动态端口返回模拟 SSE，既不读取真实凭据，也不访问模型。停止 fixture 可检验代理离线；启动前将 CCASK_CC_DIR 指向不存在的临时目录，可检验缺失配置。App 本身的健康检查不依赖 CC Switch。
