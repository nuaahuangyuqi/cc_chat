# CC Ask Python 客户端使用说明

适用版本：0.1.2。安装包名为 `ccask-client`，Python 导入名为 `ccask`。

## 1. 准备服务和项目

客户端通过本机 HTTP 服务调用模型。使用期间，CC Ask App（或源码网页服务）和 CC Switch 都需要运行。

1. 在 CC Switch 中配置 API 供应商，或登录 GPT 官方账号。
2. 开启 Codex 聚合模式、代理和请求日志。
3. 打开 CC Ask，在“连接管理”刷新连接。
4. 创建项目，例如“论文助手”，选择供应商、模型，并按需设置项目指令和模型参数。

项目名必须与 CC Ask 中的名字一致，也可使用项目 ID。供应商、模型、项目指令和生成参数由服务端的项目配置决定，客户端不需要填写密钥。GPT 模式使用 CC Switch 当前选中的官方账号。

独立客户端支持 Python 3.7+；源码服务需要 Python 3.12+。源码启动方式见 [网页端说明](web.md)，App 安装方式见 [macOS 说明](macos.md)。

## 2. 安装和升级

先启动 **0.1.2 或更新的 CC Ask 服务**，再在运行脚本的 Python 环境安装：

```sh
NO_PROXY=127.0.0.1,localhost python -m pip install --upgrade "http://127.0.0.1:8765/api/sdk/ccask_client-0.1.2-py3-none-any.whl"
```

也可以从 CC Ask 网页的“Python 调用”页复制安装命令。使用自定义端口时，安装地址也要相应修改。

检查客户端版本：

```sh
python -c "import ccask; print(ccask.__version__)"
```

建议为使用客户端的项目创建独立虚拟环境。`ccask` 源码包和 `ccask-client` 都提供同名的 `ccask` 模块，请使用不同环境，避免相互覆盖。

## 3. 最小示例

```python
from ccask import Ask

with Ask("论文助手") as bot:
    reply = bot.ask("给我三个多模态检索的研究方向")
    print(reply.text)
```

默认 `memory=0`，每次请求只发送当前问题和项目指令。成功问答仍保存在服务端本地数据库。

`with` 退出时会关闭客户端 HTTP 连接，数据库中的会话和历史会继续保留。

## 4. 构造参数

```python
Ask(
    project="论文助手",
    memory=10,
    session_id="多模态检索",
    base_url="http://127.0.0.1:8765",
    timeout=240,
)
```

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `project` | 必填 | CC Ask 项目名或项目 ID |
| `memory` | `0` | 每次请求带入的最近完整问答轮数；非负整数 |
| `session_id` | `None` | 会话名称；省略时自动生成一个新名称 |
| `base_url` | `CCASK_URL`，未设置时为 `http://127.0.0.1:8765` | 本机服务地址 |
| `timeout` | `240` | 客户端等待本地服务响应的超时秒数 |

`memory` 的有效整数范围为 `0` 至 `2147483647`，实际使用建议从 3～10 开始。负数、小数、字符串和 `None` 会报 `invalid_memory`。旧代码的 `True` 按 `10` 处理，`False` 按 `0` 处理。

`base_url` 目前仅支持 HTTP 和 `127.0.0.1`、`localhost`、`::1` 等本机地址。客户端调用会绕过系统 HTTP 代理环境变量。

## 5. 按轮数控制记忆

```python
from ccask import Ask

with Ask("论文助手", memory=2, session_id="研究讨论") as bot:
    bot.ask("我的方向是多模态检索")       # 第 1 轮
    bot.ask("我只有一张 24GB 显卡")      # 第 2 轮
    bot.ask("请推荐一个可行实验")         # 第 3 轮：带第 1、2 轮
    print(bot.ask("写出实验步骤").text)   # 第 4 轮：带第 2、3 轮
```

一轮是“一次用户提问 + 一次成功完成的助手回答”。`memory=2` 表示取**当前问题之前最近的 2 轮**，按时间顺序发送，然后追加当前问题；不足 2 轮时使用现有全部历史。

- `memory=0`：不带历史。
- `memory=1`：带最近 1 轮。
- `memory=10`：最多带最近 10 轮。
- 项目指令会随每次请求发送，不计入轮数。
- 历史用户图片属于对应轮次，随该轮一起带入；超出窗口后不再发送。
- 历史助手只回传可见回答，不回传旧的加密 reasoning 状态。
- 成功问答均保存；失败、取消或流式响应未完成的问答不写入历史。

