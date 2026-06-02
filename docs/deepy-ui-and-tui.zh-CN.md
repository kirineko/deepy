# Classic UI 与 Modern UI

本文说明 Deepy 的两个终端界面，并记录当前功能对齐和迁移状态。

## 界面定位

- **Classic UI**：Rich/prompt-toolkit 终端 UI。
- **Modern UI**：Textual 终端 UI。
- 两个界面共用同一套模型运行、工具调用、session、skills、MCP、后台任务和自动 compact 逻辑。
- 默认 `deepy` 命令会按 `ui.interface` 配置进入对应 UI。缺配置时默认使用 Classic UI + dark theme。
  `deepy tui` 保留为直接启动 Modern UI 的兼容命令。

## 当前视觉模型

Modern UI 使用更紧凑的 terminal-agent shell：scrollback transcript、轻量状态行、底部
composer 和按需 overlay。旧版 TUI 截图已经从本文移除，因为它们展示的是旧布局；只有在从当前实现重新截取后，才应重新加入截图。

`/status` 会按需显示用量、上下文窗口压力和 DeepSeek 余额。退出 Modern UI 时会输出和 Classic UI
一致的 compact session summary。

## Classic UI

Classic UI 基于 Rich 和 prompt-toolkit。

主要功能：

- 普通聊天和多轮 agent 执行。
- Thinking、实时 assistant 活动状态、工具调用、工具结果、紧凑 usage footer/status、错误信息渲染。
- `shell`、`read`、`modify`、`todo_write`、`AskUserQuestion`、Web、MCP 和后台任务工具输出。
- `/new`、`/resume`、`/sessions`、`/compact` 等 session/context 命令。
- `/init`、`/reset`、`/model`、`/theme`、`/ui`、`/mcp`、`/status`、`/skills` 等管理命令。
- `/ps` 查看模型启动的后台 shell 任务，`/stop` 可选择停止单个任务或全部运行中的后台任务。
- `/status` 会显示用量、上下文窗口和 DeepSeek 余额；余额接口只在显式运行 `/status` 时调用。
- `/exit`、`/quit` 和 Ctrl+D 连按两次会输出统一的 session summary。
- 退出 Deepy 时会先清理仍在运行的后台任务，再清理 MCP runtime。
- `!command` 本地命令模式。
- slash 命令补全和 `@file` 文件补全。
- prompt history。
- 自动 compact 和 `compact next` 提示。
- 底部状态显示 model、audit mode、cwd、AGENTS、MCP 数量、context 使用量。
- `Shift+Tab` 可在 `normal`、`auto`、`yolo` 三种 audit mode 间切换。
- 对有副作用的内置工具和 MCP tools 显示 audit 审批提示。审批面板使用面向任务的摘要，
  不直接展示 SDK 原始字段；文件目标在项目目录内时显示相对路径；`Write` / `Update`
  审批会显示高亮 diff 预览。大 diff 会在最终 `Approve` / `Reject` 决策区域上方提供独立
  的 review 控件。审批交互只使用上下键移动、Enter 确认当前选项、Esc 拒绝。
- 首次缺配置时引导用户配置 API key、model、base URL 和 UI。

## Modern UI

Modern UI 基于 Textual。

主要功能：

- 普通聊天和多轮 agent 执行。
- Thinking、紧凑工具调用/结果摘要和错误信息渲染。
- 工具 transcript 行只显示状态和目标摘要，默认不展示参数或输出正文。
- 成功的 `Write` / `Update` 如果带 diff，会直接显示使用项目相对路径的 diff，不额外显示工具摘要行。
- `shell`、`read`、`todo_write`、Web、MCP、`load_skill` 和后台任务工具有专门摘要效果。
- AskUserQuestion 支持单选、多选、自定义回答、取消和同 session 继续。
- `/new`、`/resume`、`/sessions`、`/compact` 已支持。
- `/init`、`/reset`、`/model`、`/theme`、`/ui`、`/mcp`、`/status`、`/skills` 已支持。
  theme/model 这类频繁短选择会以内联 transcript 决策呈现，不再打开阻塞弹框。
- `/ps`、`/stop` 已支持，用于查看后台 shell 任务，并选择停止单个任务或全部任务。
- `/status` 会显示用量、上下文窗口和 DeepSeek 余额；余额接口只在显式运行 `/status` 时调用。
- `/exit`、`/quit` 和 Ctrl+D 连按两次会在退出后输出与 Classic UI 一致的 session summary。
- `!command` 本地命令模式已支持，并复用 shell 工具块显示结果。
- slash 命令补全和 `@file` 文件补全已支持。
- 原生 Textual prompt 输入会把 CJK、emoji 和多行草稿保留在可编辑 buffer 中，不再插入 UI
  替换 token。
