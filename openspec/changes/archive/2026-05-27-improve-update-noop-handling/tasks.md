## 1. Spec and Contract

- [x] 1.1 Update OpenSpec deltas for mixed no-op `Update` behavior, all-no-op metadata, and visible failure summaries.
- [x] 1.2 Validate the OpenSpec change strictly.

## 2. Tool Runtime

- [x] 2.1 Change `Update` planning to collect no-op edits as skipped metadata instead of blocking mixed valid edits.
- [x] 2.2 Preserve all-or-nothing preflight rejection for non-no-op failures.
- [x] 2.3 Return `ok=true` all-no-op results that do not claim file changes.
- [x] 2.4 Include applied/skipped edit counts and skipped edit metadata in successful results.

## 3. UI Feedback

- [x] 3.1 Improve tool progress/detail summaries for structured preflight failures.
- [x] 3.2 Add or update rendering tests for concise first-failure details.

## 4. Validation

- [x] 4.1 Add focused runtime tests for mixed no-op success, all-no-op success, and non-no-op rollback.
- [x] 4.2 Run focused tests for tools and message rendering.
- [x] 4.3 Run `uv run ruff check src tests`.
- [x] 4.4 Run `uv run ty check src`.
- [x] 4.5 Run the full test suite.