轮数控制的是请求内容，数据库会保留全部成功问答。窗口满后旧轮次自动退出后续输入，不会被删除，也不会自动生成摘要。轮数不是 Token 上限：长回答和图片仍可能让有限轮次的请求很大。历史输入依然会产生相应 Token 用量，具体以供应商记录为准。

### 运行中调整、暂停和恢复

```python
with Ask("论文助手", memory=10, session_id="研究讨论") as bot:
    bot.ask("我正在比较两种检索方法")

    bot.set_memory(3)          # 后续最多带最近 3 轮
    bot.stop_memory()          # 等价于 set_memory(0)
    bot.ask("解释一下余弦相似度")  # 独立回答，但成功问答仍会保存

    bot.start_memory()         # 恢复这个客户端上次设置的正数：3
    print(bot.ask("结合刚才的内容继续分析").text)

    bot.start_memory(5)        # 也可以直接指定 5 轮
```

`start_memory()` 在客户端尚未设置过正数时默认开启 10 轮。暂停期间保存的问答，也会参与恢复后的最近 N 轮选择。`bot.memory` 可读取本客户端最近成功设置的轮数；调整时请调用方法，不要直接给这个属性赋值。

## 6. 跨脚本或跨进程恢复会话

相同项目和相同 `session_id` 会使用同一个服务端会话：

```python
# 第一次运行
with Ask("论文助手", memory=10, session_id="实验 A") as bot:
    bot.ask("数据集使用 MS COCO，先记录这个实验设定")

# 之后再次运行，可以在另一个进程中
with Ask("论文助手", memory=10, session_id="实验 A") as bot:
    print(bot.ask("基于之前的设定，建议哪些指标？").text)
```

每次创建 `Ask` 都会将这个会话的窗口设为传入的 `memory`，包括默认的 `0`。因此恢复记忆时要显式传入正数。同名会话的窗口设置由使用该会话的客户端共享；多个独立任务应使用不同 `session_id`。

不传 `session_id` 时，每次创建 `Ask` 都会创建新会话。可以通过 `bot.session_id` 或 `reply.session_id` 获得自动生成的名称，以便下次恢复。同名会话在不同项目之间互相独立。

服务端会顺序处理同一会话的提问、窗口调整和清空操作。不同会话可独立处理；Python 客户端本身提供同步接口。

## 7. 清空会话

```python
with Ask("论文助手", memory=10, session_id="实验 A") as bot:
    bot.clear_memory()
    print(bot.ask("开始一个新实验").text)
```

`clear_memory()` 会删除该会话全部已保存问答，而不仅是当前窗口内的部分。窗口设置继续生效，用量和请求记录仍保留。清空操作会排在同一会话正在执行的模型调用之后。

只想暂时独立回答时，使用 `stop_memory()`；需要彻底重新开始时，使用 `clear_memory()` 或新的 `session_id`。

## 8. 图片输入

```python
from pathlib import Path
from ccask import Ask

with Ask("论文助手", memory=2, session_id="图表分析") as bot:
    reply = bot.ask(
        "比较这两张图的实验结果",
        images=["figure-1.png", Path("figure-2.jpg")],
    )
    print(reply.text)

    raw = Path("figure-3.webp").read_bytes()
    print(bot.ask("这张图有什么异常？", images=[raw]).text)
```

`images` 是图片列表，每项支持本地路径字符串、`Path` 或原始 `bytes`。支持 PNG、JPEG、WebP；每张最多 20 MB，每次最多 20 张，总原始图片数据最多 40 MB。模型及供应商也需要支持图片输入。

文字参数每次最多 1,000,000 个字符。可以使用空字符串配合图片提问；文字和图片不能同时为空。

## 9. 返回值

`bot.ask()` 返回 `Reply`：

| 属性 | 内容 |
| --- | --- |
| `reply.text` | 模型回答文字 |
| `reply.session_id` | 会话名称，可用于之后恢复 |
| `reply.request_id` | 本地服务请求 ID，用于对应调用记录 |

`print(reply)` 与 `print(reply.text)` 都会打印回答。客户端会等模型完整返回后一次性给出结果。

## 10. 异常处理和关闭连接

