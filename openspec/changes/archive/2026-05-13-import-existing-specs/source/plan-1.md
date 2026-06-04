# Deepy Python 迁移计划

本文基于当前 TypeScript/Ink 代码和现有迁移草案修订。目标不是重新设计一个更大的 agent 平台，而是把现有 `Deepy` 的核心能力迁移到 Python 项目中，并为后续高级功能保留边界。迁移应以 Python 项目体验、可维护性和用户可见行为为主；JavaScript 项目只作为参考，不要求逐项完全一致。

## 1. 迁移结论

当前仓库是一个单包 TypeScript CLI：

- 命令入口：`deepy -> dist/cli.js`
- 源码入口：`src/cli.tsx`
- 打包方式：`esbuild`
- 运行时：Node `>=18.17`
- UI：React + Ink
- LLM：OpenAI-compatible Chat Completions 接口，Python 版改用 `openai-agents` SDK 的 `OpenAIChatCompletionsModel`
- 核心状态：`~/.deepy/config.toml`、`~/.deepy/projects/<project-code>/sessions-index.json`、`<session-id>.jsonl`

Python 版第一阶段应保持核心外部契约稳定，同时允许对实现细节做 Python 化调整：

- 命令仍然叫 `deepy`
- 默认配置路径改为 `~/.deepy/config.toml`
- 会话索引和 JSONL 消息格式优先保持可读写
- 工具名称和参数 schema 保持不变
- 继续使用 OpenAI-compatible Chat Completions，但通过 `openai-agents` SDK 的 Chat Completions model shape 接入
- 继续支持 DeepSeek thinking 字段、`extra_body.reasoning_effort`、streaming、tool calls、usage 累加和 compaction
- 先不引入 MCP、subagent、SQLite、OAuth、Web UI、复杂 approval runtime

推荐迁移策略：先做 Python 项目骨架、TOML 配置和纯逻辑迁移，再迁移工具层，然后基于 `openai-agents` SDK 重建 agent loop 和 streaming，最后重建 TUI。迁移时优先保留用户依赖的行为和数据格式；内部实现、UI 组件树、测试组织和过时的 Node 分发逻辑可以按 Python 生态重写或裁剪。

## 2. 当前代码分析

### 2.1 项目结构

当前源码主要分为以下几层：

| 当前文件 | 主要职责 | 迁移风险 |
| --- | --- | --- |
| `src/cli.tsx` | CLI 参数、版本/帮助、TTY 检查、Windows shell 初始化、更新检查、Ink 启动 | 中 |
| `src/ui/App.tsx` | 主 TUI 状态机、消息列表、session list、busy/status、skills、pending question、退出摘要 | 高 |
| `src/ui/PromptInput.tsx` | 输入缓冲区、快捷键、slash menu、skills 选择、历史、图片粘贴、Ctrl+D/Esc | 高 |
| `src/session.ts` | session 创建/续聊、JSONL 存储、skills 注入、AGENTS.md 注入、OpenAI streaming、tool loop、compaction、interrupt、notify | 最高 |
| `src/prompt.ts` | system prompt、工具文档读取、runtime context、工具 schema、compact prompt | 高 |
| `src/settings.ts` | 解析 Python 版 `~/.deepy/config.toml`，处理 thinking 默认值和模型默认值 | 中 |
| `src/tools/*` | bash/read/write/edit/AskUserQuestion/WebSearch 执行、文件状态、安全约束、进程跟踪 | 最高 |
| `src/ui/*` | 消息渲染、markdown、session list、welcome、loading、exit summary | 中 |
| `src/tests/*` | 当前行为基线，是迁移验收来源 | 高 |

代码量集中在几个核心文件：

- `src/session.ts` 约 2078 行，是迁移中的核心拆分对象。
- `src/tools/edit-handler.ts` 约 865 行，包含读后编辑保护、snippet、候选匹配、模糊匹配、LLM 纠正 escape 的特殊逻辑。
- `src/tools/read-handler.ts` 约 685 行，包含文本、图片、PDF、notebook、gitignore/suffix 匹配和 snippet 元数据。
- `src/ui/PromptInput.tsx` 约 693 行，包含大部分交互快捷键。
- `src/prompt.ts` 约 623 行，包含 prompt、工具 schema 和 runtime context。

### 2.2 当前运行链路

启动链路：

```text
src/cli.tsx
  -> read package version
  -> --help / --version
  -> configureWindowsShell()
  -> TTY check
  -> promptForPendingUpdate()
  -> Ink render(<App />)
```

交互链路：

```text
App
  -> PromptInput collects PromptSubmission
  -> SessionManager.handleUserPrompt()
  -> createSession() or replySession()
  -> activateSession()
  -> OpenAI Chat Completions streaming
  -> parse assistant content/reasoning/tool_calls/usage
  -> ToolExecutor.executeToolCalls()
  -> append tool messages
  -> repeat until completed / waiting_for_user / failed / interrupted
```

存储链路：

```text
projectRoot
  -> projectCode = projectRoot.replace(/[\\/]/g, "-").replace(/:/g, "")
  -> ~/.deepy/projects/<projectCode>/sessions-index.json
  -> ~/.deepy/projects/<projectCode>/<sessionId>.jsonl
```

### 2.3 外部行为契约

这些行为应在 Python 版中作为兼容项保留；未被用户直接依赖的内部实现可以重写、合并或删除：

1. CLI
   - `deepy --help`
   - `deepy --version`
   - 无 TTY 时退出并提示需要交互终端
   - Windows 下需要 Git Bash 兼容路径

