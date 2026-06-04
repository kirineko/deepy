## 1. TUI Structure And Shared State

- [x] 1.1 Audit current `src/deepy/tui/` app, widgets, state, runner, and diff modules against this change's specs.
- [ ] 1.2 Extract focused TUI modules for command handling, transcript behavior, tool widgets, screens, and prompt history without changing external CLI entrypoints.
- [x] 1.3 Introduce a small shared TUI state/controller boundary for active session id, busy state, loaded skills, pending questions, selected theme/model state, and transient UI flags.
- [x] 1.4 Preserve the existing `deepy tui` command path and the default `deepy` Rich/prompt-toolkit path.

## 2. Command Discovery And Auxiliary Screens

- [x] 2.1 Add Textual command provider support for Deepy commands grouped by conversation, session, skills, model/theme, status/help, and MCP.
- [x] 2.2 Upgrade prompt slash suggestions so known commands insert predictably and unknown slash commands do not start accidental model turns.
- [x] 2.3 Implement `/help` as a Textual help/status surface showing commands, keybindings, model, session, loaded skills, config path, and core TUI state.
- [x] 2.4 Implement `/status` as a dismissible Textual status surface with project root, model, reasoning, active session, context status, MCP status, loaded skills, and theme.
- [x] 2.5 Implement `/theme` selection for `auto`, `dark`, and `light`, using existing settings persistence and clear restart/update messaging.
- [x] 2.6 Implement `/model` model and reasoning selection with cancellation preserving current settings.
- [x] 2.7 Add explicit unsupported messages for any stable slash command that remains unimplemented in TUI after this pass.
- [x] 2.8 Replace the `/init` unsupported path with TUI model-turn handling that uses `build_agents_init_prompt()`.
- [x] 2.9 Replace the `/reset` unsupported path with a Textual-native config reset/setup form that writes config through existing config helpers.
- [x] 2.10 Update TUI command discovery, help, and slash suggestions so `/init`, `/reset`, local command mode, and full `/skills` behavior are described accurately.

## 3. AskUserQuestion Continuation

- [x] 3.1 Trace stable UI AskUserQuestion continuation and identify the reusable session continuation path.
- [x] 3.2 Implement a Textual question surface for normalized AskUserQuestion metadata with keyboard navigation and focused entry.
- [x] 3.3 Support single-select answer submission and transcript recording.
- [x] 3.4 Support multi-select answer submission and transcript recording.
- [x] 3.5 Support custom-answer input when the question offers or requires a free-form answer path.
- [x] 3.6 Support cancellation with recoverable session state and clear transcript/status feedback.
- [x] 3.7 Wire pending `RunSummary.pending_questions` into the question surface and continue the same session id after answer submission.

## 4. Session And Context Commands

- [x] 4.1 Implement `/new` in TUI to clear the active session id and reset per-session TUI state without changing global settings.
- [x] 4.2 Implement `/sessions` as a navigable Textual sessions surface using existing Python JSONL session entries.
- [x] 4.3 Implement `/resume [ID]` direct resume and picker-based resume.
- [x] 4.4 Restore visible transcript history after resume when session items are available.
- [x] 4.5 Implement `/compact [focus]` using the existing durable compaction flow.
- [x] 4.6 Render compaction running, success, no-op, and failure states without leaving the TUI.

## 5. Tool-Specific TUI Widgets

- [x] 5.1 Create a reusable expandable tool block model with summary, status, metadata, hidden details, keyboard expansion, and pointer expansion.
- [x] 5.2 Implement a shell result block showing command, cwd, exit code, status, duration when known, stdout, stderr, truncation, timeout, and interruption state.
- [x] 5.3 Implement a read result preview block showing path, line/page range, syntax-aware preview when available, and folded large content.
- [x] 5.4 Implement todo projection so `todo_write` updates a concise transcript progress board and side-panel projection.
- [x] 5.5 Implement WebSearch and WebFetch result treatments with source or URL metadata and expandable result body.
- [x] 5.6 Implement MCP status/tool result treatment with server/tool identity, success/failure/cleanup/unavailable states, concise error display, and quiet stdio stderr in TUI runs.
- [x] 5.7 Preserve existing model-facing tool names, argument schemas, and JSON result contracts.
- [x] 5.8 Implement TUI `!command` detection before slash/model prompt handling, including empty-command usage feedback.
- [x] 5.9 Reuse `run_local_command()`, `shell_tool_result_json()`, and `build_synthetic_shell_transcript_items()` for TUI local command execution, rendering, and persistence.
- [x] 5.10 Preserve the existing Windows local-command boundary in TUI: PowerShell/PowerShell Core run through non-interactive subprocess pipes, no PTY/pywinpty, sanitized output, normalized line endings, and shell metadata.
- [x] 5.11 For Windows `cmd.exe`, either reuse the existing non-interactive `cmd` dialect path or show a clear unsupported message; never send `!command` to the model.
- [x] 5.12 Ensure local command results render through the same TUI shell block used by model-invoked `shell` tool results.

