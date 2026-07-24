\# AI Prompt 与问题解决记录



\## 1. 文档说明



本项目在开发过程中使用了 AI 工具辅助完成需求拆解、方案比较、代码审查、错误定位和测试设计。



AI 主要承担以下角色：



\* 帮助拆解笔试要求

\* 提供不同技术方案供比较

\* 辅助生成初始代码框架

\* 分析报错原因

\* 补充测试边界

\* 检查设计是否满足题目要求

\* 整理 README 和开发记录



核心 Agent Runtime、工具执行流程、Session 隔离、Context 管理和最终技术取舍，均在理解代码逻辑后完成，并通过自动化测试和真实 LLM API 验证。



本项目没有使用 LangGraph、OpenHands、OpenClaw 等 Agent 框架完成主流程。



\---



\## 2. 使用 AI 的基本原则



开发过程中遵循以下原则：



1\. 不让 AI 直接替代对 Agent Runtime 的理解。

2\. AI 给出代码后，需要阅读代码并理解模块职责。

3\. 对安全相关实现补充单元测试。

4\. 对报错先分析原因，再修改代码。

5\. 对多个方案进行比较，而不是直接采用第一个答案。

6\. 不向 AI 提供真实 API Key。

7\. 最终以本地测试和真实运行结果作为判断依据。



\---



\## 3. 问题一：如何拆解最小可用 Agent



\### 遇到的问题



题目同时要求实现：



\* Agent Loop

\* 三个工具

\* 工具注册机制

\* LLM 输出解析

\* Session 隔离

\* Context 管理

\* Context 压缩

\* 异常处理

\* Trace

\* 测试用例

\* 真实 LLM API



如果一开始直接接入真实模型，工具、网络、Prompt 和 Runtime 问题会混在一起，难以定位。



\### 使用的 AI Prompt



```text

请把“从零实现一个最小可用 Agent”的题目拆成多个可独立测试的开发阶段。

不能使用现有 Agent 框架，核心 Agent Runtime 必须自行实现。

```



\### AI 提供的建议



AI 建议将项目拆成以下阶段：



1\. 工具基类和注册中心

2\. Calculator、Search 和 Todo

3\. FakeLLM 与输出解析器

4\. Agent Loop

5\. Session 持久化

6\. Context 管理和压缩

7\. Trace

8\. 真实 LLM API

9\. CLI 和端到端验证



\### 最终方案



采用分层开发方式，先使用 FakeLLM 验证 Runtime，再接真实 API。



\### 选择原因



这种方式能够将问题分离：



\* FakeLLM 阶段只验证 Runtime

\* 工具单元测试只验证工具行为

\* 真实 API 阶段只验证网络和模型输出

\* Session 测试只验证隔离和恢复

\* Context 测试只验证压缩逻辑



\### 验证方式



每完成一个阶段就运行对应测试，最后运行全量测试。



最终全量测试结果：



```text

74 passed

```



\---



\## 4. 问题二：如何设计工具注册机制



\### 遇到的问题



题目要求每个工具包含：



\* 名称

\* 描述

\* 参数 Schema



并且 LLM 必须基于 Schema 自主决定工具调用。



\### 使用的 AI Prompt



```text

如何设计一个不依赖 Agent 框架的 Tool Registry？

每个工具需要包含 name、description 和参数 Schema，

并且能够统一执行和处理异常。

```



\### 方案比较



AI 提供了以下候选方案：



1\. 每个工具使用普通字典描述

2\. 使用装饰器注册函数

3\. 使用 BaseTool 抽象类和 Registry

4\. 使用 Pydantic 模型定义参数



\### 最终方案



采用：



```text

BaseTool

\+ ToolArguments

\+ ToolRegistry

\+ ToolResult

```



每个工具通过 Pydantic 参数模型自动生成 JSON Schema。



\### 选择原因



\* 工具接口统一

\* 参数校验集中

\* Schema 可以直接提供给 LLM