```python
from ccask import Ask, CCAskError, ConnectionError

try:
    with Ask("论文助手", memory=3, session_id="实验 A") as bot:
        print(bot.ask("帮我设计实验").text)
except ConnectionError as exc:
    print("本地服务连接失败：", exc)
except CCAskError as exc:
    print("调用失败：", exc.code, exc.status, str(exc))
```

`ConnectionError` 是 `CCAskError` 的子类，所以应先捕获它。本地文件路径错误也可能抛出 `FileNotFoundError` 等 Python 文件异常。

| 常见错误码 | 处理方式 |
| --- | --- |
| `invalid_memory` | 将 memory 改为非负整数 |
| `service_upgrade_required` | 更新并重启 App 或本地服务，再使用新版客户端 |
| `service_unavailable` | 启动 CC Ask，检查地址、端口和客户端等待超时 |
| `project_not_found` | 检查项目名，确认项目已创建且未归档 |
| `aggregation_off` | 在 CC Switch 开启 Codex 聚合模式 |
| `upstream_auth_failed` | 检查 CC Switch 中的 API 授权或官方账号登录 |
| `upstream_rate_limited` | 检查供应商额度或等待速率限制解除 |
| `model_unavailable` | 刷新连接并选择当前账号支持的模型 |
| `request_timeout` | 检查上游耗时，按需调整服务端超时 |
| `stream_interrupted` / `incomplete_response` | 查看 CC Switch 请求日志，处理原因后重试 |

服务端默认上游超时为 180 秒，通过启动服务时的 `CCASK_TIMEOUT` 调整；客户端默认等待 240 秒，通过 `Ask(timeout=...)` 调整。客户端超时只表示停止等待，服务端可能仍在完成请求，重试前先查看调用记录。

不使用 `with` 时，请显式关闭客户端：

```python
bot = Ask("论文助手", memory=3)
try:
    print(bot.ask("你好").text)
finally:
    bot.close()
```

## 11. 服务地址和数据位置

自定义地址可显式传参：

```python
bot = Ask("论文助手", memory=3, base_url="http://127.0.0.1:8766")
```

也可通过环境变量 `CCASK_URL` 设置。显式 `base_url` 优先。

默认数据库为 `~/.local/share/ccask/ccask.db`，由 CC Ask 服务管理。可在启动服务前通过 `CCASK_DATA_DIR` 指定其他目录。历史文字和图片数据都会保存在该数据库中；备份时应将它作为包含个人数据的文件处理。

`clear_memory()` 清除当前数据库中的会话问答。迁移备份位于数据库目录的 `backups/`，其历史内容需单独管理。

## 12. 从 0.1.1 升级

1. 先更新并重启 CC Ask App 或源码服务到 0.1.2。
2. 在使用客户端的 Python 环境重新运行新版 wheel 安装命令。
3. 将原来的 `memory=True` 改写为需要的轮数，例如 `memory=10`。
4. 检查依赖暂停记忆的业务逻辑：现在暂停期间的成功问答也会保存，并可能在恢复记忆后进入窗口。

首次打开旧数据库时，服务会先创建迁移备份，再增加记忆轮数字段。原先开启记忆的会话迁移为 10 轮，关闭的迁移为 0 轮，已有问答继续保留。之后创建 `Ask` 时使用传入参数重新设置窗口。

旧的 `memory=True/False` 和旧客户端的记忆开关请求仍被新服务接受，分别映射成 10/0 轮。新版服务统一使用有上限的历史窗口。旧版本在关闭记忆期间未保存的问答无法恢复。

## 13. 本地 HTTP 接口

通常使用 Python 客户端即可。自行接入本地服务时，可使用：

```text
POST /api/sessions
{"project":"论文助手","memory":10,"session_id":"实验 A"}
```

返回对象包含内部 `id`、会话名称 `name`、`memory_rounds` 和兼容字段 `memory_enabled`。后续路径使用内部 `id`，不是会话名称。

```text
PUT /api/sessions/{id}/memory
{"memory":3}

POST /api/sessions/{id}/ask
{"content":[{"type":"input_text","text":"继续讨论"}]}

POST /api/sessions/{id}/clear
```

创建会话时 `memory` 默认 0；修改窗口时必须显式提供值。窗口参数错误返回 HTTP 422。图片内容使用 `input_image` 和 `image_url`，值为支持格式的 `data:image/...;base64,...`，可参考 `ccask.client.image_content()` 生成。
