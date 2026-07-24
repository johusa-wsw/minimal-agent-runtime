\# Minimal Agent Runtime



一个不依赖 LangGraph、OpenHands、OpenClaw 等现有 Agent 框架，从零实现的最小可用 Agent Runtime。



项目通过真实的 OpenAI-compatible LLM API 完成模型决策，并自行实现：



\* Agent 循环

\* 模型输出解析

\* 工具注册与执行

\* 多 Session 隔离

\* 对话历史持久化

\* Context 长度管理与基础压缩

\* 工具调用 Trace

\* 异常处理

\* CLI 交互

\* 自动化测试



\---



\## 1. 项目目标



本项目实现如下 Agent Loop：



```text

接收用户输入

&#x20;   ↓

加载当前 Session 的历史与摘要

&#x20;   ↓

调用 LLM 判断直接回答还是调用工具

&#x20;   ↓

解析 LLM 输出

&#x20;   ↓

直接回答 ─────────────────────→ 返回用户

&#x20;   ↓

调用工具

&#x20;   ↓

把工具结果重新放入 Context

&#x20;   ↓

再次调用 LLM

&#x20;   ↓

继续调用工具或返回最终答案

```



示例：



```text

用户：

请计算 238 × 17，并把结果加入待办。



Agent 第 1 轮：

调用 calculator(expression="238 \* 17")



工具结果：

4046



Agent 第 2 轮：

调用 todo(action="add", content="238 \* 17 = 4046")



工具结果：

待办创建成功



Agent 第 3 轮：

结果是 4046，已经记录到待办事项中。

```



Agent 是否调用工具、调用哪个工具以及传入什么参数，均由 LLM 根据工具 Schema 自主决定。



\---



\## 2. 核心功能



\### 2.1 自研 Agent Runtime



项目没有使用现有 Agent 框架管理主流程。



以下能力均由本项目自行实现：



\* Agent 最大循环轮次控制

\* LLM 调用

\* LLM 输出 JSON 解析

\* Tool Call 提取

\* 工具参数校验

\* 工具执行

\* 工具结果回填

\* 最终答案判断

\* Session 历史加载与保存

\* Context 压缩

\* Trace 日志记录



核心循环位于：



```text

src/minimal\_agent/runtime/agent.py

```



\---



\### 2.2 结构化 LLM 输出协议



本项目没有依赖模型供应商的原生 Function Calling 主流程，而是定义了统一的 JSON 决策协议。



调用工具时，模型需要输出：



```json

{

&#x20; "type": "tool\_call",

&#x20; "reason": "需要先计算表达式",

&#x20; "tool\_name": "calculator",

&#x20; "arguments": {

&#x20;   "expression": "238 \* 17"

&#x20; }

}

```



返回最终答案时，模型需要输出：



```json

{

&#x20; "type": "final",

&#x20; "reason": "工具执行已经完成",

&#x20; "answer": "238 × 17 等于 4046。"

}

```



`reason` 只保存简短的决策依据，不要求模型暴露完整思维链。



解析器支持：



\* 纯 JSON

\* Markdown JSON 代码块

\* JSON 前后存在额外文本

\* 字段缺失检测

\* 未知决策类型检测

\* 多余字段检测

\* 非法工具参数检测



当模型输出无法解析时，Runtime 会把错误反馈给模型，让模型在下一轮重新输出合法 JSON。



\---



\## 3. 系统架构



```mermaid

flowchart TD

&#x20;   U\[User Input] --> S\[SessionStore]

&#x20;   S --> C\[ContextManager]

&#x20;   C --> L\[LLM Client]

&#x20;   L --> P\[ResponseParser]



&#x20;   P -->|final| A\[Final Answer]

&#x20;   P -->|tool\_call| R\[ToolRegistry]



&#x20;   R --> CAL\[Calculator]

&#x20;   R --> SEA\[Mock Search]

&#x20;   R --> TODO\[Todo]



&#x20;   CAL --> TR\[Tool Result]

&#x20;   SEA --> TR

&#x20;   TODO --> TR



&#x20;   TR --> L



&#x20;   L --> TRACE\[JSONL Trace]

&#x20;   R --> TRACE

&#x20;   A --> TRACE

&#x20;   A --> S

```



各模块职责：



| 模块                 | 职责                         |

| ------------------ | -------------------------- |

