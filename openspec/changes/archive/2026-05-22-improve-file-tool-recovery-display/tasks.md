## 1. Tool Argument Recovery

- [x] 1.1 Add conservative malformed-argument repair helpers for unquoted `snapshot_<number>`, unquoted `snippet_<number>`, Python-style simple literals, and trailing commas.
- [x] 1.2 Wire repair into built-in function-tool argument parsing after normal JSON parse failure and before returning `invalid_arguments`.
- [x] 1.3 Ensure repaired arguments are schema/field validated before any tool side effect can run.
- [x] 1.4 Add structured repair metadata for repaired successes and retryable invalid-argument failures.
- [x] 1.5 Add tests proving unsafe content-bearing malformed arguments are not repaired or executed.

## 2. Snapshot Freshness Tokens

- [x] 2.1 Add a numeric runtime-local snapshot token to managed file snapshots.
- [x] 2.2 Include `snapshot_token` in `read_file` metadata alongside `snapshot_id` and content hash.
- [x] 2.3 Extend `write_file` existing-file replacement validation and schema to accept a fresh `snapshot_token`.
- [x] 2.4 Extend `apply_patch` `replace_file` validation and schema to accept a fresh `snapshot_token`.
- [x] 2.5 Update file-tool docs and prompt guidance for numeric freshness tokens without removing existing `snapshot_id` or hash guidance.

## 3. Stable Terminal Rendering

- [x] 3.1 Add safe malformed file-tool argument summaries for `write_file`, `edit_text`, and `apply_patch`.
- [x] 3.2 Prevent raw large `content`, replacement text, and patch operation bodies from rendering solely because argument JSON parsing failed.
- [x] 3.3 Render retryable invalid-argument tool results with a quieter retryable/recoverable status distinct from blocking failures.
- [x] 3.4 Preserve normal failed rendering for stale snapshot, missing freshness token, path policy, unsupported target, match, and commit failures.

## 4. Experimental TUI Rendering

- [x] 4.1 Add retryable/recoverable state handling to TUI tool blocks.
- [x] 4.2 Add bounded malformed file-tool argument summaries to TUI tool call and output blocks.
- [x] 4.3 Fold a retryable malformed attempt into a later successful same-tool/same-target file-tool block when the match is clear.
- [x] 4.4 Keep raw persisted session history unchanged while applying any TUI-only recovered-attempt folding.
- [x] 4.5 Keep expanded diagnostic details bounded and include parse location/recovery hints when available.

## 5. Verification

- [x] 5.1 Add focused tool tests for argument repair, retryable metadata, snapshot token acceptance, stale/mismatched token rejection, and unsafe repair rejection.
- [x] 5.2 Add message-view and stable terminal tests for safe malformed summaries and retryable status rendering.
- [x] 5.3 Add TUI tests for retryable tool blocks, recovered-attempt folding, bounded details, and blocking-failure non-folding.
- [x] 5.4 Run focused tests for `tests/test_tools.py`, `tests/test_message_view.py`, `tests/test_terminal_ui.py`, and relevant TUI tests.
- [x] 5.5 Run `openspec validate improve-file-tool-recovery-display --type change --strict`.
