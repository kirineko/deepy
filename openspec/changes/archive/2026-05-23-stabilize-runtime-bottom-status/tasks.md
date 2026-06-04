## 1. Runtime Status Formatting

- [x] 1.1 Add a small runtime-status fitting model that separates protected prefix, activity label, and payload before producing the final bottom-row text.
- [x] 1.2 Add single-line payload sanitization for newlines, carriage returns, tabs, ANSI escape sequences, and non-printing control characters.
- [x] 1.3 Add tail truncation for command payloads so local commands and shell tool commands preserve the command prefix when width is limited.

## 2. Terminal UI Integration

- [x] 2.1 Apply the segment-aware fitting path to active model/tool runtime status updates.
- [x] 2.2 Apply the command-preserving fitting path to local `!cmd` runtime status updates.
- [x] 2.3 Keep transcript tool summaries and completed command output behavior unchanged unless a shared helper can be used without reducing transcript detail.

## 3. Tests

- [x] 3.1 Add focused tests that long tool payloads preserve spinner, elapsed time, interrupt affordance, and one-row width fitting.
- [x] 3.2 Add focused tests that long local commands and shell tool commands are tail-truncated while preserving the command prefix.
- [x] 3.3 Add focused tests that runtime payloads containing newlines, carriage returns, tabs, ANSI escape sequences, or control characters cannot produce multi-row bottom-status output.
- [x] 3.4 Keep or update existing runtime status tests for wide CJK text, narrow terminals, and shorter refresh padding.

## 4. Validation

- [x] 4.1 Run the focused terminal UI test set.
- [x] 4.2 Run repository formatting/lint/type validation appropriate for touched files.
- [x] 4.3 Run `openspec validate stabilize-runtime-bottom-status --type change --strict`.
