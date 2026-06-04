## 1. Remove Legacy Context Paths

- [x] 1.1 Identify all callers of `compact_items_for_context()`, `build_session_input_callback()`, and `DeepySessionManager.compact_session()`.
- [x] 1.2 Remove silent model-input trimming from the Agents SDK session callback path.
- [x] 1.3 Replace placeholder `compact_session()` behavior with a delegation point for the new compaction service.
- [x] 1.4 Update or delete tests that assert old placeholder compaction or callback trimming behavior.
- [x] 1.5 Add regression tests proving oversized context is not silently trimmed when durable compaction fails.

## 2. Context Settings And Token Accounting

- [x] 2.1 Extend `ContextConfig` with `reserved_context_tokens`, `compact_preserve_recent_messages`, and optional `compact_preserve_recent_tokens` defaults and TOML parsing.
- [x] 2.2 Update config serialization, README examples, `deepy config show`, and `deepy doctor` so resolved canonical compaction policy values are visible.
- [x] 2.3 Remove `compact_prompt_token_threshold` from runtime config and compaction decisions; old config keys are ignored.
- [x] 2.4 Extend session index metadata to track latest precise context token checkpoint and pending estimated tokens; treat old `activeTokens` as display fallback only.
- [x] 2.5 Update session append and usage recording so model usage resets pending estimates and later appended user/assistant/tool items add pending token estimates.
- [x] 2.6 Add restoration logic that reconstructs effective context tokens from checkpoint metadata and records after the checkpoint when needed.

## 3. Compaction Core

- [x] 3.1 Create a compaction result model containing replacement SDK items, preserved item count, before/after token estimates, trigger reason, and archive path.
- [x] 3.2 Implement recent-context selection that preserves complete user/assistant turns and keeps dependent tool-call groups valid.
- [x] 3.3 Update the compact prompt builder to support optional manual focus instructions and output a model-visible summary message without internal analysis text.
- [x] 3.4 Implement the compaction model call using the existing provider bundle with no normal Deepy tools loaded.
- [x] 3.5 Implement safe session rewrite: generate replacement first, rotate/archive original JSONL, write replacement, update index, and restore original on write failure.
- [x] 3.6 Remove any remaining placeholder summary generation code that does not call the compaction model.

## 4. Automatic Compaction Flow

- [x] 4.1 Add `should_auto_compact()` policy using effective tokens, context window, trigger ratio, and reserved context tokens.
- [x] 4.2 Run durable auto compaction before `Runner.run_streamed` when a resumed session exceeds policy.
- [x] 4.3 Make auto compaction failure stop the turn with a clear error while leaving session history unchanged.
- [x] 4.4 Ensure the Agents SDK session input callback is no longer responsible for compaction or trimming.
- [x] 4.5 Add a hard oversized-context guard that blocks the model request when compaction cannot make the context fit.

## 5. Interactive `/compact`

- [x] 5.1 Register `/compact` in built-in slash command completions.
- [x] 5.2 Add `/compact [focus]` handling in the interactive terminal command dispatcher.
- [x] 5.3 Handle no-active-session and empty-session cases without creating or modifying sessions.
- [x] 5.4 Show compaction progress, success before/after token estimates, and concise failure messages.
- [x] 5.5 Refresh footer context status after manual and automatic compaction.

## 6. Status, Resume, And Session Display

- [x] 6.1 Update context footer/status report to include effective tokens, pending estimate, reserved budget, compact threshold, window, and percentage.
- [x] 6.2 Update `deepy sessions list` and resume previews so compacted sessions show the post-compaction active token estimate.
- [x] 6.3 Ensure `deepy sessions show` displays compacted summary items and preserved recent items in replay order.
- [x] 6.4 Ensure archived pre-compaction files do not appear as active sessions unless explicitly exposed by a future command.

## 7. Tests And Validation

- [x] 7.1 Add settings tests for default, invalid, and deprecated compaction policy values.
- [x] 7.2 Add unit tests for `should_auto_compact()` ratio, reserved-budget, zero-token, and pending-token cases.
- [x] 7.3 Add session tests for usage checkpoint reset, pending token accumulation, restore reconstruction, and compacted `activeTokens`.
- [x] 7.4 Add compaction service tests for summary generation, focus instruction injection, recent preservation, tool-call group integrity, archive creation, and rollback on failure.
- [x] 7.5 Add runner tests proving auto compaction runs before model calls and failure prevents oversized model requests.
- [x] 7.6 Add terminal/slash command tests for `/compact`, `/compact <focus>`, no active session, empty session, success, failure, and help/completion discoverability.
- [x] 7.7 Add regression tests proving session callback compaction/trimming is gone.
- [x] 7.8 Run the focused test suite for settings, context, sessions, runner, slash commands, terminal UI, and status.
