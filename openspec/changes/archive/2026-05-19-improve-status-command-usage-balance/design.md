## Context

Deepy currently has three related status surfaces:

- `deepy status` uses `src/deepy/status.py` to report project/config/runtime state.
- The stable interactive UI already has a `/status` handler, but `/status` is not included in the built-in slash command catalog.
- The experimental Textual TUI has a `/status` screen backed by the same status report, but it does not include DeepSeek account balance.

Deepy also has an existing stable terminal exit panel in `src/deepy/ui/exit_summary.py`, but the stable interactive loop currently shows it only through `/exit`/`/quit`; confirmed Ctrl+D exits return directly without rendering the panel. The experimental Textual TUI currently exits directly as well. The exit summary already reports local cumulative usage and input-suggestion usage, which overlaps with the new status panel's local usage summary. These should converge visually and semantically without making exit perform remote balance checks.

Token usage is already normalized through `TokenUsage` and persisted in the project session index. Context Window occupancy is intentionally separate from cumulative Token Usage and should remain separate in the status output. DeepSeek documents a read-only balance endpoint at `GET /user/balance` that returns account availability plus per-currency balances.

## Goals / Non-Goals

**Goals:**

- Make `/status` discoverable and useful as the compact place to inspect local usage, context state, runtime state, and DeepSeek balance.
- Call the DeepSeek balance endpoint only in direct response to `/status`.
- Keep all non-`/status` paths free of balance network calls, including startup, prompt footer/status bar rendering, model turns, usage footers, `deepy doctor`, and ordinary `deepy status` unless that command is explicitly extended later.
- Reuse existing usage/session-index data instead of introducing a new accounting store.
- Keep balance lookup failures non-fatal and visibly degraded.
- Redesign the stable exit summary panel to match the compact status panel's information hierarchy.
- Ensure stable `/exit`, `/quit`, and confirmed Ctrl+D all render the redesigned exit summary.
- Show the redesigned exit summary when the experimental Textual TUI exits through `/exit` or confirmed Ctrl+D, after leaving full-screen mode.

**Non-Goals:**

- Do not estimate money spent from token counts or model pricing.
- Do not cache balance persistently.
- Do not add background polling or startup health checks for balance.
- Do not expose or print API keys.
- Do not change session JSONL format or migrate existing session indexes.
- Do not call the balance endpoint from exit paths.

## Decisions

1. Add an explicit balance lookup mode to the shared status builder.

   The shared status module should keep local status construction pure by default. Balance data should be requested only when the caller passes an explicit flag or calls a dedicated async/sync helper used by `/status`.

   Alternative considered: always include balance in `build_status_report()`. Rejected because status reports are used in CLI, TUI runtime summaries, and help surfaces where hidden network calls would be surprising and could slow startup or rendering.

2. Treat `/status` as the only balance trigger.

   The stable interactive `/status` handler and the Textual TUI `/status` command should request balance. Prompt footer rendering, TUI status bars, welcome panels, `deepy doctor`, model completion usage footers, and ordinary local status construction should not request balance.

   Alternative considered: query balance in `deepy status` as well. Rejected for this change because the user explicitly constrained balance lookup to `/status`; CLI expansion can be considered separately with an explicit flag if needed later.

3. Keep usage scopes explicit.

   The status panel should show active-session Token Usage when `current_session_id` is known, and project Token Usage by merging usage values from the project session index. Context Window should continue to use latest request context occupancy, not cumulative total tokens.

   Alternative considered: only show the active session. Rejected because the current `deepy status` already reports project-level counts, and a compact project total is useful for checking local history without leaving the session.

4. Use a small DeepSeek balance client boundary.

   Implement a narrow helper that builds the balance URL from the configured DeepSeek base URL, sends `Authorization: Bearer <api_key>`, parses `is_available` and `balance_infos`, and returns a typed result or unavailable error. It should avoid sending requests when no API key is configured or when the configured base URL is not a DeepSeek API host.

   Alternative considered: call through the OpenAI SDK client. Rejected unless the SDK exposes a simple generic GET path, because this endpoint is outside Chat Completions and should remain a tiny read-only integration.

5. Render a compact status panel instead of extending the footer.

   `/status` should print/open a compact grouped block with labels such as model, api, balance, usage, ctx, project, sessions, skills, and mcp. The persistent footer/status bar should not show balance because that would either be stale or require background calls.

   Alternative considered: add `balance` to the bottom footer. Rejected because the footer is rendered frequently and would violate the `/status`-only lookup rule.

6. Redesign exit summary as a local-only companion panel.

   The exit summary should use the same compact grouping and label style as `/status`, but only local data: session usage, input-suggestion usage, active model, assistant/message count when available, and session/project identity when useful. Stable `/exit`, `/quit`, and confirmed Ctrl+D should all go through this renderer. It should omit DeepSeek balance and avoid any network call.

   Alternative considered: reuse the `/status` panel wholesale on exit. Rejected because `/status` includes balance and live runtime checks, while exit should be fast, deterministic, and local-only.

7. Let TUI print the exit summary after the Textual app closes.

   The TUI should prepare or return a local exit summary when `/exit` or confirmed Ctrl+D triggers shutdown, then print it after full-screen teardown so it appears in the normal terminal like the stable UI's exit panel.

   Alternative considered: show a modal inside the TUI before exit. Rejected because the user wants a unified exit result, and an in-app modal would disappear with the full-screen app unless it required an extra confirmation step.

## Risks / Trade-offs

- [Risk] Balance endpoint latency could make `/status` feel slow. -> Mitigation: use a short timeout and render unavailable text on timeout.
- [Risk] Users with proxy or non-official OpenAI-compatible base URLs could leak requests to the wrong service. -> Mitigation: skip balance lookup unless the resolved host is a DeepSeek API host.
- [Risk] Project usage totals can be incomplete if older sessions lack usage metadata. -> Mitigation: label unknown or partial data clearly and rely only on existing normalized usage records.
- [Risk] TUI and stable UI formatting could diverge. -> Mitigation: centralize status summary formatting data in `status.py`, with UI-specific renderers consuming the same fields.
- [Risk] Exit summary rendering after TUI teardown may be skipped if exit paths do not share one shutdown boundary. -> Mitigation: route `/exit` and Ctrl+D confirmation through one TUI exit-summary path and cover both with tests.