| `AgentRuntime`     | 管理 LLM、工具调用和最大循环次数         |

| `ResponseParser`   | 将 LLM 文本解析为结构化决策           |

| `ToolRegistry`     | 注册工具、暴露 Schema、执行工具        |

| `SessionStore`     | 保存 Session、消息和摘要           |

| `ContextManager`   | 构建上下文并压缩旧消息                |

| `LLMClient`        | 请求真实 OpenAI-compatible API |

| `JSONLTraceWriter` | 保存每次执行的结构化日志               |

| `CLI`              | 提供单次执行和多轮聊天入口              |



\---



\## 4. 工具系统



每个工具都包含：



\* 工具名称

\* 工具描述

\* 参数 Schema

\* 参数校验逻辑

\* 工具执行逻辑



工具通过统一的 `BaseTool` 接口实现，并注册到 `ToolRegistry`。



\### 4.1 Calculator



支持：



\* 加法

\* 减法

\* 乘法

\* 除法

\* 整除

\* 取模

\* 幂

\* 括号

\* 一元正负号



示例：



```text

请计算 (2 + 3) \* 4

```



安全性设计：



计算器没有直接使用 Python `eval()`，而是通过 AST 白名单解析表达式。



只允许数字和有限的数学运算节点，禁止：



\* 函数调用

\* 模块导入

\* 属性访问

\* 变量读取

\* 任意 Python 代码执行

\* 过大的指数

\* 超出限制的计算结果



\---



\### 4.2 Search



Search 是一个本地 Mock 搜索工具，数据位于：



```text

data/mock\_search.json

```



支持：



\* 关键词搜索

\* 中英文内容匹配

\* 简单相关性评分

\* `top\_k` 数量限制

\* 结构化搜索结果



当前知识库包含：



\* Agent Runtime

\* Tool Calling

\* Session

\* Context

\* Memory



Search 使用 Mock 数据的原因是，本题重点在于 Agent Runtime、工具 Schema 和工具调用流程，而不是外部搜索引擎的实现。



\---



\### 4.3 Todo



Todo 支持：



\* `add`：添加待办

\* `list`：查看待办

\* `complete`：完成待办

\* `delete`：删除待办



Todo 数据保存到 SQLite。



每条待办都绑定：



```text

user\_id + session\_id

```



因此，同一用户的不同聊天窗口拥有彼此独立的待办列表。



例如：



```text

user-a / window-1

user-a / window-2

```



`window-1` 无法查看、完成或删除 `window-2` 的待办。



\---



\## 5. Session 管理



Session 使用以下复合键唯一标识：



```text

user\_id + session\_id

```



例如：



```text

user\_id = user-a

session\_id = window-1

```



同一个用户可以拥有多个独立聊天窗口：



```text

user-a / window-1

user-a / window-2

```



两个窗口分别保存：



\* 用户输入

\* Agent 最终回答

\* 工具调用决策

\* 工具执行结果

\* Session 摘要

\* Todo 数据



不同 Session 之间不会共享历史消息和待办。



程序退出后，再使用相同的 `user\_id` 和 `session\_id` 启动，仍然可以恢复之前的对话。



\---



\## 6. Context 管理



\### 6.1 Context 内容



每次调用 LLM 前，Context 主要包含：



1\. System Prompt

2\. 当前 Session 的历史摘要

3\. 最近的原始对话消息

4\. 当前用户输入

5\. 必要的工具调用和工具结果

6\. 当前可用工具的 Schema



不会长期无差别保存和传入所有中间信息。



\---



\### 6.2 保留的信息



长期历史中保留：



\* 用户输入

\* Agent 最终回答

\* 工具名称

\* 工具必要参数

\* 精简后的工具结果

\* 历史摘要

\* 当前任务状态



不优先长期保留：



\* 重复的 System Prompt

\* 每轮完整推理过程

\* 大段无关搜索结果

\* 完整异常堆栈

\* 重复工具 Schema



\---



\### 6.3 Context 压缩



当 Context 超过设定预算时，系统采用：



```text

旧消息 → 基础摘要

最近消息 → 保留原文

```



压缩后的 Context 结构：



```text

System Prompt

\+ 更早对话摘要

\+ 最近若干条原始消息

\+ 当前用户输入

```



当前版本使用规则式摘要器，不额外调用 LLM，因此：



\* 行为稳定

\* 没有额外 API 成本

\* 测试结果可复现