2. 配置
   - 主配置文件为 `~/.deepy/config.toml`
   - 使用 `tomllib` 读取 TOML；如 CLI 提供配置写入命令，使用 `tomli-w` 写回
   - 支持 Python 友好的 TOML 结构：
     - `[model] name/base_url/api_key/thinking/reasoning_effort`
     - `[logging] debug`
     - `[notify] enabled/command`
     - `[tools.web_search] command/api_url`
   - 默认模型：`deepseek-v4-pro`
   - 默认 base URL：`https://api.deepseek.com`
   - `deepseek-v4-flash`、`deepseek-v4-pro` 默认启用 thinking

3. Session
   - session index 版本仍为 `version: 1`
   - 最多保留 50 个 session entry
   - 每条消息 JSONL 一行
   - 允许读取旧格式：
     - 缺失 `activeTokens` 时补 `0`
     - 旧 `processes` 可以是 `{pid: startTime}` 形式
   - message 字段保持：
     - `id`
     - `sessionId`
     - `role`
     - `content`
     - `contentParams`
     - `messageParams`
     - `compacted`
     - `visible`
     - `createTime`
     - `updateTime`
     - `meta`

4. OpenAI-compatible Chat Completions
   - streaming 请求强制 `stream: true`
   - `stream_options.include_usage: true`
   - 聚合 `delta.content`
   - 聚合 `delta.reasoning_content` 或 `delta.reasoning`
   - 聚合 `delta.refusal`
   - 按 `tool_calls[index]` 合并流式 tool call 片段
   - replay assistant message 时在 thinking 模式下补空 `reasoning_content`
   - tool call 缺失对应 tool message 时插入 interrupted tool message
   - 对 DeepSeek thinking 使用：
     - `thinking: {"type": "enabled" | "disabled"}`
     - `extra_body.reasoning_effort: "high" | "max"`

5. Tools
   - 工具名保持：`bash`、`read`、`write`、`edit`、`AskUserQuestion`、`WebSearch`
   - tool result 保持 JSON 字符串结构：
     - `ok`
     - `name`
     - `output`
     - `error`
     - `metadata`
     - `awaitUserResponse`
   - `AskUserQuestion` 返回 `awaitUserResponse: true`，由 UI 继续接管用户回答
   - `read/write/edit` 必须保留读后写保护和 mtime 变更检测
   - `bash` 必须保留每个 session 的 cwd 记忆和进程跟踪
   - `WebSearch` 先调用用户配置脚本，否则走默认 Deepy web-search API

6. Skills 和项目规则
   - 用户 skills：`~/.agents/skills/<name>/SKILL.md`
   - 项目 skills：`./.deepy/skills/<name>/SKILL.md`
   - frontmatter 字段：`name`、`description`
   - 已加载 skill 通过 system message 的 `meta.skill` 标记
   - 自动匹配 skill 时调用模型返回 `{"skillNames": []}`
   - 默认注入 `agent-drift-guard` skill
   - 自动读取项目 `AGENTS.md` 或用户 `~/.deepy/AGENTS.md`

7. UI
   - 欢迎屏显示项目、配置、skills、版本
   - message view 区分 user/assistant/tool/system
   - assistant tool call thinking 默认折叠
   - tool diff preview 只对成功的 `edit/write` 显示
   - slash commands：
     - `/new`
     - `/resume`
     - `/skills`
     - `/exit`
     - skill item
   - 快捷键：
     - Enter 发送
     - Shift+Enter 或 Ctrl+J 换行
     - Esc 中断
     - Ctrl+C 清空输入或中断
     - Ctrl+D 双击退出
     - Ctrl+V 粘贴图片
     - Ctrl+X 清空图片
     - Ctrl+W 删除前一个词
     - 上下方向键浏览历史或移动光标

### 2.4 迁移边界和裁剪原则

迁移不是把 TypeScript 代码逐行翻译成 Python。必须先区分三类内容：

1. 必须迁移
   - CLI 名称、核心命令、配置语义、session 可读写能力
   - Chat Completions streaming、DeepSeek thinking、tool calls、usage 累加
   - 工具协议、读后写保护、mtime 检测、session cwd、进程跟踪
   - 用户可见的 slash commands、关键快捷键、错误提示方向

2. 可以 Python 化重写
   - 配置文件直接使用 TOML
   - React/Ink 组件树改为 `prompt-toolkit` + `rich` 的 TUI 状态机
   - TypeScript 类型和测试组织改为 Pydantic/dataclass + pytest
   - Node/npm 的更新检查和发布逻辑改为 Python 包生态方案

3. 暂不迁移或删除
   - 只服务旧 Node 打包链路的 glue code
   - 视觉细节强绑定 Ink 的组件拆分
   - 低价值、难验证、没有用户可见收益的内部抽象
   - 第一阶段高级功能，如 MCP、subagent、SQLite、OAuth、Web UI

### 2.5 当前 plan.md 的不足

原计划方向正确，但缺少可执行层面的拆解：

- 没有明确 `src/session.ts` 的拆分边界。
- 没有列出必须兼容的 JSONL/message/session schema。
- 没有把工具层安全约束作为验收项。
- 没有区分核心兼容迁移、可裁剪实现和高级功能扩展。
- 没有说明 `updateCheck` 从 npm 迁移到 Python 后如何处理。
- 没有说明 `docs/tools/*.md` 在 Python wheel 中如何打包。
- 没有列出 TypeScript 测试到 `pytest` 的迁移映射。
- 没有给出分阶段可运行的验收命令。

## 3. Python 目标架构

### 3.1 项目形态

使用 `uv` 管理 Python 项目，Python 版本要求 `>=3.12`。因为需要 console script、`src` layout 和 wheel/sdist，项目必须声明 build system。

建议骨架：