\* 工具异常可以统一包装

\* 后续增加工具不需要修改 Agent Runtime



\### 验证方式



测试覆盖：



\* 正常注册

\* 重复工具名

\* 工具列表

\* Schema 生成

\* 未知工具

\* 参数错误

\* 工具执行异常



\---



\## 5. 问题三：Calculator 为什么不能使用 eval



\### 遇到的问题



最简单的计算器实现是：



```python

eval(expression)

```



但表达式来自 LLM 输出，属于不可信输入。



\### 使用的 AI Prompt



```text

LLM 会生成 calculator 的 expression 参数。

直接使用 eval 有什么风险？

如何实现一个只支持基本数学运算的安全计算器？

```



\### 风险分析



`eval` 不仅可以计算数学表达式，也可以执行任意 Python 代码。



例如恶意输入可能尝试：



```python

\_\_import\_\_("os").system("command")

```



因此直接使用 `eval` 会造成任意代码执行风险。



\### 最终方案



使用 Python AST 解析表达式，只允许以下节点：



\* 数字常量

\* 加法

\* 减法

\* 乘法

\* 除法

\* 整除

\* 取模

\* 幂运算

\* 一元正负号

\* 括号



拒绝：



\* 函数调用

\* 模块导入

\* 变量名

\* 属性访问

\* 布尔值

\* 超大指数

\* 过于复杂的 AST

\* 超出范围的结果



\### 验证方式



测试覆盖：



\* 运算优先级

\* 括号

\* 浮点结果

\* 一元负号

\* 除零

\* 函数调用

\* 变量访问

\* 超大指数

\* 多余参数

\* 空表达式



\---



\## 6. 问题四：如何解析 LLM 输出



\### 遇到的问题



虽然 System Prompt 要求模型只输出 JSON，但真实模型可能返回：



\* 纯 JSON

\* Markdown 代码块

\* JSON 前后带解释

\* 缺少字段

\* 多余字段

\* 非法工具名

\* 完全不符合格式的文本



\### 使用的 AI Prompt



```text

如何实现一个健壮的 LLM 输出解析器？

需要支持纯 JSON、Markdown JSON 代码块和前后混有文本的情况。

```



\### 最终方案



实现独立的 `ResponseParser`：



1\. 尝试解析完整字符串

2\. 提取 Markdown 代码块

3\. 从混合文本中寻找第一个合法 JSON 对象

4\. 使用 Pydantic 验证决策类型

5\. 区分 `tool\_call` 和 `final`



\### 输出协议



工具调用：



```json

{

&#x20; "type": "tool\_call",

&#x20; "reason": "需要计算",

&#x20; "tool\_name": "calculator",

&#x20; "arguments": {

&#x20;   "expression": "6 \* 7"

&#x20; }

}

```



最终回答：



```json

{

&#x20; "type": "final",

&#x20; "reason": "已经获得结果",

&#x20; "answer": "结果是 42。"

}

```



\### 异常恢复



如果解析失败，Runtime 不立即退出，而是把格式错误反馈给 LLM，要求模型下一轮重新输出合法 JSON。



\### 验证方式



测试覆盖：



\* 纯 JSON

\* JSON 代码块

\* 混合文本

\* 空输出

\* 无 JSON

\* 未知决策类型

\* 多余字段



\---



\## 7. 问题五：为什么先使用 FakeLLM



\### 遇到的问题



如果一开始使用真实 API，可能同时遇到：



\* 网络失败

\* API 配置错误

\* 模型输出格式不稳定

\* Agent Loop 错误

\* 工具调用错误



难以判断问题属于哪一层。



\### 使用的 AI Prompt



```text

在接入真实 LLM API 前，如何验证 Agent Loop 自身是正确的？

```



\### 最终方案



实现 `FakeLLMClient`，按照预设顺序返回模型响应。



例如：



```text

第 1 次返回 calculator 工具调用

第 2 次返回 todo 工具调用

第 3 次返回 final

```