\* 摘要失败不会影响主 Agent 流程



摘要器通过统一接口实现，后续可以替换为 LLM 摘要器，而不需要修改 `ContextManager` 的主结构。



\---



\## 7. Memory 的召回时机与放置方式



本项目中的 Memory 分为两类。



\### 7.1 Session Memory



Session Memory 包含：



\* 当前窗口的历史消息

\* 用户在当前窗口提供的名字和偏好

\* 当前任务状态

\* 工具调用结果

\* 历史摘要



召回时机：



```text

每次 Agent Run 开始时

```



Runtime 会先根据：



```text

user\_id + session\_id

```



从 SQLite 加载当前 Session 的消息和摘要。



放置方式：



```text

System Prompt

→ Session 摘要

→ 最近原始消息

→ 当前用户输入

```



如果摘要和最近原始消息存在冲突，以最近消息为准。



\---



\### 7.2 Tool State



Todo 不直接混入普通对话 Memory，而是保存在独立的 SQLite 表中。



召回时机：



```text

只有当 LLM 决定调用 todo 工具时

```



这样可以避免每一轮都把完整 Todo 列表放进 Context，减少无关信息和 Token 消耗。



\---



\### 7.3 当前 Memory 边界



当前版本只支持 Session 级记忆：



\* 同一 Session 可以持续记住

\* 程序重启后仍能恢复

\* 不同 Session 彼此隔离

\* 不同用户彼此隔离



当前未实现跨 Session 的长期用户画像和语义向量检索。



\---



\## 8. Trace 执行日志



每次 Agent Run 都会创建独立的 JSONL 文件：



```text

traces/

└── 20260724T091845\_user-a\_window-1\_xxxxxxxx.jsonl

```



可能记录的事件包括：



```text

run\_started

context\_loaded

llm\_request

llm\_response

response\_parse\_failed

tool\_call

tool\_result

final\_answer

max\_steps\_exceeded

```



示例：



```json

{"event":"run\_started","step":null,"payload":{"user\_input":"7乘8是多少？"}}

{"event":"llm\_request","step":1,"payload":{"message\_count":2}}

{"event":"llm\_response","step":1,"payload":{"raw\_output":"..."}}

{"event":"tool\_call","step":1,"payload":{"tool\_name":"calculator"}}

{"event":"tool\_result","step":1,"payload":{"success":true}}

{"event":"final\_answer","step":2,"payload":{"answer":"答案是56。"}}

```



Trace 的主要用途：



\* 调试模型决策

\* 检查工具参数

\* 分析工具执行错误

\* 查看每轮循环过程

\* 复现 Agent 行为

\* 为录屏和问题排查提供证据



为了避免 Trace 文件无限增大，过长文本会自动截断。



Trace 属于辅助能力。即使 Trace 写入失败，也不会中断 Agent 主流程。



\---



\## 9. 异常处理



项目实现了以下异常处理：



\### LLM 层



\* 请求超时

\* 网络连接异常

\* HTTP 状态码错误

\* 返回内容不是 JSON

\* 返回内容缺少 `choices`

\* 返回内容缺少消息文本

\* API 配置缺失



\### Parser 层



\* 空输出

\* 找不到 JSON

\* 非法决策类型

\* 字段缺失

\* 多余字段

\* 参数结构错误



\### Tool 层



\* 未注册工具

\* 工具参数校验失败

\* 工具内部可预期错误

\* 工具内部未知异常

\* Calculator 除零

\* Calculator 恶意表达式

\* Search 数据文件不存在

\* Todo 缺少 Session Context

\* 跨 Session 修改 Todo



\### Runtime 层



\* 空用户输入

\* 空用户 ID

\* 空 Session ID

\* 超出最大循环次数

\* LLM 调用失败



\---



\## 10. 项目目录



