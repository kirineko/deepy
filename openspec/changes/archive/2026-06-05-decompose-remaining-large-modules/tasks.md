## 1. Baseline and guard prep

- [x] 1.1 Record current line counts as baselines: `tools/agents.py` (1079),
  `config/settings.py` (1070), `llm/runner.py` (943).
- [x] 1.2 Confirm `tests/architecture/test_module_size.py` is green before changes.

## 2. Decompose `tools/agents.py` (lowest risk first)

- [x] 2.1 Extract `tools/tool_args.py` (`_tool_args`, `_string_arg`,
  `_optional_string_arg`, `_int_arg`, `_optional_int_arg`, `_bool_arg`,
  `_invalid_tool_arguments_result`, `_merge_tool_result_metadata`).
- [x] 2.2 Extract `tools/arg_repair.py` (`_repair_tool_arguments`,
  `_quote_unquoted_read_ranges`, `_replace_unquoted_python_literals`,
  `_remove_trailing_commas`, `_is_identifier_char`).
- [x] 2.3 Extract `tools/schema_compat.py` (`make_mimo_compatible_tool_schema`,
  `_remove_nullable_required_fields`, `_schema_type_allows_null`,
  `_validate_args_against_schema`, `_schema_value_matches`, `_schema_enum_matches`).
- [x] 2.4 Keep `build_function_tools` and `_test_shell_*` in `agents.py`; re-export
  `build_function_tools` and `make_mimo_compatible_tool_schema`.
- [x] 2.5 Confirm `agents.py` < 800 lines; run `uv run ruff check src tests`,
  `uv run ty check src`, `uv run pytest tests/tools tests/audit -q`.

## 3. Decompose `llm/runner.py`

- [x] 3.1 Audit which helpers reference monkeypatched names
  (`ensure_context_ready`, `log_debug_event`, `launch_notify_script`,
  `log_api_error`); ensure those callers stay in `runner.py` or resolve names at
  call time through the runner module.
- [x] 3.2 Extract `llm/runner_approvals.py` (`_approval_decisions`,
  `_pending_approval_from_interruption`, `_approval_preflight`,
  `_approval_tool_name`, `_approval_arguments`, `_approval_call_id`,
  `_approval_server_name`, `_approval_action_kind`).
- [x] 3.3 Extract `llm/runner_errors.py` (`format_deepseek_api_error`,
  `DeepSeekErrorStatus`, `_api_status_error_message`, `_api_status_error_response`,
  `_api_error_body_field`, `_safe_int`).
- [x] 3.4 Extract `llm/runner_interrupt.py` (`_cancel_stream_result`,
  `_watch_stream_interrupt`, `_finish_interrupt_task`,
  `_reconcile_interrupted_session_tail`, `_is_user_prompt_item`,
  `_item_text_content`, `_interrupted_tool_output_items`,
  `_missing_output_items_for_call`, `_function_call_id`,
  `_function_call_output_id`, `_interrupted_marker_item`,
  `_is_interrupt_marker_item`, `_pending_questions_from_tool_output`).
- [x] 3.5 Keep `run_prompt_once`, `RunSummary`, `_run_status`,
  `_resolve_loaded_skills`, `_max_turns_output` in `runner.py`; re-export
  `run_prompt_once`, `RunSummary`, `DEFAULT_MAX_TURNS`, `format_deepseek_api_error`.
- [x] 3.6 Confirm `runner.py` < 800 lines; run `uv run ruff check src tests`,
  `uv run ty check src`, `uv run pytest tests/llm tests/sessions tests/audit -q`.

## 4. Decompose `config/settings.py`

- [x] 4.1 Extract `config/providers.py` (`ModelInfo`, `ProviderInfo`,
  `PROVIDER_CATALOG`, provider predicates/queries, reasoning/thinking helpers,
  `normalize_reasoning_effort`, `mask_secret`, `_as_*` coercers).
- [x] 4.2 Extract `config/schema.py` (all config dataclasses and their
  `from_mapping`: `ModelConfig`, `ContextConfig`, `LoggingConfig`, `NotifyConfig`,
  `WebSearchToolConfig`, `TestShellToolConfig`, `ToolsConfig`, `McpWebSearchConfig`,
  `McpConfig`, `UiConfig`, `Settings`).
- [x] 4.3 Extract `config/config_io.py` (`load_settings`, `settings_to_toml_dict`,
  `write_config`, `update_config_*` family, `ui_*_number`/`ui_*_from_selection`,
  `is_valid_*` predicates, `_read_toml_mapping`, `_write_private_toml`,
  `_drop_empty`).
- [x] 4.4 Make `settings.py` a thin re-export hub so both `deepy.config.X` and
  `deepy.config.settings.X` resolve; keep `config/__init__.py` unchanged.
- [x] 4.5 Verify no `config/` import cycle (`providers` ← `schema` ← `config_io`).
- [x] 4.6 Confirm `settings.py` < 800 lines; run `uv run ruff check src tests`,
  `uv run ty check src`, `uv run pytest tests/config tests/llm tests/status
  tests/session_cost tests/sessions -q`.

## 5. Shared test harness fixtures (Lever A only)

- [x] 5.1 Add `tests/ui/modern/conftest.py` with a `make_tui_app` fixture and an
  `async` `tui_harness` context manager; move shared module helpers
  (`_idle_run_once`, `_submit_prompt`, `_wait_for`, `_choose_inline_option`,
  `_submit_text_input`, ...) into it.
- [x] 5.2 Migrate `tests/ui/modern/test_app.py` onto the fixtures (setup/teardown
  only; assertions unchanged); test count stays 145.
- [x] 5.3 Add `tests/tools/conftest.py` with a `make_runtime` fixture; move shared
  helpers (`read_v3`, `write_v3`, `update_v3`, `preflight_v3`, `decode`, ...) into it.
- [x] 5.4 Migrate `tests/tools/test_tools.py` onto the fixture (setup only;
  assertions unchanged); test count stays 128.
- [x] 5.5 Run `uv run pytest tests/ui/modern tests/tools -q` and confirm same pass
  count as before migration.

## 6. Extend guard and finalize

- [x] 6.1 Add `tools/agents.py`, `config/settings.py`, `llm/runner.py` to
  `TRACKED_MODULES` in `tests/architecture/test_module_size.py` with recorded
  baselines.
- [x] 6.2 Run `uv run pytest tests/architecture -q` and confirm all six tracked
  modules are under the ceiling.
- [x] 6.3 Run the full gate: `uv run pytest -q`, `uv run ruff check src tests`,
  `uv run ty check src`.
- [x] 6.4 Run `openspec validate decompose-remaining-large-modules --type change
  --strict` and fix any issues.