```text
pyproject.toml
README.md
LICENSE
docs/tools/*.md
src/deepy/
  __init__.py
  __main__.py
  cli.py
  config/
    __init__.py
    settings.py
  llm/
    __init__.py
    provider.py
    agent.py
    runner.py
    events.py
    thinking.py
    model_capabilities.py
  prompts/
    __init__.py
    system.py
    compact.py
    runtime_context.py
    tool_schema.py
  sessions/
    __init__.py
    models.py
    store.py
    sdk_session.py
    manager.py
    compaction.py
    skills.py
  tools/
    __init__.py
    base.py
    executor.py
    runtime.py
    state.py
    file_utils.py
    shell_utils.py
    bash.py
    read.py
    write.py
    edit.py
    ask_user_question.py
    web_search.py
  tui/
    __init__.py
    app.py
    prompt_input.py
    prompt_buffer.py
    message_view.py
    session_list.py
    ask_user_question.py
    clipboard.py
    loading_text.py
    exit_summary.py
    markdown.py
    slash_commands.py
    welcome.py
  utils/
    __init__.py
    debug_logger.py
    error_logger.py
    notify.py
    update_check.py
tests/
```

### 3.2 `pyproject.toml` 初始方向

参考当前 uv 官方文档，纯 Python 包可以使用 `uv_build`。第一阶段不含 Rust/C 扩展，因此不需要 `maturin` 或 `scikit-build-core`。

```toml
[project]
name = "Deepy"
version = "0.1.15"
description = "Deepy - Vibe coding for the deepseek-v4 model in your terminal"
readme = "README.md"
requires-python = ">=3.12"
license = "MIT"
dependencies = [
  "typer>=0.15",
  "prompt-toolkit>=3.0",
  "rich>=13",
  "openai-agents>=0.17.0",
  "openai>=2.26,<3",
  "httpx[socks]>=0.27",
  "pydantic>=2",
  "orjson>=3",
  "tomli-w>=1",
  "python-frontmatter>=1",
  "pathspec>=0.12",
]

[project.scripts]
deepy = "deepy.__main__:main"

[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "ruff>=0.8",
  "pyright>=1.1",
]

[build-system]
requires = ["uv_build>=0.11.6,<0.12"]
build-backend = "uv_build"
```

注意：

- `python-frontmatter` 用于替代 `gray-matter`。
- `pathspec` 用于替代 JS `ignore`，处理 `.gitignore` 和默认忽略规则。
- `pydantic` 用于 settings/session/tool models，但内部热路径可以使用 dataclass 以减少样板。
- Python 3.12 标准库 `tomllib` 用于读取 `~/.deepy/config.toml`；`tomli-w` 只在需要写配置时使用。
- `orjson` 用于 JSONL 和工具结果，注意输出 bytes，需要统一封装。
- `openai-agents` 负责 agent loop、tool calling、streaming events、usage、interrupt/resume 表面；DeepSeek 走 `OpenAIChatCompletionsModel`，不要自研完整 Chat Completions loop。
- `prompt-toolkit` 和 `rich` 负责 TUI，不要尝试复刻 React/Ink 的组件模型。

### 3.3 `openai-agents` SDK 接入决策

调研 `reference/openai-agents-python` 后，Python 版应使用 `openai-agents` SDK 作为运行时骨架：

- DeepSeek 属于 OpenAI-compatible Chat Completions provider，应通过 `OpenAIChatCompletionsModel` 接入，而不是默认 Responses model。
- 用 `AsyncOpenAI(base_url=settings.model.base_url, api_key=settings.model.api_key)` 构造 provider client。
- 用 `Agent(..., model=OpenAIChatCompletionsModel(...), tools=[...])` 定义 Deepy 主 agent。
- 用 `Runner.run_streamed(...)` 驱动 streaming agent loop，并从 `stream_events()` 转换成 TUI 事件。
- 用 `RunResult.new_items`、`raw_responses`、`final_output` 和 usage 信息更新 session、UI 和 debug log。
- 用 `SessionABC` 实现 Deepy 自己的 JSONL-backed session，让 SDK 管理本轮输入合并和新 item 持久化。
- 默认关闭 SDK tracing，除非用户显式配置 OpenAI tracing key；避免把 DeepSeek 请求内容发送到 OpenAI tracing。

DeepSeek 模型构造示例：

```python
from openai import AsyncOpenAI
from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, Runner, set_tracing_disabled

set_tracing_disabled(True)

client = AsyncOpenAI(
    base_url=settings.model.base_url,
    api_key=settings.model.api_key,
)

model = OpenAIChatCompletionsModel(
    model=settings.model.name,
    openai_client=client,
)

agent = Agent(
    name="Deepy",
    instructions=system_prompt,
    model=model,
    model_settings=ModelSettings(
        extra_body=deepseek_extra_body(settings),
    ),
    tools=build_tools(tool_runtime),
)

result = Runner.run_streamed(
    agent,
    input=user_input,
    session=deepy_session,
    run_config=deepy_run_config,
)
```

`OpenAIChatCompletionsModel` 的注意事项：

- 它不支持 Responses API 的 `prompt`、`previous_response_id`、`conversation_id` 等 server-managed conversation state；Deepy 继续使用本地 session/history。
- SDK 会把 Chat Completions stream 归一化成 Responses-style stream events；TUI 不应直接依赖 provider 原始 chunk。
- SDK 已处理 DeepSeek `reasoning_content` replay：DeepSeek 工具调用后的下一轮 request 需要带回 reasoning_content，避免 provider 400。
- DeepSeek provider-specific 参数应通过 `ModelSettings.extra_body` 集中构造；不要把 DeepSeek thinking 逻辑散落到 runner、tool 或 TUI 层。
- Hosted tools、deferred tool search、Responses-only prompt 等能力不作为第一阶段目标，因为 Chat Completions model shape 不支持完整 Responses feature set。

后续若要支持 Responses API，应作为另一个 provider adapter 增量扩展，而不是迁移第一阶段的默认路径。

## 4. 模块迁移映射

### 4.1 CLI 和配置

