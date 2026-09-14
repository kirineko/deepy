<p align="center">
  <img src="asset/deepy-logo.webp" alt="Deepy logo" width="144">
</p>

<h1 align="center">Deepy</h1>

<p align="center">
  A terminal-native coding agent for real project work.
</p>

<p align="center">
  <a href="https://deepy.kirineko.tech/"><strong>Install</strong></a>
  ·
  <a href="https://kirineko.github.io/deepy/">Home</a>
  ·
  <a href="README.zh-CN.md">中文</a>
</p>

![Deepy terminal welcome screen](asset/welcome.webp)

## What Deepy Is

Deepy is a Python CLI coding agent for real project work. It stays in your
terminal and combines OpenAI Agents SDK tool orchestration, project Rules,
Agent Skills, MCP, subagents, sessions, and visible UI to read code, edit files,
run commands, search the web, and resume long tasks. It is DeepSeek-first while
also supporting OpenAI-compatible providers.

## Why Use It

- **DeepSeek-first agent loop**: tuned for DeepSeek V4 thinking mode while still
  supporting DeepSeek, MiMo, Kimi and CLI Proxy through the Responses API.
- **Transparent terminal execution**: thinking, tool calls, diffs, shell output,
  usage, and context pressure stay visible in the transcript.
- **Project memory and continuity**: `AGENTS.md` rules, local SQLite sessions,
  `/resume`, `/compact`, automatic compacting, and context-window status keep
  long project work recoverable.
- **Extensible agent ecosystem**: Agent Skills, MCP servers, subagents, and
  skill-market installation give Deepy reusable workflows beyond built-in tools.
- **Practical coding controls**: stale-write protection, direct `!cmd` local
  commands, managed background tasks, and `/ps` / `/stop` keep local execution
  reviewable.
- **Cross-platform shell support**: POSIX shell, PowerShell, cmd, Windows paths,
  UTF-8 output, CRLF editing, and non-interactive Windows local command mode.

## Quick Start

1. Install `uv`:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2. Install Deepy:

```bash
uv tool install deepy-cli
```

3. Start Deepy in a project:

```bash
cd your-project
deepy
```

If Deepy has not been configured yet, the first run guides you through provider,
API key, model, and theme setup. You can later run `deepy config setup` to
reconfigure manually.

Upgrade or uninstall:

```bash
uv tool upgrade deepy-cli
uv tool uninstall deepy-cli
```

## First Session

Try requests like these inside `deepy`:

```text
Summarize this project and point out the main entry points.
Read @src/app.py and explain how the request flow works.
Fix the failing test, run the focused test, and summarize the diff.
Search the web for the current API behavior, then update the integration notes.
```

Useful interactive inputs:

```text
@src/app.py       Mention a file in the current project
!pytest -q        Run a local non-interactive command directly
/model            Select provider, model, and thinking mode
/status           Show usage, context pressure, and DeepSeek balance
/resume           Resume a previous project session
/new              Start a fresh session
/compact          Compact the active session context
/mcp              Show MCP server status and tools
/skills           Manage local and market Skills
/ps               Show managed background shell tasks
/stop             Choose background shell tasks to stop
Esc               Interrupt the current model turn
Ctrl+D            Press twice to quit
```

## What It Looks Like

### Terminal-Centered Agent Loop

Deepy keeps model reasoning, WebFetch, shell output, and status lines visible in
one transcript.

![Deepy thinking, WebFetch, and shell output](asset/webfetch-shell-thinking.webp)

### Code Editing With Reviewable Diff

File edits are shown with path information and readable diff output.

![Deepy edit diff preview](asset/edit-diff.webp)

### Search, Fetch, And Local Commands

Use WebSearch / WebFetch for external context, `@` for file mentions, and `!`
for direct local commands.

![Deepy web research workflow](asset/websearch.webp)

## Classic UI And Modern UI

Deepy has two peer terminal interfaces. Classic UI is the Rich/prompt-toolkit
terminal UI, and Modern UI is the Textual terminal UI. The default `deepy`
command starts the UI saved in `ui.interface`; missing config defaults to
Classic UI with the dark theme. The compatibility command below still starts
Modern UI directly:

```bash
deepy tui
```

Modern UI has a compact scrollable transcript, lightweight status line,
Textual-native composer, live assistant/tool activity states, compact tool
summary rows, slash-command and `@file` suggestions, inline audit/model/theme
choices, status/help screens, and a Deepy-owned diff view. Use `/ui` in either
interface to change the default UI for the next `deepy` startup.