\### 选择原因



能够稳定测试：



\* 直接回答

\* 单工具调用

\* 多工具调用

\* 工具错误恢复

\* 模型格式错误恢复

\* 最大循环次数

\* 工具结果是否进入下一轮 Context



\### 验证方式



Agent Loop 相关测试全部使用 FakeLLM，不消耗真实 API 额度。



\---



\## 8. 问题六：Python 循环导入



\### 遇到的现象



运行测试时出现：



```text

ImportError: cannot import name 'BaseLLMClient'

from partially initialized module

```



\### 原因分析



导入关系形成循环：



```text

llm.base

→ runtime.models

→ runtime.\_\_init\_\_

→ runtime.agent

→ llm.base

```



`runtime/\_\_init\_\_.py` 在加载数据模型时提前导入了 `agent.py`，而 `agent.py` 又依赖 `llm.base`。



\### 使用的 AI Prompt



```text

Python 出现 partially initialized module 和 circular import，

当前 llm.base 会导入 runtime.models，

runtime.\_\_init\_\_ 又会导入 runtime.agent，应该如何处理？

```



\### 最终方案



在 `runtime/\_\_init\_\_.py` 中使用延迟导入。



只有真正访问 `AgentRuntime` 时，才导入 `runtime.agent`。



\### 选择原因



\* 保留原有导入方式

\* 不需要大范围修改模块结构

\* 能够切断初始化阶段的循环依赖



\### 验证方式



运行：



```powershell

python -c "from minimal\_agent.llm.fake import FakeLLMClient; from minimal\_agent.runtime import AgentRuntime; print('imports ok')"

```



并重新运行 Agent Loop 测试。



\---



\## 9. 问题七：Session 如何隔离



\### 遇到的问题



题目要求同一用户的两个聊天窗口相互独立：



```text

用户 A / 窗口 1

用户 A / 窗口 2

```



两个窗口需要分别保存历史和 Todo。



\### 使用的 AI Prompt



```text

如何设计一个基于 SQLite 的 SessionStore，

让同一个用户的多个窗口相互隔离，

并且程序重启后能够继续聊天？

```



\### 最终方案



使用复合键：



```text

user\_id + session\_id

```



数据库包含：



\* `sessions`

\* `messages`

\* `todos`



每次读取和修改都必须同时使用 `user\_id` 和 `session\_id`。



\### 选择原因



\* 结构简单

\* 可以持久化

\* 适合 CLI Demo

\* 可以验证用户隔离和窗口隔离

\* 不需要引入额外数据库服务



\### 验证方式



测试覆盖：



\* 同 Session 历史恢复

\* 不同 Session 隔离

\* 不同用户隔离

\* 程序重启恢复

\* 跨 Session Todo 修改失败

\* 清空 Session



真实 API 演示中也验证了：



\* 相同 Session 重启后仍能记住用户信息

\* 新 Session 不会获得旧 Session 的历史和 Todo



\---



\## 10. 问题八：Context 过长如何处理



\### 遇到的问题



持续聊天时，如果每轮都加载全部历史，Context 会不断增长。



这会导致：



\* Token 成本增加

\* 响应延迟增加

\* 接近模型上下文上限

\* 旧信息干扰当前任务



\### 使用的 AI Prompt



```text

一个最小 Agent 如何实现基础 Context 压缩？

需要保留最近对话，同时让模型知道更早的关键信息。

```



\### 方案比较



候选方案包括：



1\. 只保留最近 N 条消息

2\. 删除所有工具结果

3\. 使用规则式摘要

4\. 使用额外 LLM 生成摘要

5\. 向量化历史消息



\### 最终方案



当前版本使用：



```text

历史摘要

\+ 最近若干条原始消息

\+ 当前用户输入

```



使用近似 Token 估算判断是否超过预算。



超过预算后：



1\. 选择需要保留的近期消息

2\. 将更早消息压缩为摘要