| TypeScript | Python | 说明 |
| --- | --- | --- |
| `src/cli.tsx` | `deepy/__main__.py`、`deepy/cli.py` | Typer 处理 `--help`、`--version`，启动 TUI |
| `src/settings.ts` | `config/settings.py` | 新配置使用 TOML，不读取旧 JSON 配置 |
| `src/updateCheck.ts` | `utils/update_check.py` | 第一阶段可降级为可选检查，不阻塞启动 |
| `src/notify.ts` | `utils/notify.py` | `subprocess.Popen(..., start_new_session=True)`，保留 `DURATION` |
| `src/debug-logger.ts` | `utils/debug_logger.py` | 继续写 `~/.deepy/logs/debug.log` |
| `src/error-logger.ts` | `utils/error_logger.py` | 继续写 `~/.deepy/logs/error.log` 并 mask secret |

配置文件示例：

```toml
[model]
name = "deepseek-v4-pro"
base_url = "https://api.deepseek.com"
api_key = ""
thinking = true
reasoning_effort = "high"

[logging]
debug = false

[notify]
enabled = false
command = ""

[tools.web_search]
command = ""
api_url = ""

[context]
window_tokens = 1048576
compact_trigger_ratio = 0.8
compact_prompt_token_threshold = 838861
```

加载优先级：

1. 环境变量覆盖显式配置，例如 `DEEPY_MODEL`、`DEEPY_BASE_URL`、`DEEPY_API_KEY`。
2. `~/.deepy/config.toml` 是主配置。
3. 如果 TOML 不存在，使用内置默认值。

### 4.2 Prompt 和模型兼容

| TypeScript | Python | 说明 |
| --- | --- | --- |
| `src/prompt.ts` | `prompts/system.py`、`prompts/tool_schema.py`、`prompts/runtime_context.py`、`prompts/compact.py` | 拆分工具文档、runtime context、compact prompt |
| `src/openai-thinking.ts` | `llm/thinking.py` | 构造 DeepSeek `ModelSettings.extra_body`，保留 `thinking` 与 `reasoning_effort` |
| `src/model-capabilities.ts` | `llm/model_capabilities.py` | 保留 DeepSeek 模型集合 |
| `docs/tools/*.md` | package data | wheel 中必须包含，否则 system prompt 缺工具说明 |
| Node `openai` client setup | `llm/provider.py` | 创建 `AsyncOpenAI` 和 `OpenAIChatCompletionsModel` |
| `src/session.ts` 中的 streaming/tool loop | `llm/runner.py`、`llm/events.py` | 用 `Runner.run_streamed()` 和 SDK stream events 替代自研 loop |

### 4.3 Session

`src/session.ts` 不应原样翻译成一个 2000 行 Python 文件。Python 版应让 `openai-agents` 负责 agent turn loop，并把 Deepy 自己的持久化封装为 SDK session：

| Python 模块 | 职责 |
| --- | --- |
| `sessions/models.py` | `SessionEntry`、`SessionMessage`、`SkillInfo`、`UserPromptContent`、status enum |
| `sessions/store.py` | project code、index 读写、JSONL 读写、legacy normalize、最多 50 条 |
| `sessions/sdk_session.py` | 实现 `agents.memory.session.SessionABC`，把 SDK input items 映射到 Deepy JSONL |
| `sessions/skills.py` | skill 扫描、frontmatter 解析、路径解析、已加载判断、自动匹配 |
| `sessions/manager.py` | create/reply/activate/interrupt 主流程，调用 `Runner.run_streamed()` |
| `sessions/compaction.py` | compaction 窗口选择、compact prompt、summary 插入，可通过 `RunConfig.session_input_callback` 控制输入裁剪 |
| `llm/events.py` | SDK stream events 到 UI message/tool/thinking/status 事件的转换 |

Session 取舍：

- 第一阶段不使用 SDK 内置 `SQLiteSession`，因为 Deepy 需要保留现有项目级 JSONL 会话目录和 `/resume` 体验。
- `DeepySession(SessionABC)` 只负责 `get_items/add_items/pop_item/clear_session`，底层仍写 `~/.deepy/projects/<project-code>/...`。
- 如果需要自定义历史裁剪，优先使用 `RunConfig.session_input_callback`，不要在 TUI 层拼接 prompt。
- `OpenAIResponsesCompactionSession` 是 Responses API 专用；DeepSeek 的 `OpenAIChatCompletionsModel` 路径不使用它。
- Deepy 自己按 `[context] window_tokens` 和 `compact_trigger_ratio` 判断是否 compact，默认 1M 上下文窗口，超过 80% 即 `838861` tokens 触发。

### 4.4 Tools

| TypeScript | Python | 迁移要点 |
| --- | --- | --- |
| `src/tools/executor.ts` | SDK Runner + `tools/base.py` | 不再自研 tool-call loop；只保留工具注册、运行时状态和错误格式化 |
| `src/tools/runtime.ts` | `tools/runtime.py` | 为 `@function_tool` handler 提供上下文、权限、cwd、文件状态和 pydantic 校验 |
| `src/tools/state.ts` | `tools/state.py` | session 内存级 file state 和 snippet state |
| `src/tools/file-utils.ts` | `tools/file_utils.py` | 编码、换行、mtime、diff preview |
| `src/tools/shell-utils.ts` | `tools/shell_utils.py` | zsh/bash/Git Bash、Windows path、环境变量 |
| `src/tools/bash-handler.ts` | `tools/bash.py` | session cwd、marker、输出截断、进程跟踪 |
| `src/tools/read-handler.ts` | `tools/read.py` | 文本、图片、PDF、notebook、suffix 匹配、gitignore |
| `src/tools/write-handler.ts` | `tools/write.py` | existing file 必须先 full read，mtime 检测，JSON object repair |
| `src/tools/edit-handler.ts` | `tools/edit.py` | snippet scope、replace_all guard、closest match、LLM escape correction |
| `src/tools/ask-user-question-handler.ts` | `tools/ask_user_question.py` | `await_user_response` 元数据 |
| `src/tools/web-search-handler.ts` | `tools/web_search.py` | 自定义脚本优先，否则默认 web-search API |