```text

minimal-agent/

├── README.md

├── pyproject.toml

├── .env.example

├── .gitignore

│

├── src/

│   └── minimal\_agent/

│       ├── cli.py

│       │

│       ├── runtime/

│       │   ├── agent.py

│       │   ├── models.py

│       │   └── parser.py

│       │

│       ├── llm/

│       │   ├── base.py

│       │   ├── fake.py

│       │   └── openai\_compatible.py

│       │

│       ├── tools/

│       │   ├── base.py

│       │   ├── registry.py

│       │   ├── factory.py

│       │   ├── calculator.py

│       │   ├── search.py

│       │   └── todo.py

│       │

│       ├── session/

│       │   └── store.py

│       │

│       ├── context/

│       │   ├── manager.py

│       │   └── summarizer.py

│       │

│       ├── tracing/

│       │   └── trace.py

│       │

│       └── prompts/

│           └── system\_prompt.py

│

├── data/

│   └── mock\_search.json

│

├── tests/

│   ├── test\_agent\_context.py

│   ├── test\_agent\_loop.py

│   ├── test\_agent\_session.py

│   ├── test\_agent\_trace.py

│   ├── test\_calculator.py

│   ├── test\_context.py

│   ├── test\_llm\_client.py

│   ├── test\_parser.py

│   ├── test\_registry.py

│   ├── test\_search.py

│   ├── test\_session.py

│   ├── test\_todo.py

│   ├── test\_tool\_factory.py

│   └── test\_trace.py

│

├── docs/

│   ├── AI\_PROMPTS\_AND\_PROBLEM\_SOLVING.md

│   └── test-results.txt

│

└── traces/

```



\---



\## 11. 环境要求



推荐环境：



```text

Python >= 3.11

```



本项目已在以下环境完成测试：



```text

Windows

Python 3.13.12

pytest 9.1.1

```



主要依赖：



\* `httpx`

\* `pydantic`

\* `python-dotenv`

\* `pytest`

\* `pytest-asyncio`



\---



\## 12. 安装方式



克隆项目：



```bash

git clone <YOUR\_REPOSITORY\_URL>

cd minimal-agent

```



创建虚拟环境：



\### Windows PowerShell



```powershell

python -m venv .venv

.\\.venv\\Scripts\\Activate.ps1

```



安装项目和开发依赖：



```powershell

python -m pip install -e ".\[dev]"

```



\---



\## 13. 环境变量配置



复制环境变量示例：



```powershell

Copy-Item .env.example .env

```



编辑 `.env`：



```dotenv

LLM\_API\_KEY=your-api-key

LLM\_BASE\_URL=https://your-provider.example/v1

LLM\_MODEL=your-model-name

LLM\_TIMEOUT\_SECONDS=60



AGENT\_DATABASE\_PATH=data/minimal\_agent.db

AGENT\_SEARCH\_DATA\_PATH=data/mock\_search.json

AGENT\_TRACES\_DIR=traces

AGENT\_MAX\_STEPS=8

```



说明：



\* `LLM\_BASE\_URL` 填写到 `/v1`

\* 不要在地址后重复添加 `/chat/completions`

\* `.env` 已加入 `.gitignore`

\* 不要把真实 API Key 提交到 Git



\---



\## 14. 运行方式



\### 14.1 查看帮助



```powershell

python -m minimal\_agent.cli --help

```



\### 14.2 单次请求



```powershell

python -m minimal\_agent.cli run `

&#x20; "请计算238乘17" `

&#x20; --user user-a `

&#x20; --session window-1 `

&#x20; --show-trace

```



\### 14.3 多轮聊天



```powershell

python -m minimal\_agent.cli chat `

&#x20; --user user-a `

&#x20; --session window-1 `

&#x20; --show-trace

```



CLI 命令：



```text

/exit       退出当前聊天

/quit       退出当前聊天

/history    查看当前 Session 的历史

/clear      清空当前 Session

```



\---



\## 15. Session 验证示例



\### 窗口一



```powershell

python -m minimal\_agent.cli chat `

&#x20; --user demo-user `

&#x20; --session window-1 `

&#x20; --show-trace

```



输入：



```text

我叫小明，请记住。

我叫什么？

请计算238乘17，并把结果加入待办。

查看我的待办。

```



退出后，重新启动相同 Session：



```powershell

python -m minimal\_agent.cli chat `

&#x20; --user demo-user `

&#x20; --session window-1 `

&#x20; --show-trace

```



再次输入：



```text

我叫什么？

查看我的待办。

```



Agent 应能恢复名字和待办。



\### 窗口二



```powershell

python -m minimal\_agent.cli chat `

&#x20; --user demo-user `

&#x20; --session window-2 `

&#x20; --show-trace

```



输入：



```text

我叫什么？

查看我的待办。

```



窗口二不应该读取到窗口一的名字和待办。



\---



\## 16. 自动化测试



运行全部测试：



```powershell

python -m pytest -v

