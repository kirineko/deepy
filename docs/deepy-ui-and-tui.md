# Classic UI And Modern UI

This page explains Deepy's two terminal interfaces and records the current
feature alignment and migration status.

## Interface Positioning

- **Classic UI**: the Rich/prompt-toolkit terminal UI.
- **Modern UI**: the Textual terminal UI.
- Both interfaces share the same model runner, tools, sessions, skills, MCP,
  background tasks, and automatic compacting logic.
- The default `deepy` command starts the UI saved in `ui.interface`. Missing
  config defaults to Classic UI with the dark theme. `deepy tui` remains as a
  compatibility command that starts Modern UI directly.

## Current Visual Model

Modern UI uses a compact terminal-agent shell: scrollback transcript,
lightweight status line, bottom composer, and on-demand overlays. The previous
TUI screenshots were removed from this page because they showed the older
layout; new screenshots should be added only after the redesigned layout is
captured from the current implementation.

`/status` shows usage, context-window pressure, and DeepSeek balance on demand.
Exiting Modern UI prints the same compact session summary as Classic UI.

## Classic UI

Classic UI is built with Rich and prompt-toolkit.

Main capabilities:

- Normal chat and multi-turn agent execution.
- Thinking, live assistant activity, tool call, tool result, compact usage
  footer/status, and error rendering.
- Tool output for `shell`, `read`, `modify`, `todo_write`,
  `AskUserQuestion`, Web, MCP, and background task tools.
- Session/context commands such as `/new`, `/resume`, `/sessions`, and
  `/compact`.
- Management commands such as `/init`, `/reset`, `/model`, `/theme`, `/ui`, `/mcp`,
  `/status`, and `/skills`.
- `/ps` for model-started background shell tasks and `/stop` for stopping one
  task or all running tasks.
- `/status` for usage, context window, and DeepSeek balance. The balance API is
  called only when `/status` is explicitly invoked.
- Unified session summary after `/exit`, `/quit`, or pressing Ctrl+D twice.
- Exit cleanup for running background tasks before MCP runtime cleanup.
- `!command` local command mode.
- Slash-command completion and `@file` completion.
- Prompt history.
- Automatic compacting and `compact next` status.
- Bottom status with model, audit mode, cwd, AGENTS, MCP count, and context usage.
- `Shift+Tab` cycles audit mode through `normal`, `auto`, and `yolo`.
- Audit approval prompts for side-effecting built-in tools and MCP tools. These
  prompts use task-focused summaries instead of raw SDK fields, show relative
  paths when a file target is under the project root, and render `Write` /
  `Update` approvals with highlighted diff previews. Large file diffs include
  a separate review control above the final `Approve` / `Reject` decision area.
  Approval prompts are navigated with Up/Down, activated with Enter, and
  rejected with Esc.
- First-run setup when API key/model/UI configuration is missing.

## Modern UI

Modern UI is the Textual interface.

Main capabilities:

- Normal chat and multi-turn agent execution.
- Thinking, compact tool call/result summaries, and error rendering.
- Tool transcript rows show status and target summaries without default
  parameter or output bodies.
- Successful `Write` / `Update` results with diffs render the diff directly
  with project-relative paths and without extra tool summary rows.
- Dedicated summaries for `shell`, `read`, `todo_write`, Web, MCP,
  `load_skill`, and background task tools.
- AskUserQuestion single-choice, multiple-choice, custom answer, cancel, and
  same-session continuation flows.
- `/new`, `/resume`, `/sessions`, and `/compact`.
- `/init`, `/reset`, `/model`, `/theme`, `/ui`, `/mcp`, `/status`, and `/skills`.
  Frequent short choices such as theme/model pickers render inline in the
  transcript instead of opening blocking modals.
- `/ps` and `/stop` for background shell tasks.
- `/status` with usage, context window, and DeepSeek balance. The balance API is
  called only when `/status` is explicitly invoked.
- Session summary after `/exit`, `/quit`, or pressing Ctrl+D twice.
- `!command` local command mode, rendered with the shell tool block.
- Slash-command completion and `@file` completion.
- Textual-native prompt input keeps CJK text, emoji, and multiline drafts in the
  editable buffer without UI replacement tokens.
- Prompt text, image attachments, generated input suggestions, slash
  suggestions, and `@file` suggestions are separate composer states.
- Image attachments are displayed outside the editable text buffer and still
  submit as prompt image payloads. The attachment row shows the selected image
  and keyboard hint; while the prompt input remains focused, press Down to enter
  attachment selection, Left/Right to choose an attachment, Backspace to remove
  it, and Up to return to normal input.
