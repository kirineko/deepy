## 1. Configuration And Command Surface

- [x] 1.1 Add input-suggestion enabled config parsing with a default of enabled.
- [x] 1.2 Add config serialization/update helpers that persist only the enabled state and preserve unrelated TOML settings with `0600` permissions.
- [x] 1.3 Add `/input-suggestion` to built-in slash command discovery and help text.
- [x] 1.4 Implement `/input-suggestion` toggle handling in the stable terminal UI, including unsupported-argument validation and in-process setting refresh.
- [x] 1.5 Implement `/input-suggestion` toggle handling in the experimental Textual TUI with the same validation and confirmation behavior.
- [x] 1.6 Update config show/status output to include the resolved input-suggestion enabled state without exposing a customizable suggestion model.

## 2. Suggestion Core

- [x] 2.1 Add a shared input suggestion module for controller state, delayed visibility, cancellation, acceptance, dismissal, and accepted-method metadata.
- [x] 2.2 Add suggestion prompt construction from recent session context with a deterministic recent-history limit.
- [x] 2.3 Add eligibility checks for interactive mode, enabled state, successful completed turns, at least two assistant/model replies, idle prompt state, and no pending question or confirmation flow.
- [x] 2.4 Add deterministic quality filters for length, CJK length, one-word allowlist, slash commands, formatting, multiple sentences, prefixed labels, error-like output, evaluative text, AI voice, and meta text.
- [x] 2.5 Add cancellation behavior for user typing, paste, submit, local command start, model turn start, feature disable, and UI teardown.

## 3. DeepSeek Side Query And Usage

- [x] 3.1 Add a provider/model-settings path for input suggestion calls that always uses `deepseek-v4-flash`, disables thinking, omits `reasoning_effort`, requests usage, and disables provider storage.
- [x] 3.2 Implement the best-effort suggestion model call with no user-visible failure on timeout, cancellation, API error, or filtered response.
- [x] 3.3 Add input-suggestion-specific usage data structures or session records that preserve token counts, request count, model, and elapsed time.
- [x] 3.4 Ensure suggestion usage does not update ordinary turn `TokenUsage`, context window checkpoints, or automatic compaction decisions.
- [x] 3.5 Add user-facing accumulated suggestion usage display where existing session/exit usage is summarized, clearly labeled separately from model-turn usage.

## 4. Stable Terminal UI Integration

- [x] 4.1 Render visible suggestions as muted prompt-area ghost text when the stable prompt buffer is empty.
- [x] 4.2 Bind Tab to accept a visible input suggestion only when slash/file completion is not active, inserting text without submitting.
- [x] 4.3 Bind Right Arrow to accept a visible input suggestion under the same conditions, inserting text without submitting.
- [x] 4.4 Preserve Enter behavior so visible suggestions are not accepted or submitted from an empty prompt.
- [x] 4.5 Clear visible suggestions when the user edits, pastes, submits, opens another completion surface, starts a local command, or starts a model turn.
- [x] 4.6 Trigger background suggestion generation after eligible stable UI turns complete and suppress generation for waiting-for-user, interrupted, failed, or early-session turns.

## 5. Textual TUI Integration

- [x] 5.1 Extend or wrap the Textual prompt widget to render prompt-area ghost text for empty-buffer input suggestions.
- [x] 5.2 Bind Tab and Right Arrow to accept Textual ghost-text suggestions without submitting.
- [x] 5.3 Preserve Textual Enter behavior so visible suggestions are not accepted or submitted from an empty prompt.
- [x] 5.4 Prevent ghost text from incoherently overlapping slash command and file mention suggestion surfaces.
- [x] 5.5 Clear Textual suggestions on edit, paste, submit, local command start, model turn start, feature disable, and app teardown.
- [x] 5.6 Trigger background suggestion generation after eligible Textual turns complete and suppress generation for pending questions, failures, or early sessions.

## 6. Tests And Validation

- [x] 6.1 Add settings tests for default-enabled input suggestions, persisted toggles, config show serialization, and invalid/non-customizable model behavior.
- [x] 6.2 Add suggestion filter and eligibility unit tests, including the two-model-reply threshold and cancellation paths.
- [x] 6.3 Add provider tests asserting fixed `deepseek-v4-flash`, thinking disabled, no `reasoning_effort`, usage enabled, and storage disabled.
- [x] 6.4 Add usage accounting tests proving suggestion usage stays separate from turn usage and context window checkpoints.
- [x] 6.5 Add stable terminal UI tests for ghost text rendering, Tab acceptance, Right Arrow acceptance, Enter non-acceptance, dismissal, and `/input-suggestion` toggle behavior.
- [x] 6.6 Add Textual headless tests for ghost text rendering, Tab/Right acceptance, Enter non-acceptance, overlap avoidance with existing suggestions, dismissal, and `/input-suggestion` toggle behavior.
- [x] 6.7 Run focused tests for changed areas, then run the repo's standard validation set: pytest, ruff, type check, and OpenSpec strict validation.