`/status` shows session/project usage, context-window pressure, and DeepSeek
balance in one panel. Exiting Modern UI prints the same compact session summary
as Classic UI. Prompt text, image attachments, generated input
suggestions, slash suggestions, and file suggestions are separate composer
states, so UI-only attachment labels are not written into the editable prompt
buffer. Attached images appear in an attachment row with prompt-local keyboard
shortcuts: press Down to enter attachment selection, Left/Right to choose,
Backspace to remove, and Up to return to normal input. The shared `dark` /
`light` setting maps to curated
Textual themes in Modern UI, with `dark` defaulting to `tokyo-night`; Modern UI can
also save a Textual-only `ui.textual_theme` override from `/theme`.

See [docs/deepy-ui-and-tui.md](docs/deepy-ui-and-tui.md) for the full feature
comparison and current limitations.

## Rules

Rules are project and personal instructions that shape how Deepy should work.
Deepy automatically loads them from `AGENTS.md` files:

- `~/.deepy/AGENTS.md` for Deepy-wide personal guidance
- `AGENTS.md` files from the git root down to the current working directory

Project `AGENTS.md` files are loaded from broad to specific. A file in a nested
directory appears after the repository root file and takes precedence when rules
conflict. Direct user instructions still take precedence over loaded
`AGENTS.md` guidance.

Run `/init` in the interactive terminal to have Deepy inspect the repository and
create or refresh the project root `AGENTS.md`.

## Skills

Skills are reusable capability packs. Deepy discovers three kinds:

- **Project skills**: `<project>/.agents/skills/<name>/SKILL.md`. These are
  shared with the current repository and take priority over user or built-in
  skills with the same name.
- **User skills**: `~/.agents/skills/<name>/SKILL.md`. These are personal
  skills available across projects and override built-in skills with the same
  name.
- **Built-in skills**: packaged with Deepy for common workflows. They are always
  available, but they are not editable or uninstallable through the skill UI.

Skills use the standard Agent Skills progressive-disclosure flow: Deepy shows
Skill metadata first, and the model reads the full `SKILL.md` only when the task
matches that skill.

The skill market is a curated source for installable Skills. Market-installed
Skills can be installed into user or project scope, updated, and uninstalled
through Deepy's Skills UI. Deepy records market-installed Skill metadata under
`~/.deepy/skill-market/`.

Use `/skills` to manage local and market Skills, or invoke a Skill directly:

```text
/skills
/<name> [request]
```

![Deepy Skills market](asset/skill-market.webp)

## MCP

Deepy can load MCP servers through the OpenAI Agents SDK. MCP is how you connect
external tools such as search providers, databases, local services, or
organization-specific context providers.

Most users only need `~/.deepy/mcp.json`. Project-level MCP configuration is
ignored by default because stdio MCP servers can start local commands. Enable it
only for repositories you trust.

See [docs/mcp.md](docs/mcp.md) for setup, fields, search preference, subagent
MCP inheritance, and troubleshooting.

## Trust Boundaries

- File edits are rendered with path information and readable diffs.
- Existing file replacement uses stale-write protection.
- `!cmd` is direct local command mode; model-started shell commands are shown in
  the transcript.
- MCP stdio servers start local commands. Project MCP config is ignored by
  default and should only be enabled for repositories you trust.
- Built-in subagents do not receive source mutation tools by default.
- The tester subagent uses constrained `test_shell`, not raw unrestricted
  `shell`.

## Learning Resources

| Topic | English | Chinese |
| --- | --- | --- |
| Tutorial videos | [docs/tutorial-videos.md](docs/tutorial-videos.md) | [docs/tutorial-videos.zh-CN.md](docs/tutorial-videos.zh-CN.md) |
| MCP setup and troubleshooting | [docs/mcp.md](docs/mcp.md) | [docs/mcp.zh-CN.md](docs/mcp.zh-CN.md) |
| Subagents and custom subagents | [docs/subagents.md](docs/subagents.md) | [docs/subagents.zh-CN.md](docs/subagents.zh-CN.md) |
| Classic UI and Modern UI | [docs/deepy-ui-and-tui.md](docs/deepy-ui-and-tui.md) | [docs/deepy-ui-and-tui.zh-CN.md](docs/deepy-ui-and-tui.zh-CN.md) |