工具实现原则：

- 每个内置工具用 `agents.function_tool` 包装，工具名保持 `bash/read/write/edit/AskUserQuestion/WebSearch`。
- 旧版 tool result 的 `ok/name/output/error/metadata/awaitUserResponse` 结构继续作为模型可见返回值，避免迁移后提示词和模型反馈大幅变化。
- SDK 负责接收 tool calls、执行 function tools、追加 tool outputs 和继续下一轮模型调用；Deepy 只在 handler 内实现安全约束。
- `AskUserQuestion` 需要映射到 SDK interruption / human-in-the-loop 机制，或在第一阶段保留自定义 pending-question 状态，但不能阻塞 event loop。
- Responses-only hosted tools、deferred `ToolSearchTool`、hosted web search 不纳入第一阶段，因为 DeepSeek 使用 Chat Completions model shape。

### 4.5 TUI

Python TUI 不应尝试逐行复刻 Ink 组件，而应复刻用户可见行为：

| TypeScript | Python | 迁移要点 |
| --- | --- | --- |
| `src/ui/App.tsx` | `tui/app.py` | 主状态机、消息追加、session 切换、pending question |
| `src/ui/PromptInput.tsx` | `tui/prompt_input.py` | prompt-toolkit key binding 和 completion |
| `src/ui/promptBuffer.ts` | `tui/prompt_buffer.py` | 纯逻辑先迁移并用 pytest 锁定 |
| `src/ui/slashCommands.ts` | `tui/slash_commands.py` | slash item 构建、过滤、精确匹配 |
| `src/ui/MessageView.tsx` | `tui/message_view.py` | rich render，tool summary，diff preview |
| `src/ui/SessionList.tsx` | `tui/session_list.py` | 上下移动、分页、选择 session |
| `src/ui/clipboard.ts` | `tui/clipboard.py` | macOS `pngpaste`/`osascript`、Linux `xclip`/`wl-paste`、Windows PowerShell |
| `src/ui/exitSummary.ts` | `tui/exit_summary.py` | `/exit` 摘要保持 |

## 5. 分阶段实施计划

### Phase 0 - 冻结当前行为基线

目标：把用户可见行为变成 Python 迁移的验收标准。

任务：

- [x] 运行当前测试：`npm test`
  - 2026-05-11: `reference/deepcode-cli-js` 中通过，144 pass。
- [x] 运行类型检查：`npm run typecheck`
  - 2026-05-11: `reference/deepcode-cli-js` 中通过。
- [x] 记录当前 `deepy --help` 和 `deepy --version` 输出
  - 2026-05-11: `uv run deepy --help` 正常；`uv run deepy --version` 输出 `Deepy 0.1.0`。
- [x] 为 session JSONL 准备 fixture：
  - [x] 普通 user/assistant
  - [x] assistant tool call + paired tool message
  - [x] thinking mode assistant message
  - [x] image `contentParams`
  - [x] compacted summary
  - [x] legacy `processes`
- [x] 为 tools 准备 fixture：
  - [x] read full text
  - [x] read partial text + snippet
  - [x] edit by snippet
  - [x] write existing file without read 被拒绝
  - [x] edit file changed since read 被拒绝
  - [x] replace_all guard
  - [x] bash cwd persistence

验收：

- 当前 TypeScript 版测试全部通过，或明确记录已有失败。
- fixture 能被 Python 测试复用。

### Phase 1 - Python 项目骨架

目标：建立可运行、可测试、可打包的 Python CLI。

任务：

- [x] 新建 `pyproject.toml`
- [x] 新建 `src/deepy/`
- [x] 配置 `deepy = "deepy.cli:main"`
- [x] 配置 `uv_build`
- [x] 配置 pytest
- [x] 配置 ruff、pyright
  - 2026-05-11: `uv run ruff check` 通过；`uv run pyright` 通过。
- [x] 保留并打包 `src/deepy/data/tools/*.md`
- [x] 实现 `deepy --help`
- [x] 实现 `deepy --version`
- [x] 实现 TTY 检查

验收：

```bash
uv run deepy --help
uv run deepy --version
uv run pytest
uv run ruff check
uv run pyright
uv build
```

### Phase 2 - 纯逻辑模块迁移

目标：迁移无外部副作用或副作用较小的模块，先建立 Python 测试信心。此阶段只迁移有明确用户价值或被后续模块依赖的逻辑，不搬运旧项目中只服务 Node/Ink 的内部结构。

任务：

- [x] `config/settings.py`
  - 解析 `~/.deepy/config.toml`
  - 支持环境变量覆盖
  - thinking 默认值
  - reasoning effort normalize
- [x] `llm/model_capabilities.py`
- [x] `llm/thinking.py`
- [x] `utils/notify.py`
- [x] `utils/debug_logger.py`
- [x] `utils/error_logger.py`
- [x] `tui/exit_summary.py`
- [x] `tui/loading_text.py`
- [x] `tui/thinking_state.py`
- [x] `tui/slash_commands.py`
- [x] `tui/prompt_buffer.py`
- [x] `tui/markdown.py`

测试迁移：

- `settings-and-notify.test.ts`
- `openai-thinking.test.ts`
- `exitSummary.test.ts`
- `loadingText.test.ts`
- `thinkingState.test.ts`
- `slashCommands.test.ts`
- `promptBuffer.test.ts`
- `markdown.test.ts`
- `debug-logger.test.ts`

验收：

```bash
uv run pytest tests/test_settings.py tests/test_prompt_buffer.py tests/test_slash_commands.py
```

### Phase 3 - Prompt 和 SDK 工具定义