3\. 把摘要保存到 `sessions.summary`

4\. 删除已经被摘要覆盖的旧消息

5\. 下一轮重新注入摘要



\### 选择原因



规则式摘要：



\* 不增加额外 API 成本

\* 测试行为稳定

\* 适合作为笔试中的基础压缩方案

\* 后续可以替换为 LLM Summarizer



\### 验证方式



测试覆盖：



\* 未超预算时不压缩

\* 超预算后生成摘要

\* 保留最近消息

\* 注入已有摘要

\* 删除已压缩旧消息

\* Agent 能收到压缩摘要



\---



\## 11. 问题九：Trace 如何设计



\### 遇到的问题



题目要求工具调用 Trace 或执行日志。



仅使用普通文本日志无法方便地分析每次 Agent Run 的完整流程。



\### 使用的 AI Prompt



```text

如何为 Agent Runtime 设计结构化 Trace？

需要记录 LLM 请求、模型输出、工具调用、工具结果和最终答案。

```



\### 最终方案



每次 Agent Run 生成独立 JSONL 文件。



记录事件包括：



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



每条记录包含：



\* 时间

\* run\_id

\* user\_id

\* session\_id

\* event

\* step

\* payload



\### 设计取舍



Trace 写入失败不能中断 Agent 主流程。



因此 Trace 属于辅助能力，写入异常会被捕获。



过长文本会被自动截断，避免日志无限增长。



\### 验证方式



测试覆盖：



\* JSONL 文件生成

\* 独立 Run 使用独立文件

\* 文本截断

\* 直接回答 Trace

\* 工具调用 Trace



\---



\## 12. 问题十：Windows 应用控制策略阻止 pytest.exe



\### 遇到的现象



运行：



```powershell

pytest -v

```



出现：



```text

应用程序控制策略已阻止此文件

```



\### 原因分析



被拦截的是虚拟环境中的 `pytest.exe` 启动器，而不是 pytest Python 模块。



\### 使用的 AI Prompt



```text

Windows 应用控制策略阻止 .venv 中的 pytest.exe，

但虚拟环境已经正常激活，如何继续运行测试？

```



\### 最终方案



改用：



```powershell

python -m pytest -v

```



或：



```powershell

.\\.venv\\Scripts\\python.exe -m pytest -v

```



\### 选择原因



这种方式直接通过 Python 模块启动 pytest，不依赖被系统策略拦截的 exe 启动器，也不需要修改 Windows 安全策略。



\### 验证方式



最终通过该命令完成 74 项测试。



\---



\## 13. 问题十一：Tab 和空格混用



\### 遇到的现象



运行测试时出现：



```text

TabError: inconsistent use of tabs and spaces in indentation

```



\### 原因分析



使用记事本编辑代码时，某些行使用了 Tab，其他行使用了空格。



\### 使用的 AI Prompt



```text

Python 报 TabError，如何定位并将整个文件统一转换为四空格缩进？

```



\### 最终方案



使用 PowerShell 将 Tab 替换为四个空格：



```powershell

$content = Get-Content src\\minimal\_agent\\runtime\\agent.py -Raw

$content = $content.Replace("`t", "    ")

Set-Content src\\minimal\_agent\\runtime\\agent.py -Value $content -Encoding utf8

```



随后使用：



```powershell

python -m py\_compile src\\minimal\_agent\\runtime\\agent.py

```



进行语法检查。



\### 验证方式



重新运行 Context 和全量测试，全部通过。



\---



\## 14. 问题十二：真实 API 出现 SSL EOF



\### 遇到的现象



真实聊天过程中出现：



```text

SSL: UNEXPECTED\_EOF\_WHILE\_READING

```



\### 原因分析



TLS 连接被服务端、代理或中间网络提前关闭。



该错误属于网络层偶发错误，不是 Agent Loop 或工具逻辑错误。



\### 使用的 AI Prompt



```text

httpx 调用 OpenAI-compatible API 时偶发 SSL EOF，