## Command Reference

```bash
deepy --version
deepy config setup
deepy config reset
deepy config theme
deepy doctor
deepy doctor --live --json
deepy status
deepy tui
deepy skills list
deepy skills show <name>
deepy sessions list
deepy sessions show <session-id>
deepy run "summarize this project"
```

Deepy stores active project sessions in a local SQLite session store. Historical
JSONL session files from older Deepy versions are not imported, listed, or
resumed by current session commands.

Inside the interactive terminal:

```text
/help                   Show interactive help
/model                  Select provider, model, and thinking mode
/status                 Show usage, context pressure, and DeepSeek balance
/resume                 Resume a previous project session
/new                    Start a fresh session
/compact                Compact the active session context
/mcp                    Show MCP server status and tools
/skills                 Manage local and market Skills
/<name> [request]       Invoke a Skill directly
/init                   Create or update project AGENTS.md
/theme                  Show or change terminal UI theme
/ui                     Show or change Classic/Modern UI
/ps                     Show managed background shell tasks
/stop                   Choose background shell tasks to stop
```

## Configuration

Deepy stores configuration in `~/.deepy/config.toml`. The interactive first-run
setup creates this file for most users.

Minimal resolved shape:

```toml
config_version = 2
active_provider = "deepseek"

[providers.deepseek]
api_key_env = "DEEPSEEK_API_KEY"
model = "deepseek-flash"
base_url = "https://api.deepseek.com"
reasoning = "max"

[context]
window_tokens = 1048576
compact_trigger_ratio = 0.8
reserved_context_tokens = 50000
compact_preserve_recent_messages = 2

[audit]
mode = "yolo" # normal, auto, or yolo

[ui]
interface = "classic" # classic or modern
theme = "dark" # dark or light
```

Audit modes control side-effect approval. `normal` asks before managed text
writes, shell commands, background task stops, and MCP tool calls. `auto`
auto-approves managed text writes but still asks for commands and untrusted MCP
tools. `yolo` preserves the high-autonomy default.

Manual configuration commands:

```bash
deepy config setup
deepy config init --provider deepseek --model deepseek-flash
deepy config theme light
```

| Provider | Model IDs | Thinking |
|---|---|---|
| DeepSeek | `deepseek-flash` (V4.1 Flash) | `none`, `high`, `max` |
| MiMo | `mimo-v2.5`, `mimo-v2.5-pro` | `disabled`, `enabled` |
| Kimi | `kimi-k3` | `low`, `high`, `max` |
| CLI Proxy | `gpt-6-astra`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5` | `none`, `low`, `medium`, `high`, `xhigh` |

Each provider keeps its own key, URL, model and thinking settings. `/model provider <id>` restores its saved profile; leaving the setup password blank preserves the saved key. Default environment variables are `DEEPSEEK_API_KEY`, `MIMO_API_KEY`, `KIMI_API_KEY` (with `MOONSHOT_API_KEY` fallback), and `CLI_PROXY_API_KEY`. Environment keys take precedence without being written back. The generic `DEEPY_API_KEY` override is no longer supported.

Old shared `[model]` configuration requires setup again. Keep a copy for manual recovery; Deepy does not automatically migrate or overwrite it. Full reset rebuilds configuration.

Conversation, subagents, suggestions and compaction use Responses. Built-in WebSearch independently calls DeepSeek Messages native search, requiring a separate DeepSeek key for every conversation provider. Configured Tavily/search MCP preference remains effective; WebFetch still retrieves URLs locally over HTTP. Search usage is displayed separately and included in session API consumption.

All catalog models except MiMo 2.5 Pro accept images. Both UIs support multiple pasted images and image-only prompts: PNG/JPEG/WebP/GIF, 10 MiB per image, eight images per turn, and 32 MiB for the complete encoded request. Switching to a text-only model preserves images and asks you to remove draft attachments, switch back, or start a text-only session. Native audio, video, PDF input and media generation are not supported in this update.

Batch `Read` accepts at most eight images; larger image batches return a tool error so the agent can retry with fewer files.

Suggestions use the current provider's fixed `deepseek-flash`/none, `mimo-v2.5`/disabled, `kimi-k3`/low, or `gpt-5.6-luna`/none, with separate usage accounting.

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check
uv run ty check src
uv build
```

The Python package is built from `src/deepy`. GitHub Pages files and screenshot
assets live outside the package directory and are not included in the wheel.