```



当前测试结果：



```text

74 passed

```



覆盖范围包括：



\* Agent 直接回答

\* 单工具调用

\* 多工具连续调用

\* 未知工具恢复

\* 模型非法输出恢复

\* 最大轮次限制

\* Calculator 安全性

\* 工具注册和 Schema

\* Search 查询

\* Todo 增删改查

\* 用户隔离

\* Session 隔离

\* Session 重启恢复

\* 工具结果持久化

\* Context 压缩

\* 最近消息保留

\* 摘要注入

\* LLM HTTP 请求结构

\* LLM 异常响应

\* Trace 文件生成

\* Trace 文本截断



完整测试结果位于：



```text

docs/test-results.txt

```



\---



\## 17. 设计取舍



\### 为什么不使用 Agent 框架



本题重点是理解并实现 Agent Runtime，因此没有使用 LangGraph、OpenHands 或 OpenClaw 管理主流程。



\### 为什么使用自定义 JSON 工具协议



自定义协议可以清晰展示：



\* LLM 如何做决策

\* Runtime 如何解析决策

\* Runtime 如何执行工具

\* 工具结果如何进入下一轮

\* Parser 如何处理错误输出



\### 为什么 Search 使用 Mock



Search 的目标是验证工具注册、参数 Schema 和 Agent 调用流程，而不是实现完整搜索引擎。



\### 为什么 Todo 单独存储



Todo 是结构化业务状态，不适合每轮都塞入普通对话 Context。只有在模型调用 Todo 工具时，才从数据库读取。



\### 为什么先持久化用户输入



用户消息在 LLM 调用前写入数据库。



这样即使发生网络错误，用户输入也不会直接丢失。



代价是用户重新发送时，历史中可能出现重复消息。当前版本保留这一行为，并通过 Session 历史体现真实请求状态。



\---



\## 18. 已知限制



当前版本仍有以下限制：



1\. Search 使用本地 Mock 数据，不连接真实搜索引擎。

2\. Context 摘要使用规则式压缩，不具备复杂语义归纳能力。

3\. 当前 Memory 只在单个 Session 内生效。

4\. 尚未实现跨 Session 的长期用户画像。

5\. 尚未实现向量数据库和语义检索。

6\. 当前每轮只允许调用一个工具，多工具任务通过多轮 Loop 完成。

7\. 没有实现异步工具与后台任务。

8\. CLI 主要用于功能验证，尚未提供 Web UI。

9\. Token 数量采用近似估算，而不是特定模型的精确 tokenizer。

10\. Mock Search 的相关性算法较简单。



\---



\## 19. 后续改进方向



\* 接入真实搜索 API

\* 实现 LLM Summarizer

\* 增加长期 Memory 提取与召回

\* 增加向量语义检索

\* 实现异步工具

\* 实现任务状态机

\* 增加流式输出

\* 增加 Web UI

\* 增加更精确的 Token 统计

\* 对敏感 Trace 字段进行脱敏

\* 增加并发 Session 控制

\* 增加 LLM 调用指标和耗时统计

\* 增加失败请求重试与幂等控制



\---



\## 20. AI 辅助开发说明



项目开发过程中使用了 AI 工具辅助：



\* 拆解题目需求

\* 比较模块设计方案

\* 生成初始测试思路

\* 排查 Python 循环导入

\* 排查 Tab 与空格缩进问题

\* 分析 SSL 网络错误

\* 优化 Session Memory Prompt

\* 检查异常处理边界



核心 Agent Runtime、工具执行流程、Session 管理、Context 压缩和最终技术取舍均在理解代码行为后完成，并通过自动化测试和真实 API 演示进行验证。



详细记录见：



```text

docs/AI\_PROMPTS\_AND\_PROBLEM\_SOLVING.md

```



\---



\## 21. 演示视频



录屏地址：



```text

<YOUR\_DEMO\_VIDEO\_URL>

```



演示内容包括：



\* CLI 启动

\* 直接回答

\* Calculator 调用

\* 多工具连续调用

\* Search 调用

\* Todo 管理

\* Session 重启恢复

\* 多窗口隔离

\* Trace 查看

\* 自动化测试结果



\---



\## 22. License



本项目仅用于 Agent 技术笔试与学习演示。



\## 演示视频



\[查看 Minimal Agent Runtime 操作演示](替换为GitHub-Release中的视频附件链接)