应该在哪一层增加重试？

哪些错误适合重试？

```



\### 最终方案



在 LLM Client 层增加有限次数的指数退避重试。



只对以下类型的网络异常进行重试：



\* Timeout

\* NetworkError

\* RemoteProtocolError



不对所有业务错误和 HTTP 状态码进行盲目重试。



\### 选择原因



\* Runtime 不需要感知底层网络细节

\* 网络抖动可以自动恢复

\* 避免无限重试

\* 避免对参数错误或认证错误重复请求



\---



\## 15. 问题十三：模型错误声称无法记住用户信息



\### 遇到的现象



SessionStore 已经保存历史，但模型回答：



```text

我没有记忆功能，无法持久化保存用户称呼。

```



\### 原因分析



模型只看到 calculator、search 和 todo 三个工具，因此错误地认为：



```text

没有 memory 工具

= 没有记忆能力

```



但本项目的 Session Memory 由 Runtime 在每轮请求前自动加载，不需要 memory 工具。



\### 使用的 AI Prompt



```text

Session 历史已经持久化并重新注入 Context，

但模型仍声称没有记忆能力。

应该如何修改 System Prompt？

```



\### 最终方案



在 System Prompt 中明确说明：



1\. 当前对话属于持久化 Session。

2\. 后续轮次会重新提供当前 Session 的历史。

3\. 用户名字、偏好和任务状态可以从历史中继续使用。

4\. 不要因为不存在 memory 工具就声称没有 Session 记忆。

5\. 不同 Session 之间相互隔离。

6\. 最近消息和旧摘要冲突时，以最近消息为准。



\### 验证方式



真实聊天验证：



```text

用户：我叫小明，请记住。

用户：我叫什么？

Agent：你叫小明。

```



退出程序并重新启动相同 Session 后再次询问，Agent 仍能恢复用户信息。



\---



\## 16. 真实 API 端到端验证



真实 API 验证了以下流程：



\### 直接回答



```text

用户输入

→ LLM 返回 final

→ Runtime 输出答案

```



\### Calculator



```text

用户要求计算

→ LLM 调用 calculator

→ 工具返回结果

→ LLM 生成最终答案

```



\### 多工具调用



```text

用户要求计算并记录待办

→ calculator

→ todo

→ final

```



\### Search



```text

用户查询 Agent Runtime

→ search

→ 返回相关文档

→ LLM 整理答案

```



\### Session 恢复



```text

用户提供名字

→ 退出程序

→ 重新进入相同 Session

→ Agent 能回答用户名字

```



\### Session 隔离



```text

window-1 保存名字和待办

window-2 无法读取 window-1 的内容

```



\### Trace



每次运行都会生成 JSONL Trace，能够查看完整的模型与工具调用过程。



\---



\## 17. AI 生成内容的人工检查



AI 给出的代码和方案没有直接无条件采用，主要进行了以下人工检查：



\* 检查工具参数 Schema

\* 检查 Calculator 安全边界

\* 检查 Session SQL 是否包含 `user\_id + session\_id`

\* 检查 Context 压缩是否会重复摘要

\* 检查 Trace 是否影响主流程

\* 检查真实 API Key 是否被 `.gitignore` 忽略

\* 检查模型输出解析是否能恢复

\* 检查所有模块是否有测试

\* 使用真实 API 进行端到端验证



\---



\## 18. 最终结果



项目最终实现：



\* 自研 Agent Runtime

\* 真实 OpenAI-compatible LLM API

\* Calculator、Search、Todo 三个工具

\* Tool Registry 和参数 Schema

\* JSON 决策协议

\* 多工具连续调用

\* Session 持久化

\* 多窗口隔离

\* 对话追问

\* Context 压缩

\* JSONL Trace

\* CLI

\* 异常处理

\* 自动化测试



最终测试结果：



```text

74 passed

```



完整测试结果见：



```text

docs/test-results.txt

```



