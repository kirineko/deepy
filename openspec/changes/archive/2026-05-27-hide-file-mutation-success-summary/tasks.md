## 1. Spec

- [x] 1.1 Add terminal UI spec delta for hiding redundant successful file mutation summaries.
- [x] 1.2 Validate the OpenSpec change strictly.

## 2. Implementation

- [x] 2.1 Update tool output rendering to omit successful `Write`/`Update` summary lines when a diff preview is present.
- [x] 2.2 Preserve summary rendering for failures, retryable results, and no-diff results.
- [x] 2.3 Update focused rendering tests.

## 3. Validation

- [x] 3.1 Run focused message/terminal rendering tests.
- [x] 3.2 Run `uv run ruff check src tests`.
- [x] 3.3 Run `uv run ty check src`.
- [x] 3.4 Run the full test suite.
