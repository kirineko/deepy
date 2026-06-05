## 1. Guard rail and baseline

- [x] 1.1 Add `tests/architecture/__init__.py` and `tests/architecture/test_module_size.py` that walks `src/deepy/**/*.py` and asserts the three tracked modules are under the ceiling; start in report-only mode if any are still oversized.
- [x] 1.2 Record the current line counts of `builtin.py`, `terminal.py`, `app.py` in the test as the baseline to drive down.
- [x] 1.3 Run `uv run pytest tests/architecture -q` to confirm the guard executes.

## 2. Decompose `ui/classic/terminal.py` (lowest risk first)

- [x] 2.1 Extract `runtime_workers.py` (async worker, main-thread bridge, startup-state/handle classes); import back into `terminal.py`.
- [x] 2.2 Extract `startup.py` (version-update check, theme load, prompt session, mcp runtime, input suggestion).
- [x] 2.3 Extract `approvals.py` (terminal approval resolver/collection, preflight diff, prepare prompt, local command handling).
- [x] 2.4 Extract `esc_watch.py` (ESC interrupt watchers, background stop selection, background cleanup).
- [x] 2.5 Extract `stream_render.py` (`TerminalStreamRenderer`, inline/silent runtime status, `_should_use_inline_runtime_status`).
- [x] 2.6 Extract `slash_commands.py` (`_handle_slash_command`, `_handle_compact_command`, resume/history printing).
- [x] 2.7 Extract `exit_summary.py` (exit summary + session cost start/end/footer).
- [x] 2.8 Extract `footer.py` (toolbar, status footer, context footer, usage footer, token-format helpers).
- [x] 2.9 Extract `printing.py` (print user/assistant/stream/tool-debug, status line).
- [x] 2.10 Extract `questions.py` (pending-question response collection and prompting).
- [x] 2.11 Re-export every private symbol that `tests/ui/classic/test_terminal.py` imports (`_handle_slash_command`, `_print_assistant_output`, `_print_stream_event`, `_print_user_input`, `_build_status_footer`, `_format_context_footer`, `_print_usage_footer`, `_run_once_with_status`, `_collect_pending_question_response`, `_format_duration_ms`, `_format_stream_token_count_short`, `_format_token_count_short`, `_tool_output_text`, `_working_status_text`) and keep the `InputFunc` alias + `run_interactive` in `terminal.py`.
- [x] 2.12 Confirm `terminal.py` is under 800 lines; run `uv run ruff check src tests`, `uv run ty check src`, `uv run pytest tests/ui/classic -q`.

## 3. Decompose `tools/builtin.py` — free functions first

- [x] 3.1 Extract `tools/constants.py` (module-level constants such as `DEFAULT_LINE_LIMIT`, `MAX_BASH_OUTPUT_CHARS`, `MAX_LINE_LENGTH`); re-export from `builtin.py` for `tests/tools/test_tools.py`.
- [x] 3.2 Extract `tools/payloads.py` (frozen helper dataclasses shared across read/mutation/web).
- [x] 3.3 Extract `tools/mutation_policy.py` (path resolution, mutation policy/decision, sensitive-target checks).
- [x] 3.4 Extract `tools/text_match.py` (occurrence finding, loose-escape, similarity/bigrams, closest match).
- [x] 3.5 Extract `tools/text_io.py` (unified diff, encoding detection, atomic write, backups, newline handling).
- [x] 3.6 Extract `tools/payload_parsing.py` (v3 read/update parsing, notebook formatting).
- [x] 3.7 Extract `tools/media.py` (PDF read/page-range, image mime/follow-up message).
- [x] 3.8 Extract `tools/shell_command.py` (line-ending/truncate/output capture, shell command + args construction); sub-split if it exceeds ~400 lines.
- [x] 3.9 Create `tools/web/` package; extract `query.py`, `search_parse.py`, `fetch_html.py`.
- [x] 3.10 Run `uv run ruff check`, `uv run ty check src`, `uv run pytest tests/tools -q` after the free-function moves.