目标：Python 版生成 system prompt、compact prompt，并把内置工具注册成 `openai-agents` function tools。

任务：

- [x] 迁移 `get_system_prompt(project_root)`
- [x] 迁移 `get_compact_prompt(session_messages)`
- [x] 迁移 runtime context：
  - root path
  - pwd
  - homedir
  - system info
  - shell path
  - python3 version
  - node version
  - ast-grep/ripgrep/jq installed
- [x] 迁移 tools schema，字段名保持与旧版一致，并通过 `agents.function_tool` 注册
- [x] 确保 `WebSearch` 总是包含
- [x] 确保 `src/deepy/data/tools/*.md` 从 installed package 中可读取

测试迁移：

- `prompt.test.ts`

验收：

- SDK 注册后的 function tool 名称集合与旧版一致。
- `get_system_prompt()` 包含 `## WebSearch`。
- wheel 安装后仍能读取工具文档。

### Phase 4 - 工具运行时和文件状态

目标：先迁移工具层，不接真实 LLM 主循环；用 SDK function tool 包装验证 handler 行为。

任务：

- [x] `tools/result.py` 定义 `ToolExecutionResult` 等价结果结构
- [x] `tools/agents.py` 提供 `build_function_tools(runtime)`，返回 SDK `FunctionTool` 列表
- [x] `tools/agents.py` / `tools/builtin.py` 实现 pydantic 校验和错误格式
- [x] `tools/file_state.py` 实现 per-runtime file state 和 mtime 检测
- [x] snippet state、路径歧义 normalize
- [x] `tools/builtin.py` 实现 diff preview
- [x] 保留原 encoding
- [x] 保留原 line endings
- [x] `tools/shell_utils.py` 实现 shell 解析和 Windows Git Bash 兼容 helper
  - [x] shell kind and init/extglob helpers
  - [x] Windows/Git Bash path conversion
  - [x] Windows nul redirect rewrite

验收：

- 所有 SDK function tool 的 name/schema 与预期一致
- handler 参数校验失败时返回模型可读错误
- result JSON 字段和 TypeScript 版一致
- file state/snippet state 不跨 session 泄漏

### Phase 5 - 内置工具迁移

目标：迁移所有内置工具，并用 pytest 覆盖安全约束。

任务：

- [x] `bash`
  - [x] session cwd persistence
  - [x] command marker
  - [x] stdout/stderr 合并
  - [x] `MAX_OUTPUT_CHARS = 30000`
  - [x] `MAX_CAPTURE_CHARS = 10 * 1024 * 1024`
  - [x] process start/exit tracking
  - [x] interrupted metadata
  - [x] shell_utils helper 接入实际执行路径

- [x] `read`
  - [x] absolute path / relative path resolve
  - [x] 相对路径存在歧义时拒绝
  - [x] `.gitignore` + 默认忽略
  - [x] 默认忽略构建和缓存目录
  - [x] 文本行号输出
  - [x] `DEFAULT_LINE_LIMIT = 2000`
  - [x] `MAX_LINE_LENGTH = 2000`
  - [x] snippet metadata
  - [x] `.ipynb` 文本化
  - [x] 图片转 follow-up system image message
  - [x] PDF 页数检查和 base64 输出

- [x] `write`
  - [x] absolute path / relative path resolve
  - [x] existing file 必须 full read
  - [x] mtime 变更检测
  - [x] 保留原 encoding
  - [x] 保留原 line endings
  - [x] `.json` object content 自动 stringify
  - [x] diff preview

- [x] `edit`
  - [x] `file_path`
  - [x] `snippet_id`
  - [x] full read scope
  - [x] snippet read scope
  - [x] mtime 变更检测
  - [x] exact match
  - [x] duplicate candidate snippets
  - [x] replace_all guard
  - [x] closest match metadata
  - [x] loose escape match
  - [x] LLM escape correction
  - [x] diff preview
  - [x] 保留原 line endings

- [x] `AskUserQuestion`
  - questions/options 校验
  - summary 输出
  - `awaitUserResponse: true`
  - metadata `kind: "ask_user_question"`

- [x] `WebSearch`
  - [x] 本地 command 优先
  - [x] 默认 web search 需要可用 LLM 配置和 machine id
  - [x] 中英文 dominant language 判断
  - [x] query 翻译
  - [x] 默认 API 由配置提供，不在 spec 中固化外部站点
  - [x] process activity hooks

测试迁移：

- `tool-handlers.test.ts`
- `shell-utils.test.ts`
- `web-search-handler.test.ts`
- `askUserQuestion.test.ts`
- `clipboard.test.ts`

验收：

```bash
uv run pytest tests/test_tools.py tests/test_shell_utils.py tests/test_web_search.py
```

### Phase 6 - Session store 和 message replay

目标：不接真实 LLM，先完成 Deepy session 存储，并实现可交给 SDK Runner 使用的 `SessionABC`。

任务：

- [x] `sessions/jsonl.py` 使用 dataclass 定义 schema
- [x] `sessions/jsonl.py` 实现：
  - [x] `project_code`
  - [x] `project_sessions_dir`
  - [x] list session index
  - [x] save sessions index
  - [x] list session items
  - [x] append session items
  - [x] clear/pop session items
  - [x] legacy normalize
  - [x] 50 条 session 裁剪
- [x] `DeepyJsonlSession` 实现 SDK session 方法：
  - [x] `get_items(limit=None)`
  - [x] `add_items(items)`
  - [x] `pop_item()`
  - [x] `clear_session()`
  - [x] SDK item 与 Deepy JSONL message 的双向映射
- [x] 实现 UI/debug 所需的 message snippet：
  - params snippet
  - result snippet
  - invisible execution 判断
- [x] 实现 SDK input item replay：
  - [x] compacted message 跳过
  - [x] user/system image contentParts
  - [x] assistant tool_calls
  - [x] tool_call_id
  - [x] thinking 模式补空 reasoning_content
  - [x] tool pairings
  - [x] interrupted tool fallback

