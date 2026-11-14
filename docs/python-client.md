# CC Ask Python 客户端使用说明

适用版本：0.1.3。安装包名为 `ccask-client`，导入名为 `ccask`。

## 1. 准备和安装

1. 在 CC Switch 配置 API 供应商或登录 GPT 官方账号，开启 Codex 聚合模式、代理和请求日志。
2. 打开 CC Ask App 或源码网页服务，在“连接管理”刷新连接。
3. 创建项目并选择模型，例如“记忆测试”。使用期间保持两个应用运行。
4. 先更新 CC Ask 服务，再在运行脚本的 Python 环境安装对应客户端：

```sh
NO_PROXY=127.0.0.1,localhost python -m pip install --upgrade "http://127.0.0.1:8765/api/sdk/ccask_client-0.1.3-py3-none-any.whl"
```

在 App 的“Python 调用”页也可以复制安装命令。客户端支持 Python 3.7+，源码服务需要 Python 3.12+。模型和凭据通过 CC Switch 管理，脚本只需填写 CC Ask 的项目名或 ID。

```sh
python -c "import ccask; print(ccask.__version__)"
```

建议为客户端创建独立虚拟环境。源码包 `ccask` 和独立客户端 `ccask-client` 都提供同名模块，请使用不同环境安装。

## 2. 两种记忆分别控制

```python
from ccask import Ask

with Ask(
    project="记忆测试",
    default_memory=True,
    memory=0,
    session_id="我的会话",
) as bot:
    print(bot.ask("我是赛博坦海克斯").text)
    print(bot.ask("还记得我是谁吗？").text)
```

上例使用服务端会话续接，要求代理和供应商支持 `store=true` 与 `previous_response_id`。

| 参数组合 | 每次提问如何获得上下文 |
| --- | --- |
| `default_memory=False, memory=0` | 每次独立，只发送当前问题及项目指令 |
| `default_memory=False, memory=10` | 每次显式拼接当前会话最近 10 轮完整问答，再追加当前问题 |
| `default_memory=True, memory=0` | 首次只发当前问题，后续发送当前问题和上一次 response ID，由服务端接续上下文 |
| `default_memory=True, memory=10` | 建立新的服务端续接链时导入当前会话最近 10 轮，之后只发送新增问题和续接标识 |

两个参数的默认值分别为 `False` 和 `0`，保持旧代码的独立请求行为。希望连续聊天时显式设置 `default_memory=True`。

`default_memory` 是服务端会话续接开关。它与显式历史窗口独立，`memory=0` 不会关闭已经开启的服务端续接。服务端仍需使用历史上下文，历史也会产生相应输入 Token 用量。

`memory` 是从当前会话数据库读取的完整问答轮数。每轮包含“一次用户提问 + 一次成功完成的助手回答”，当前问题不计入轮数；始终取最近的 N 轮，并按时间顺序发送。不足 N 轮时使用现有历史。

原生续接开启后，`memory` 用于初始化新的续接链，不限制服务端后续累计的会话长度，也不会在每轮重复导入同一批历史。显式窗口随轮次滚动；它限制轮数，不限制 Token 或图片大小。

### 接口兼容性

CC Ask 会按所选项目通过 CC Switch 请求服务端续接。OpenAI 标准 Responses API 提供这种能力，但 GPT 官方账号的代理路线、第三方兼容接口可能采用不同限制。登录官方账号并不自动启用本库的服务端续接。

- 明确拒绝 `store` 或 `previous_response_id`、返回未存储状态、缺少续接标识时，会提示 `native_memory_unsupported`。
- 已存储的续接标识过期或失效时，会提示 `native_memory_expired`。
- 失败后会保留原来的本地历史和最后成功的续接标识，供排查或清空重开。
- 本库不会在报错后自动重试为全量历史拼接。可主动使用 `default_memory=False, memory=10`。