## 5A. Skill Market And Skill Management Parity

- [x] 5A.1 Add a Textual skill management surface for `/skills` without arguments with installed/local and market views.
- [x] 5A.2 Support `/skills search QUERY` in TUI with market results or concise market access errors.
- [x] 5A.3 Support `/skills install NAME` in TUI, including install-scope selection when needed.
- [x] 5A.4 Support `/skills uninstall NAME`, `/skills installed`, `/skills update NAME`, and `/skills update --all` in TUI using existing skill market helpers.
- [x] 5A.5 Support skill detail viewing in a Textual screen without dumping full `SKILL.md` content into the main transcript.
- [x] 5A.6 Keep loaded skill state synchronized when installing, uninstalling, removing, or using skills from the TUI surface.

## 6. Transcript, Diff, And Visual Polish

- [x] 6.1 Implement controlled auto-scroll that distinguishes bottom-anchored output from user history reading.
- [x] 6.2 Add a new-output indicator or equivalent affordance when output arrives while the user is scrolled away from the bottom.
- [x] 6.3 Add prompt input history navigation without corrupting the current draft.
- [x] 6.4 Add hunk boundaries and hunk navigation to TUI diff blocks.
- [x] 6.5 Add hunk fold/unfold support to TUI diff blocks.
- [x] 6.6 Add terminal-width wrapping or folding for long changed diff lines.
- [ ] 6.7 Add optional wide-layout diff behavior only if the single-column fallback stays clean.
- [x] 6.8 Normalize visual label treatment for thinking and tools with shared label styling and semantic state colors.
- [ ] 6.9 Verify narrow and wide layouts avoid overlapping text, broken prompt areas, or unstable side-panel behavior.

## 7. Tests And Validation

- [x] 7.1 Add Textual headless tests for command provider discovery, slash command dispatch, and unsupported command messages.
- [x] 7.2 Add Textual headless tests for `/help`, `/status`, `/theme`, and `/model` surfaces.
- [x] 7.3 Add AskUserQuestion TUI tests for single-select, multi-select, selected markers, non-duplicated tool chrome, custom answer Enter submission, cancellation, and same-session continuation.
- [x] 7.4 Add session tests for `/new`, `/sessions`, `/resume`, transcript restoration, and `/compact`.
- [x] 7.5 Add tool widget tests for shell, read, todo progress, web, MCP, MCP stdio noise suppression, waiting-for-user, expansion, and truncation.
- [x] 7.6 Add diff tests for wrapping, hunk navigation, hunk folding, truncation, narrow width, and wide width.
- [x] 7.7 Add controlled auto-scroll and input-history regression tests.
- [x] 7.8 Run focused TUI tests.
- [x] 7.9 Run `uv run pytest -q`.
- [x] 7.10 Run `uv run ruff check`.
- [x] 7.11 Run `uv run ty check src`.
- [x] 7.12 Run `openspec validate polish-experimental-textual-tui --type change --strict`.
- [ ] 7.13 Manually verify `deepy tui` on macOS.
- [ ] 7.14 Manually verify `deepy tui` on Windows Terminal with PowerShell 7 before treating the TUI as release-ready.
- [x] 7.15 Add TUI tests for `/init`, including generated AGENTS.md initialization prompt routing and no accidental unsupported message.
- [x] 7.16 Add TUI tests for `/reset` form cancellation, validation, config writing, settings reload, and theme update behavior.
- [x] 7.17 Add TUI tests for `!command` empty command, successful command, failed command, session persistence, and no model invocation.
- [x] 7.18 Add TUI tests for simulated Windows PowerShell local command mode using the existing pipe-based runner metadata.
- [x] 7.19 Add TUI tests for Windows `cmd.exe` behavior, either proving the reused non-interactive `cmd` path or proving the explicit unsupported message.
- [x] 7.20 Add TUI tests for skill market search/install/uninstall/installed/update and skill management screen navigation.
- [x] 7.21 Re-run focused TUI tests after the remaining parity work.
- [x] 7.22 Re-run `uv run pytest -q`, `uv run ruff check`, `uv run ty check src`, and `openspec validate polish-experimental-textual-tui --type change --strict`.