## 4. Decompose `tools/builtin.py` — split `ToolRuntime` into mixins

- [x] 4.1 Add `tools/runtime/__init__.py` and `tools/runtime/state.py` (typing-only state base declaring shared attribute annotations).
- [x] 4.2 Extract `runtime/read.py` (`ReadToolsMixin`: `_read_file_result`, `read`).
- [x] 4.3 Extract `runtime/mutation_preflight.py` (`preflight_file_mutation`, `preflight_write`, `preflight_update`, `_plan_update_file`).
- [x] 4.4 Extract `runtime/mutation_apply.py` (`_write_result`, `write_v3`, `update`).
- [x] 4.5 Extract `runtime/shell.py` (`shell`, `test_shell`, `_wait_for_shell_process`, `_should_interrupt`, `_shell_background`).
- [x] 4.6 Extract `runtime/tasks.py` (`task_list`, `task_output`, `task_stop`).
- [x] 4.7 Extract `runtime/web.py` (`web_search`, `web_fetch`, `_web_search_builtin`, `_try_duckduckgo_search`, `_try_searxng_search`).
- [x] 4.8 Extract `runtime/interaction.py` (`search`, `ask_user_question`, `todo_write`, `load_skill`).
- [x] 4.9 Reassemble `ToolRuntime(*mixins)` in `builtin.py` keeping all dataclass fields + `__post_init__`; verify `tools/__init__.py` and `tools/agents.py` still import `ToolRuntime` unchanged.
- [x] 4.10 Confirm `builtin.py` is under 800 lines; run `uv run ruff check`, `uv run ty check src`, `uv run pytest tests/tools tests/llm -q`.

## 5. Decompose `ui/modern/app.py` into mixins (highest risk last)

- [x] 5.1 Extract `app_helpers.py` (module-level helpers below the class).
- [x] 5.2 Extract `app_commands.py` (`_run_tui_command`, help/status markdown, theme/ui/model/view/reset/input-suggestion commands); sub-split reset if needed.
- [x] 5.3 Extract `app_skills.py` (all `_skills_*` methods + skill screen action handlers).
- [x] 5.4 Extract `app_streaming.py` (`run_model_turn`, `on_stream_event`, turn complete/failed, `_handle_stream_event`, stream progress/status).
- [x] 5.5 Extract `app_transcript.py` (append/replace/insert/clear/restore transcript, assistant delta, scroll/anchor helpers).
- [x] 5.6 Extract `app_interaction.py` (approval resolver, tool blocks, preflight diff, inline audit/choice, question handlers, interaction sheet).
- [x] 5.7 Extract `app_status.py` (status update/bar/context, session-entry cache, session cost, exit summary).
- [x] 5.8 Extract `app_sessions.py` (new/show/resume/choose/compact session, background-task stop).
- [x] 5.9 Reassemble `DeepyTuiApp(*mixins, App[None])` keeping `BINDINGS`/`CSS`/`COMMANDS`/`TITLE`/reactive `state`/`__init__`/`compose`/`on_mount` and lifecycle `action_*`/`on_*` on the concrete class; verify `ui/modern/commands.py` and `ui/modern/runner.py` still import `DeepyTuiApp`.
- [x] 5.10 Confirm `app.py` is under 800 lines; run `uv run ruff check`, `uv run ty check src`, `uv run pytest tests/ui/modern -q`.

## 6. Finalize

- [x] 6.1 Flip the module-size guard test to hard-fail at the 800-line ceiling for all three modules.
- [x] 6.2 Run the full gate: `uv run pytest -q`, `uv run ruff check src tests`, `uv run ty check src`.
- [x] 6.3 Run `openspec validate split-oversized-modules --type change --strict` and fix any issues.
- [x] 6.4 Update `AGENTS.md`/docs only if the size ceiling or guard location needs documenting; otherwise leave behavior docs unchanged (no observable behavior changed).