协议依据：[OpenAI 会话状态文档](https://developers.openai.com/api/docs/guides/conversation-state)。实际支持情况以当前代理路线和供应商为准。

## 3. 构造参数

```python
Ask(
    project="记忆测试",
    memory=0,
    session_id=None,
    default_memory=False,
    base_url="http://127.0.0.1:8765",
    timeout=240,
)
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `project` | 必填 | CC Ask 项目名或项目 ID |
| `default_memory` | `False` | 是否使用服务端会话续接；只能是布尔值 |
| `memory` | `0` | 显式带入的最近问答轮数；范围 0～2147483647 |
| `session_id` | `None` | 会话名称；省略时每个 `Ask` 自动创建新名称 |
| `base_url` | `CCASK_URL` 或 `http://127.0.0.1:8765` | 本机服务地址，显式参数优先 |
| `timeout` | `240` | 客户端等待服务返回的秒数 |

`default_memory` 是仅限关键字的参数。原先 `Ask("项目", 10, "会话")` 的参数位置继续有效。

`memory` 的旧布尔写法仍兼容：`True` 映射为 10 轮，`False` 映射为 0 轮。负数、小数、字符串和 `None` 会报错。

服务地址仅支持 HTTP 和 `127.0.0.1`、`localhost`、`::1` 等本机地址，客户端请求会绕过系统 HTTP 代理。

## 4. 会话隔离和恢复

```python
with Ask("记忆测试", default_memory=True, session_id="对话 A") as a:
    print(a.ask("我是赛博坦海克斯").text)

with Ask("记忆测试", default_memory=True, session_id="对话 B") as b:
    print(b.ask("我是谁？").text)  # 不使用 A 的历史

with Ask("记忆测试", default_memory=True, session_id="对话 A") as a:
    print(a.ask("还记得我的名字吗？").text)  # 续接 A
```

- 同一项目和相同 `session_id` 使用同一段会话。
- 不同项目或不同 `session_id` 各自保存历史和续接标识。
- 不传 `session_id` 时，每次创建 `Ask` 都使用一个新名称，可通过 `bot.session_id` 或 `reply.session_id` 获取。
- `with` 退出仅关闭 HTTP 连接，会话继续保存。
- 同一会话的请求顺序执行，不同会话可以独立处理。

每次创建 `Ask` 都会设置该会话的两个记忆参数，包括默认值。相同设置会保留原生续接链；改变任一记忆设置会重置续接标识，下一轮按新的设置建立上下文。因此恢复会话时应显式填写需要的参数。

切换供应商、账号、模型、项目指令或生成参数后，旧续接标识不会用于新配置。下一次按 `memory` 初始化新的续接链；`memory=0` 时不导入旧配置下的历史。

这些设置属于服务端会话，由同名会话的客户端共享。多个独立任务应使用不同名称。`bot.memory` 和 `bot.default_memory` 反映本客户端上次成功设置的值。

## 5. 运行时控制

```python
with Ask("记忆测试", default_memory=False, memory=10, session_id="实验 A") as bot:
    bot.set_memory(3)           # 显式历史改为最近 3 轮
    bot.stop_memory()           # 等价于 set_memory(0)
    bot.ask("独立回答这个问题")
    bot.start_memory()          # 恢复本客户端最近的正数窗口：3
    bot.start_memory(5)         # 显式改为 5 轮

    bot.set_default_memory(True)   # 开启服务端续接，下一轮建立新链
    bot.ask("开始连续讨论")
    bot.stop_memory()              # 只关闭显式历史，连续会话开关仍是 True
    bot.set_default_memory(False)  # 关闭服务端续接
```

`start_memory()` 在客户端尚未设置正数时默认开启 10 轮。暂停显式历史期间的成功问答也会保存，之后可进入窗口。

调整参数请调用上述方法，不要直接给属性赋值。重复设置相同值不会中断原生续接；改变值会重新建立续接链。

## 6. 清空当前会话，同时删除 session_id

```python
with Ask("记忆测试", default_memory=True, session_id="我的会话") as bot:
    bot.ask("我是赛博坦海克斯")
    result = bot.clear_memory()
    print(result)          # {"cleared": True, "deleted_sessions": 1}
    print(bot.session_id) # None

    # 原会话已经删除；此处自动创建新的随机名称，沿用两个记忆参数
    reply = bot.ask("开始新对话")
    print(bot.session_id)
```

`clear_memory()` 删除当前会话记录、名称、全部本地问答和本地保存的服务端续接标识。请求及用量记录保留，并解除与已删除会话的关联。

清空后不会立即创建替代会话；下一次 `ask()` 才创建随机名称的新会话。重复清空是安全的。此时调整记忆参数只调整客户端设置，也不会创建空会话。

重新显式使用已删除的名称时，将建立全新会话。其他还持有旧内部会话 ID 的客户端会收到 `session_not_found`，需要重新创建 `Ask`。

清空会等当前会话正在执行的请求结束后再删除。它删除本地记录并断开服务端续接；供应商已保存响应的物理删除及保留期限由其接口和数据策略管理。

## 7. 批量删除会话

```python
from ccask import clear_sessions

result = clear_sessions(project="记忆测试")  # 项目名或 ID
print(result["deleted_sessions"])

# 明确指定后，删除所有项目（含已归档项目）的全部会话
result = clear_sessions(all_projects=True)
```

`project` 和 `all_projects=True` 必须且只能指定一个。空参数不会默认清空全部。

批量清除删除所选范围的全部会话、历史和本地续接标识，保留项目配置、请求记录与用量。可通过 `base_url` 和 `timeout` 指定本地服务地址和等待时间；批量操作本身不会新建会话。

如果所选范围存在正在运行的调用，会报 `sessions_busy`，整次清除不生效。调用结束后再执行。已经被清除的范围再次清除时返回 0。

迁移备份位于数据库目录下的 `backups/`；清空当前数据库后，备份中的旧内容需要单独管理。

## 8. 项目中设置思考强度

在 CC Ask 项目“配置”页面的“回答要求”中选择“思考强度”，然后保存。Python 中继续使用项目名即可，下一次请求会使用新强度。

- 模型目录提供支持档位时，只显示这些档位。
- “模型默认”表示不显式传入 effort，由接口决定。
- 模型未声明档位时，可以按供应商说明选择，并自行确认其支持情况。
- 切换模型后不支持原档位时，页面会标明，保存时要求重新选择。
- 高级参数 JSON 与下拉框同步，`reasoning.summary` 等其他字段会保留。

配置存入项目的 `parameters.reasoning.effort`，例如：

```json
{"reasoning": {"effort": "high"}}
```

常见档位为 `none`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max`、`ultra`，具体以模型目录和供应商为准。提高强度通常增加耗时和 Token 使用量。GPT-6 系列启用思考时，需按官方兼容要求移除 `temperature`、`top_p` 等不兼容参数。

依据：[OpenAI 模型参数说明](https://developers.openai.com/api/docs/guides/latest-model#gpt-6-astra-update-api-and-model-parameters)。

## 9. 图片输入

```python
from pathlib import Path
from ccask import Ask

with Ask("图表分析", memory=2, session_id="实验图") as bot:
    print(bot.ask("比较结果", images=["figure.png", Path("chart.jpg")]).text)
    print(bot.ask("这张图的问题是什么？", images=[Path("other.webp").read_bytes()]).text)
```

图片列表支持路径字符串、`Path` 或原始 `bytes`，支持 PNG、JPEG、WebP。每张最多 20 MB，每次最多 20 张，总原始数据最多 40 MB；供应商和模型也需要支持图片。

文字每次最多 1,000,000 个字符，可用空字符串配合图片，但文字和图片不能同时为空。显式历史窗口中的旧图片随对应轮次发送，退出窗口后不再发送。服务端续接模式下，历史内容由服务端的上下文机制管理。

## 10. 返回值、保存和异常

`ask()` 返回 `Reply`，包含：

| 属性 | 内容 |
| --- | --- |
| `text` | 模型回答文字 |
| `session_id` | 当前会话名称 |
| `request_id` | 本地请求 ID，可用于查找调用记录 |

`print(reply)` 等价于打印回答文字。客户端等待完整回答后一次性返回。成功问答都会保存；失败、取消和未完成响应不写入历史，也不推进续接标识。

```python
from ccask import Ask, CCAskError, ConnectionError

try:
    with Ask("记忆测试", default_memory=True, session_id="实验 A") as bot:
        print(bot.ask("你好").text)
except ConnectionError as exc:
    print("本地服务连接失败：", exc)
except CCAskError as exc:
    print(exc.code, exc.status, str(exc))
```

`ConnectionError` 是 `CCAskError` 的子类，应先捕获。本地路径错误也可能抛出 `FileNotFoundError` 等 Python 文件异常。

| 错误码 | 处理 |
| --- | --- |
| `invalid_memory` / `invalid_default_memory` | 使用合法轮数或布尔值 |
| `invalid_clear_scope` | 批量清除时明确指定一个范围 |
| `service_upgrade_required` | 先更新并重启 App 或源码服务 |
| `service_unavailable` | 检查本地服务、地址、端口和等待时间 |
| `project_not_found` | 检查项目名及归档状态 |
| `session_not_found` | 会话已删除，重新创建 Ask |
| `sessions_busy` | 范围内请求完成后再批量清除 |
| `native_memory_unsupported` | 更换支持服务端续接的接口，或使用显式历史窗口 |
| `native_memory_expired` | 清空当前会话后重新开始 |
| `invalid_reasoning_effort` | 重新选择所选模型支持的思考档位 |
| `aggregation_off` | 在 CC Switch 开启 Codex 聚合模式 |
| `upstream_auth_failed` / `upstream_rate_limited` | 检查授权、额度或限流 |
| `model_unavailable` | 选择当前账号支持的模型 |
| `request_timeout` / `stream_interrupted` / `incomplete_response` | 查看调用记录和 CC Switch 日志，处理原因后重试 |

服务端上游超时默认 180 秒，由启动服务时的 `CCASK_TIMEOUT` 控制；客户端等待默认 240 秒，通过 `Ask(timeout=...)` 设置。客户端停止等待后服务端可能仍在执行，重试前先查看调用记录。

不使用 `with` 时应在结束时调用 `bot.close()`。默认数据库为 `~/.local/share/ccask/ccask.db`，可通过服务端环境变量 `CCASK_DATA_DIR` 更换目录。

## 11. 从旧版升级

先更新 App 或源码服务，再安装新版客户端。0.1.1/0.1.2 的数据库会先备份，再增加服务端续接字段，已有显式窗口和问答保留，`default_memory` 初始为 False。

原代码可继续使用 `memory=10`；希望只靠服务端续接时改成 `default_memory=True, memory=0`。`clear_memory()` 的行为已改为删除会话及名称，后续会话名称可能变化，请同步调整依赖固定名称的代码。

## 12. 本地 HTTP 接口

```text
POST /api/sessions
{"project":"记忆测试","default_memory":true,"memory":0,"session_id":"我的会话"}

PUT /api/sessions/{id}/memory
{"default_memory":false,"memory":3}

POST /api/sessions/{id}/ask
{"content":[{"type":"input_text","text":"你好"}]}

POST /api/sessions/{id}/clear

POST /api/sessions/clear
{"project":"记忆测试"}

POST /api/sessions/clear
{"all_projects":true}
```

创建会话返回内部 `id`、名称 `name`、`memory_rounds`、`default_memory` 等。路径中的 `{id}` 使用内部 ID。修改记忆时可只提供一个参数，另一个保持原值；旧的 `{"enabled":true}` 开关兼容为显式窗口 10 轮。

清除接口返回 `cleared` 和 `deleted_sessions`。非法参数返回 HTTP 422，活动会话的批量清除返回 HTTP 409。图片可通过 `ccask.client.image_content()` 转换为接口要求的 data URL。
