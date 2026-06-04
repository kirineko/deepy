## 1. Configuration

- [x] 1.1 Add a `UiConfig.view_mode` setting with values `concise` and `full`, defaulting invalid or missing values to `concise`.
- [x] 1.2 Add a TOML updater for persisting UI view mode while preserving unrelated config sections and file permissions.
- [x] 1.3 Include resolved view mode in config display and JSON status surfaces where UI settings are shown.
- [x] 1.4 Add focused settings tests for default, explicit, invalid, persisted, and displayed view mode behavior.

## 2. Stable Terminal UI

- [x] 2.1 Add `/view` to built-in slash command discovery, ranking, help output, and startup command surfaces where appropriate.
- [x] 2.2 Implement `/view`, `/view toggle`, `/view concise`, `/view full`, and invalid argument handling with concise reasoning hidden/shown confirmations.
- [x] 2.3 Thread resolved view mode into terminal stream rendering for live model turns and resumed history rendering as needed.
- [x] 2.4 Hide live reasoning transcript text in concise view while preserving session persistence and provider reasoning behavior.
- [x] 2.5 Preserve existing `[Thinking]` block rendering in full view.
- [x] 2.6 Add current-turn stream token estimation for streamed reasoning and assistant text deltas, reset it per model turn, and render it as `↓ N tokens` in runtime status.
- [x] 2.7 Add focused terminal UI tests for slash command behavior, concise/full reasoning rendering, and runtime token status accumulation across reasoning and assistant output.

## 3. Experimental Textual TUI

- [x] 3.1 Add `/view` to Textual command discovery and slash command handling.
- [x] 3.2 Apply resolved view mode to Textual live reasoning block rendering.
- [x] 3.3 Show Textual `/view` confirmations and invalid usage messages with reasoning hidden/shown state.
- [x] 3.4 Add current-turn stream token estimation to Textual live progress status with the same `↓ N tokens` semantics.
- [x] 3.5 Add focused Textual tests for concise/full view behavior, `/view toggle`, and stream token status accumulation.

## 4. Validation

- [x] 4.1 Run `openspec validate add-view-reasoning-status --type change --strict`.
- [x] 4.2 Run focused tests for settings, stable terminal UI, and Textual TUI.
- [x] 4.3 Run `uv run ruff check src tests`.
- [x] 4.4 Run `uv run ty check src`.
- [x] 4.5 Run the full test suite when implementation is complete.
