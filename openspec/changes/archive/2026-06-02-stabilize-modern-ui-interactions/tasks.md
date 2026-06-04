## 1. Interaction Flow

- [x] 1.1 Add a shared active-interaction guard for bottom sheet decision flows.
- [x] 1.2 Prevent prompt focus and prompt key handling while audit or question decisions are pending.
- [x] 1.3 Route `Esc` to reject/cancel active audit and ask-user-question flows before prompt interrupt handling.
- [x] 1.4 Add regression tests for audit and ask-user-question focus escape/deadlock behavior.

## 2. Transcript Rendering

- [x] 2.1 Fix Write/Update tool-output routing so diff blocks replace compact output rows in chronological order.
- [x] 2.2 Constrain diff block height/overflow so large diffs do not break transcript scrolling.
- [x] 2.3 Add tests for diff ordering and transcript scroll behavior with large diffs.
- [x] 2.4 Keep Write/Update diffs before current-turn streamed assistant text when tool output arrives after text deltas.
- [x] 2.5 Add a regression test for streamed assistant text arriving before a mutation diff.

## 3. Composer And Markdown Density

- [x] 3.1 Redesign the Modern UI composer to reserve five visible prompt lines.
- [x] 3.2 Ensure drafts longer than five lines scroll inside the prompt input.
- [x] 3.3 Tighten Markdown table and block spacing in transcript rendering.
- [x] 3.4 Add focused tests for composer height and compact table output.

## 4. Validation

- [x] 4.1 Validate this OpenSpec change in strict mode.
- [x] 4.2 Run focused Modern UI tests.
- [x] 4.3 Run `uv run ruff check src tests`, `uv run ty check src`, and broader tests affected by TUI changes.