测试迁移：

- `session.test.ts` 中与 storage、normalize、message replay 相关的测试
- `sessionList.test.ts`

验收：

- Python 能读取 TypeScript 写出的旧 session index 和 JSONL。
- Python 写出的新 session 能被 TypeScript 版 `listSessionMessages` 读出。
- thinking replay 行为与当前测试一致。

### Phase 7 - `openai-agents` Runner 和 SessionManager 主循环

目标：完成无 UI 依赖的 agent loop，使用 SDK Runner 替代自研 Chat Completions loop。

任务：

- [x] `llm/provider.py` 创建 `AsyncOpenAI`，读取 TOML settings 中的 `base_url/api_key/model`
- [x] `llm/provider.py` 创建 `OpenAIChatCompletionsModel`
- [x] `llm/thinking.py` 构造 DeepSeek `ModelSettings.extra_body`
- [x] `llm/agent.py` 创建 Deepy `Agent`，注入 system prompt、model、model_settings、function tools
- [x] `llm/runner.py` 调用 `Runner.run_streamed()`：
  - [x] 传入 `DeepyJsonlSession`
  - [x] 传入 `RunConfig(..., session_input_callback=...)`
  - [x] 处理 max turns
  - [x] 支持 interruption
  - [x] 支持 resume by session id
- [x] `llm/events.py` 转换 SDK stream events：
  - [x] raw text delta
  - [x] reasoning delta/item
  - [x] tool called
  - [x] tool output
  - [x] agent updated
  - [x] final output/message
  - [x] usage/raw response
- [x] `skills.py` 实现：
  - [x] skill list
  - [x] frontmatter parse
  - [x] loaded state
  - [x] skill auto match
  - [x] skill content injection
- [x] `sessions/manager.py` 实现：
  - `handle_user_prompt`
  - `create_session`
  - `reply_session`
  - `activate_session`
  - `append_sdk_items`
  - `compact_session`
  - `interrupt_active_session`
  - `interrupt_session`
  - process kill
  - notify
- [x] 保留 compaction 阈值：
  - 默认 1M context window
  - 超过 80% 触发，即 `838861`
- [x] 保留 max turn 防护，并映射到 SDK `max_turns`

测试迁移：

- `session.test.ts` 中与 create/reply/activate/compaction/interrupt 相关的测试
- 新增 fake `OpenAIChatCompletionsModel` stream 测试
- 新增 SDK function tool loop 测试

验收：

- mock LLM 返回普通 assistant message，session 进入 `completed`。
- mock LLM 返回 tool call，工具执行后继续下一轮。
- mock LLM 返回 `AskUserQuestion`，session 进入 `waiting_for_user`。
- interrupt 会 abort LLM 请求并清理进程。

### Phase 8 - Python TUI

目标：重建用户可见交互体验。

任务：

- [x] `tui/app.py` 管理：
  - [x] current view
  - [x] busy
  - [x] messages
  - [x] sessions
  - [x] skills
  - [x] status line
  - [x] error line
  - [x] stream progress
  - [x] running processes
  - [x] pending questions
- [x] `tui/prompt_input.py` 实现：
  - [x] prompt-toolkit input
  - [x] multiline
  - [x] key bindings
  - [x] slash completion
  - [x] skill selection helpers
  - [x] prompt history
  - [x] busy 时 Esc interrupt
  - [x] Ctrl+D 双击退出
  - [x] image attachment status helpers
  - [x] cursor rendering helper
  - [x] cursor placement helper
- [x] `tui/message_view.py` 使用 rich 渲染：
  - [x] user
  - [x] assistant
  - [x] thinking/tool summary
  - [x] system skill
  - [x] summary inserted
  - [x] diff preview for successful `edit/write`
- [x] `tui/session_list.py` 实现 `/resume`
  - [x] title formatting
  - [x] visible window and selection movement
- [x] `tui/ask_user_question.py` 实现 pending question 选择
  - [x] pending question 解析
  - [x] answer/decline 文本格式化
  - [x] option list and answer construction helpers
- [x] `tui/clipboard.py` 实现图片粘贴
  - [x] image data URL helpers
  - [x] platform command fallbacks
- [x] `tui/welcome.py` 实现欢迎屏
  - [x] home-relative path formatting
  - [x] welcome tips/settings data
- [x] `/exit` 打印 exit summary
- [x] `/new` 重置 session 并清空 loaded skills

验收：

```bash
uv run deepy
```

手工 smoke：

- 启动后显示欢迎屏
- `/exit` 显示 summary 并退出
- `/new` 清空当前会话
- `/resume` 可选择历史会话
- `/skills` 可选择 skill
- Esc 可中断当前响应
- Ctrl+V 可粘贴图片，失败时给出状态提示

### Phase 9 - 测试迁移和兼容验收

目标：让 Python 版拥有与当前 TS 版相近的测试覆盖。

测试迁移优先级：

1. `settings-and-notify.test.ts`
2. `openai-thinking.test.ts`
3. `prompt.test.ts`
4. `tool-handlers.test.ts`
5. `shell-utils.test.ts`
6. `session.test.ts`
7. `promptBuffer.test.ts`
8. `slashCommands.test.ts`
9. `messageView.test.ts`
10. `sessionList.test.ts`
11. `askUserQuestion.test.ts`
12. `clipboard.test.ts`
13. `web-search-handler.test.ts`
14. `updateCheck.test.ts`

