## 1. Status Data Model

- [x] 1.1 Extend status reporting data structures with active-session usage, project usage, active Context Window status, and optional balance result fields.
- [x] 1.2 Add helpers that resolve active-session usage from `current_session_id` and merge project-level usage from `list_session_entries()`.
- [x] 1.3 Add compact formatting helpers for usage scopes, Context Window status, and balance status that can be reused by stable UI and TUI renderers.
- [x] 1.4 Preserve the existing local-only status builder behavior when balance lookup is not explicitly requested.
- [x] 1.5 Redesign the exit summary data/formatting helper so stable UI and TUI can render the same local-only compact exit panel.

## 2. DeepSeek Balance Lookup

- [x] 2.1 Implement a narrow balance client/helper for `GET /user/balance` using the configured DeepSeek API key.
- [x] 2.2 Parse `is_available` and each balance entry's `currency`, `total_balance`, `granted_balance`, and `topped_up_balance`.
- [x] 2.3 Return concise unavailable results for missing API key, unsupported base URL host, timeout, HTTP error, network error, or malformed response.
- [x] 2.4 Ensure errors and rendered status never include the raw API key.
- [x] 2.5 Add unit tests for successful CNY/USD balance parsing and each unavailable path.

## 3. Stable Interactive UI

- [x] 3.1 Add `/status` to built-in slash command completions and command discovery metadata.
- [x] 3.2 Update `/help` text so `/status` describes status, usage, and DeepSeek balance.
- [x] 3.3 Update the stable `/status` handler to pass the active session id and request balance exactly for that invocation.
- [x] 3.4 Render the stable `/status` output as a compact, readable panel with model, API key state, balance, usage, Context Window, project, sessions, skills, and MCP fields.
- [x] 3.5 Add terminal UI tests for discoverability, compact output, known usage, known balance, and balance unavailable rendering.

## 4. Textual TUI

- [x] 4.1 Update the Textual `/status` auxiliary view to request balance exactly when the status view is opened.
- [x] 4.2 Render active-session usage, project usage, Context Window, and balance in the Textual status view.
- [x] 4.3 Keep Textual status bar, side panel, welcome/help text, model progress, local command progress, input suggestions, and usage blocks balance-free.
- [x] 4.4 Add Textual tests for status view balance display and balance unavailable display.
- [x] 4.5 Route TUI `/exit`, `/quit`, and confirmed Ctrl+D through a shared exit-summary path.
- [x] 4.6 Print the redesigned exit summary after Textual full-screen teardown.
- [x] 4.7 Add Textual tests for `/exit` and confirmed Ctrl+D showing the exit summary without starting a model turn.

## 5. Exit Summary Redesign

- [x] 5.1 Redesign `build_exit_summary_text()` around the compact status-panel visual language.
- [x] 5.2 Preserve cumulative model usage and input-suggestion usage reporting while omitting empty usage sections.
- [x] 5.3 Include useful local identity fields such as model and session when known.
- [x] 5.4 Ensure stable `/exit`, `/quit`, and confirmed Ctrl+D all render the redesigned panel.
- [x] 5.5 Add focused exit-summary unit tests for known usage, input-suggestion usage, no-usage output, and stable UI exit paths.

## 6. No Background Balance Calls

- [x] 6.1 Add tests proving stable UI startup, welcome rendering, footer rendering, model-turn usage footer rendering, local command status rendering, exit summary rendering, and `deepy doctor` do not call the balance helper.
- [x] 6.2 Add tests proving Textual startup, status bar updates, side panel updates, model-turn progress, local command progress, usage block rendering, and exit summary rendering do not call the balance helper.
- [x] 6.3 Add a focused regression test that only `/status` invokes the balance helper in the stable UI.
- [x] 6.4 Add a focused regression test that only the Textual status command/view invokes the balance helper in the TUI.

## 7. Validation

- [x] 7.1 Run focused tests for status, slash commands, terminal UI, exit summary, TUI status/exit, and balance helper coverage.
- [x] 7.2 Run `uv run ruff check`.
- [x] 7.3 Run `uv run ty check src`.
- [x] 7.4 Run `openspec validate improve-status-command-usage-balance --type change --strict`.
