# Deepy UI 与 Deepy TUI

本文用来说明 Deepy 的两个终端界面，并记录当前功能对齐情况。

## 界面定位

- Deepy UI：默认界面，运行 `deepy` 启动。
- Deepy TUI：实验性 Textual 界面，运行 `deepy tui` 启动。
- 两个界面共用同一套模型运行、工具调用、session、skills、MCP 和自动 compact 逻辑。
- TUI 不是默认入口，这是当前设计选择。

## Deepy UI

Deepy UI 是稳定界面，基于 Rich 和 prompt-toolkit。

主要功能：

- 普通聊天和多轮 agent 执行。
- Thinking、工具调用、工具结果、usage、错误信息渲染。
- `shell`、`read`、`modify`、`todo_write`、`AskUserQuestion`、Web、MCP 等工具输出。
- `/new`、`/resume`、`/sessions`、`/compact` 等 session/context 命令。
- `/init`、`/reset`、`/model`、`/theme`、`/mcp`、`/status`、`/skills` 等管理命令。
- `/ps` 查看模型启动的后台 shell 任务，`/stop` 可选择停止单个任务或全部运行中的后台任务。
- `/status` 会显示用量、上下文窗口和 DeepSeek 余额；余额接口只在显式运行 `/status` 时调用。
- `/exit`、`/quit` 和 Ctrl+D 连按两次会输出统一的 session summary。
- 退出 Deepy 时会先清理仍在运行的后台任务，再清理 MCP runtime。
- `!command` 本地命令模式。
- slash 命令补全和 `@file` 文件补全。
- prompt history。
- 自动 compact 和 `compact next` 提示。
- 底部状态显示 model、cwd、AGENTS、MCP 数量、context 使用量。
- 首次缺配置时引导用户配置 API key、model、base URL 和 theme。

## Deepy TUI

Deepy TUI 是实验界面，基于 Textual。

主要功能：

- 普通聊天和多轮 agent 执行。
- Thinking、工具调用、工具结果、usage、错误信息渲染。
- 工具结果块支持展开、折叠、元信息和更清晰的视觉样式。
- `shell`、`read`、`todo_write`、Web、MCP、`load_skill` 等工具有专门显示效果。
- AskUserQuestion 支持单选、多选、自定义回答、取消和同 session 继续。
- `/new`、`/resume`、`/sessions`、`/compact` 已支持。
- `/init`、`/reset`、`/model`、`/theme`、`/mcp`、`/status`、`/skills` 已支持。
- `/ps`、`/stop` 已支持，用于查看后台 shell 任务，并选择停止单个任务或全部任务。
- `/status` 会显示用量、上下文窗口和 DeepSeek 余额；余额接口只在显式运行 `/status` 时调用。
- `/exit`、`/quit` 和 Ctrl+D 连按两次会在退出后输出与稳定 UI 一致的 session summary。
- `!command` 本地命令模式已支持，并复用 shell 工具块显示结果。
- slash 命令补全和 `@file` 文件补全已支持。
- prompt history 已支持。
- 自动 compact 已支持。
- 底部状态显示 model、cwd、AGENTS、MCP 数量、context 使用量和 `compact next`。
- `/skills` 提供独立管理界面，支持 market/installed、查看、安装、卸载、更新和刷新。
- built-in skills 不在 TUI skill 管理界面里显示。
- 支持删除手工安装的 user/project skill。
- 首次缺配置时会在 TUI 内引导用户填写配置。

## 功能对比

| 功能 | Deepy UI | Deepy TUI | 当前状态 |
| --- | --- | --- | --- |
| 默认入口 | 是 | 否 | 设计如此 |
| 普通聊天 | 支持 | 支持 | 已对齐 |
| Thinking 显示 | 支持 | 支持 | 已对齐 |
| 工具调用显示 | 支持 | 支持 | 已对齐 |
| AskUserQuestion | 支持 | 支持 | 已对齐 |
| session 恢复 | 支持 | 支持 | 已对齐 |
| `/compact` | 支持 | 支持 | 已对齐 |
| 自动 compact | 支持 | 支持 | 已对齐 |
| `compact next` 提示 | 支持 | 支持 | 已对齐 |
| `/init` | 支持 | 支持 | 已对齐 |
| `/reset` | 支持 | 支持 | 功能已对齐，交互形式不同 |
| `/model` | 支持 | 支持 | 已对齐 |
| `/theme` | 支持 | 支持 | 已对齐 |
| `/mcp` | 支持 | 支持 | 已对齐 |
| `/status` | 支持 | 支持 | 已对齐，只在显式调用时查询余额 |
| `/ps` / `/stop` | 支持 | 支持 | 已对齐，管理后台 shell 任务 |
| `/skills` market | 支持 | 支持 | 已对齐 |
| 退出 summary | 支持 | 支持 | 已对齐，覆盖 `/exit`、`/quit`、Ctrl+D |
| 退出时清理后台任务 | 支持 | 支持 | 已对齐 |
| 删除 user/project skill | 支持 | 支持 | 已对齐 |
| built-in skill 管理显示 | 不显示 | 不显示 | 已对齐 |
| `!command` | 支持 | 支持 | 已对齐 |
| slash 命令补全 | 支持 | 支持 | 已对齐 |
| `@file` 补全 | 支持 | 支持 | 已对齐 |
| prompt history | 支持 | 支持 | 已对齐 |
| 底部状态 | 支持 | 支持 | 已对齐 |
| 换行快捷键 | `Ctrl+J` | `Ctrl+J` | 已对齐 |
| diff 显示 | 单列 | 单列 | 当前选择 |

## 尚未对齐或待确认

- Windows PowerShell 7：发版后继续验证 `!command`、文件编码、换行和工具输出。
- TUI 仍是实验入口，不作为默认 `deepy` 界面。

当前没有已知的核心日常功能缺口。

## 后续可优化

- 继续拆分 TUI 的 app/widgets 代码，降低维护成本。
- 继续优化窄屏、宽屏、侧边栏、长输出和长 prompt 的布局表现。
- 评估是否需要宽屏或并排 diff；当前单列 diff 是可接受方案。
- 继续打磨 TUI 的 skills market 视觉细节。
- 继续增强底部状态栏在窄屏下的截断和优先级策略。
- 在 Windows 验证完成后，补充跨平台结论。