- Prompt history.
- Automatic compacting.
- Bottom status with model, cwd, AGENTS, MCP count, context pressure, and cache
  state. Per-turn token usage is kept out of the persistent footer and remains
  available from `/status` and detail views. New output below the viewport is
  shown with a changing `New output ↓` indicator.
- Shared `dark` and `light` settings map to curated Textual themes:
  `tokyo-night` and `solarized-light`. The Modern UI `/theme` picker also offers
  several Textual-only themes such as `nord`, `catppuccin-mocha`, `gruvbox`,
  `monokai`, `solarized-light`, and `atom-one-light`; those are saved as
  `ui.textual_theme` so Classic UI only needs to understand `dark` and
  `light`.
- Audit approvals and AskUserQuestion prompts render as inline transcript
  decisions with keyboard-first approve/reject, option, custom-answer, and
  cancel paths.
- Dedicated `/skills` management UI with market/installed tabs, viewing,
  installation, uninstallation, updating, and refresh.
- Built-in skills are not shown in the TUI skill management UI.
- User/project skill deletion for manually installed skills.
- In-TUI first-run setup when configuration is missing.

## Feature Comparison

| Feature | Classic UI | Modern UI | Current status |
| --- | --- | --- | --- |
| Default entrypoint | Configurable | Configurable | `deepy` uses `ui.interface`; missing config defaults to Classic |
| Normal chat | Supported | Supported | Aligned |
| Thinking display | Supported | Supported | Aligned |
| Tool call display | Supported | Supported | Aligned |
| AskUserQuestion | Supported | Supported | Aligned |
| Session resume | Supported | Supported | Aligned |
| `/compact` | Supported | Supported | Aligned |
| Automatic compact | Supported | Supported | Aligned |
| `compact next` status | Supported | Supported | Aligned |
| `/init` | Supported | Supported | Aligned |
| `/reset` | Supported | Supported | Same capability, different interaction form |
| `/model` | Supported | Supported | Aligned |
| `/theme` | Supported | Supported | Aligned |
| `/ui` | Supported | Supported | Persists default UI for the next startup |
| Modern theme rendering | Rich palette | Textual curated theme | `dark` / `light` map to `tokyo-night` / `solarized-light`; Modern-only themes use `ui.textual_theme` |
| `/mcp` | Supported | Supported | Aligned |
| `/status` | Supported | Supported | Aligned; balance is queried only on explicit call |
| `/ps` / `/stop` | Supported | Supported | Aligned; manages background shell tasks |
| `/skills` market | Supported | Supported | Aligned |
| Exit summary | Supported | Supported | Aligned for `/exit`, `/quit`, and Ctrl+D |
| Exit background task cleanup | Supported | Supported | Aligned |
| Delete user/project skill | Supported | Supported | Aligned |
| Built-in skill management display | Hidden | Hidden | Aligned |
| `!command` | Supported | Supported | Aligned |
| Slash-command completion | Supported | Supported | Shared command metadata |
| `@file` completion | Supported | Supported | Aligned; short fragments search nested paths |
| Image attachment prompt editing | Prompt label tokens | Separate attachment state | TUI avoids editable replacement tokens |
| Image attachment deletion | Edit/remove prompt label | Prompt-local shortcuts | TUI uses Down to enter, Left/Right to choose, Backspace to delete, Up to return |
| Audit approval | Inline terminal prompt | Inline transcript decision | TUI no longer interrupts with runtime modal |
| Prompt history | Supported | Supported | Aligned |
| Bottom status | Supported | Supported | Aligned |
| Newline shortcut | `Ctrl+J` | `Ctrl+J` | Aligned |
| Diff display | Single column | Single column | Current choice |

## Known Gaps Or Pending Checks

- Windows PowerShell 7: continue validating `!command`, file encoding, newline
  behavior, and tool output after releases.
- The default `deepy` interface is configurable through `ui.interface`.

There are no known core daily-feature gaps at this time.

## Future Improvements

- Continue splitting TUI app/widgets code to reduce maintenance cost.
- Improve narrow-screen, wide-screen, sidebar, long-output, and long-prompt
  layout behavior.
- Evaluate whether wide or side-by-side diff views are needed; the current
  single-column diff is acceptable.
- Continue polishing the TUI skills market visual details.
- Improve bottom-status truncation and priority strategy on narrow screens.
- Add a stronger cross-platform conclusion after Windows validation is complete.