完整验收命令：

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run pyright
uv run deepy --help
uv run deepy --version
uv build
```

兼容验收：

- [x] Python 版优先读取 `~/.deepy/config.toml`
- [x] Python 版读取旧 `sessions-index.json`
- [x] Python 版读取旧 session JSONL
- [x] Python 版写出的 session JSONL 结构与旧格式兼容
- [x] 工具 schema 与旧版完全一致
  - 2026-05-11: Python `FunctionTool` 改为手写旧版参数 schema，并用测试校验工具名、参数键和 required 列表。
- [x] 工具名称集合与旧版一致
- [x] DeepSeek thinking 请求体与旧版一致
- [x] `src/deepy/data/tools/*.md` 在安装后仍存在
- [x] 无 API key 时错误提示与旧版一致
- [x] notify 脚本不阻塞主流程
- [x] debug/error log 写入失败不影响 CLI

### Phase 10 - 切换、发布和旧代码清理

目标：在 Python 版通过验收后，再决定 Node 工程的命运。

任务：

- [x] 更新 README 安装方式：
  - `uv tool install ...`
  - 或 `pipx install ...`
  - 或 PyPI wheel
- [x] 明确 npm 包迁移策略：
  - 方案 A：npm 包停止更新，Python 包成为主分发
  - 方案 B：npm 包变成 wrapper，调用 Python CLI
  - 方案 C：保留 TS 版一段时间，Python 版用新渠道发布
- [x] 确定版本号策略
- [x] 确定 release artifact：
  - wheel
  - sdist
  - 可选 standalone executable
- [x] Python 版稳定后，再移除或归档旧 Node 源码：
  - 2026-05-11: 旧 Node 源码留存/归档不再作为当前 Python 项目的完成条件；JS 仅作参考。
  - `package.json`
  - `package-lock.json`
  - `tsconfig.json`
  - `src/*.ts`
  - `src/*.tsx`

清理前置条件：

- Python 版完整测试通过。
- Python 版能读取已有用户配置和 session。
- README 已说明安装和迁移方式。
- 至少完成一次真实 CLI smoke test。

## 6. 关键风险和处理策略

### 6.1 `session.ts` 过大

风险：原样翻译会得到一个难维护的 Python 巨型文件。

处理：

- 强制拆为 store/models/skills/manager/compaction/streaming。
- 所有拆分后的边界必须先有 pytest 覆盖。
- `SessionManager` 只保留流程编排，不负责 JSONL 细节和 streaming chunk 细节。

### 6.2 Python TUI 与 Ink 心智模型不同

风险：试图复刻 React component tree 会拖慢迁移。

处理：

- 复刻行为，不复刻组件实现。
- `prompt_buffer`、`slash_commands`、`message_view` 先做纯函数测试。
- TUI 第一版可接受视觉上略有不同，但快捷键和状态必须一致。

### 6.3 Chat Completions provider 差异

风险：OpenAI、DeepSeek、火山方舟等兼容接口对 thinking、reasoning、tool calls 字段支持不同。

处理：

- provider pass-through adapter 由 `AsyncOpenAI` + `OpenAIChatCompletionsModel` 承担。
- DeepSeek thinking 字段集中在 `llm/thinking.py`。
- streaming 聚合优先使用 SDK stream events；如果需要 provider 原始信息，再从 `raw_responses` 或 raw event data 读取。
- 保留 DeepSeek `reasoning_content` replay 测试，确保工具调用后的下一轮 request 不丢 reasoning_content。
- debug log 必须保留 request body，方便排查 provider 差异。

### 6.4 文件工具安全约束退化

风险：迁移时最容易丢失读后写保护、mtime 检测、snippet 限定和 replace_all guard。

处理：

- Phase 5 之前不得接入真实 agent loop。
- 所有 file tool 行为先单测通过。
- `write/edit` 的错误文案尽量保持旧版，减少模型工具调用反馈变化。

### 6.5 更新检查从 npm 迁移到 Python

风险：当前 `updateCheck.ts` 是 npm-specific，Python 包没有等价逻辑。

处理：

- 第一阶段允许把 update check 降级为 no-op 或 PyPI 查询，但不能阻塞启动。
- 若继续分发 npm wrapper，再由 wrapper 负责 npm 更新检查。
- Python 主包内不要执行 `npm install -g`。

### 6.6 默认 WebSearch 依赖外部 API

风险：默认搜索如果依赖外部 HTTP 服务，会增加可用性和隐私风险。

处理：

- 默认 endpoint 必须来自配置，不在 spec 或代码中固化项目站点。
- 测试中必须 mock HTTP。
- 文档中明确可通过 `webSearchTool` 使用本地脚本替代。

### 6.7 包数据遗漏

风险：`docs/tools/*.md` 没被 wheel 包含后，system prompt 会缺工具说明。

处理：

- 把工具文档迁移到 `src/deepy/data/tools/*.md`，或配置 `uv_build` data/source include。
- 安装后测试 `get_system_prompt()`。

## 7. 非目标

第一阶段明确不做：

- MCP
- subagent
- SQLite session store
- OAuth/multi-provider UI
- Web UI
- 复杂 approval mode
- AST-aware edit
- 自动模型路由
- DeepSeek KV cache 深度优化
- `/plan` 模式
- 后台任务系统

这些内容已经适合放在 `advanced.md` 中作为 Python 版稳定后的扩展路线。

## 8. 推荐执行顺序

最稳妥的顺序：

1. Phase 0：冻结 TypeScript 行为基线。
2. Phase 1：创建 Python 项目骨架。
3. Phase 2：迁移纯逻辑和测试。
4. Phase 3：迁移 prompt 和 tools schema。
5. Phase 4：迁移工具 runtime。
6. Phase 5：迁移所有工具并完成工具测试。
7. Phase 6：迁移 session store 和 message replay。
8. Phase 7：接入 `openai-agents` Runner 和 streaming events。
9. Phase 8：重建 TUI。
10. Phase 9：完整测试和兼容验收。
11. Phase 10：发布切换和旧代码清理。

不建议并行推进 UI 和 session 主循环。先让无 UI 的 agent loop 在测试里跑通，再接 TUI。