- prompt 文本、图片附件、生成式输入建议、slash suggestions 和 `@file` suggestions 是彼此独立的
  composer 状态。
- 图片附件显示在可编辑文本之外，但提交时仍作为 prompt image payload 传给 runner。附件行会显示当前选中项
  和键盘提示；输入框保持焦点时可用下箭头进入附件选择、左右箭头选择图片、Backspace 删除选中图片、
  上箭头回到普通输入。
- prompt history 已支持。
- 自动 compact 已支持。
- 底部状态显示 model、cwd、AGENTS、MCP 数量、context 压力和 cache 状态。每轮 token usage 不再常驻底部
  footer，可通过 `/status` 或详情视图按需查看。当用户滚离底部时，新输出会用 `New output ↓` 指示。
- 共享的 `dark` 和 `light` 设置在 Modern UI 中会映射到精选 Textual 主题：`tokyo-night` 和
  `solarized-light`。Modern UI 的 `/theme` picker 也提供 `nord`、`catppuccin-mocha`、
  `gruvbox`、`monokai`、`solarized-light`、`atom-one-light` 等 Textual-only 主题；这些主题会保存为
  `ui.textual_theme`，Classic UI 仍只需要理解 `dark` 和 `light`。
- audit 审批和 AskUserQuestion 会作为内联 transcript 决策呈现，支持键盘优先的 approve/reject、
  选项、自定义回答和取消路径。
- `/skills` 提供独立管理界面，支持 market/installed、查看、安装、卸载、更新和刷新。
- built-in skills 不在 TUI skill 管理界面里显示。
- 支持删除手工安装的 user/project skill。
- 首次缺配置时会在 TUI 内引导用户填写配置。

## 功能对比

| 功能 | Classic UI | Modern UI | 当前状态 |
| --- | --- | --- | --- |
| 默认入口 | 可配置 | 可配置 | `deepy` 使用 `ui.interface`；缺配置默认 Classic |
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
| `/ui` | 支持 | 支持 | 保存下次启动默认 UI |
| Modern 主题渲染 | Rich palette | Textual 精选主题 | `dark` / `light` 映射到 `tokyo-night` / `solarized-light`；Modern-only 主题使用 `ui.textual_theme` |
| `/mcp` | 支持 | 支持 | 已对齐 |
| `/status` | 支持 | 支持 | 已对齐，只在显式调用时查询余额 |
| `/ps` / `/stop` | 支持 | 支持 | 已对齐，管理后台 shell 任务 |
| `/skills` market | 支持 | 支持 | 已对齐 |
| 退出 summary | 支持 | 支持 | 已对齐，覆盖 `/exit`、`/quit`、Ctrl+D |
| 退出时清理后台任务 | 支持 | 支持 | 已对齐 |
| 删除 user/project skill | 支持 | 支持 | 已对齐 |
| built-in skill 管理显示 | 不显示 | 不显示 | 已对齐 |
| `!command` | 支持 | 支持 | 已对齐 |
| slash 命令补全 | 支持 | 支持 | 共用命令元数据 |
| `@file` 补全 | 支持 | 支持 | 已对齐，短片段会搜索嵌套路径 |
| 图片附件 prompt 编辑 | prompt label token | 独立附件状态 | TUI 避免在可编辑文本中插入替换 token |
| 图片附件删除 | 编辑/删除 prompt label | 输入框本地快捷键 | TUI 用下箭头进入、左右选择、Backspace 删除、上箭头返回 |
| audit 审批 | 终端内联 prompt | transcript 内联决策 | TUI runtime 审批不再用阻塞 modal |
| prompt history | 支持 | 支持 | 已对齐 |
| 底部状态 | 支持 | 支持 | 已对齐 |
| 换行快捷键 | `Ctrl+J` | `Ctrl+J` | 已对齐 |
| diff 显示 | 单列 | 单列 | 当前选择 |

## 尚未对齐或待确认

- Windows PowerShell 7：发版后继续验证 `!command`、文件编码、换行和工具输出。
- 默认 `deepy` 界面由 `ui.interface` 配置决定。

当前没有已知的核心日常功能缺口。

## 后续可优化

- 继续拆分 TUI 的 app/widgets 代码，降低维护成本。
- 继续优化窄屏、宽屏、侧边栏、长输出和长 prompt 的布局表现。
- 评估是否需要宽屏或并排 diff；当前单列 diff 是可接受方案。
- 继续打磨 TUI 的 skills market 视觉细节。
- 继续增强底部状态栏在窄屏下的截断和优先级策略。
- 在 Windows 验证完成后，补充跨平台结论。
