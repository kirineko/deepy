## Why

Modern UI currently has several transcript and command workflow regressions that make the main conversation surface feel unreliable: transcript content is difficult to scroll, prompt history can appear to be the only way to move through output, Markdown tables are too loose, `/ps` appears in a detached screen, and `/reset` uses a free-text form that does not match Classic UI setup guidance. These are user-visible behaviors in the Textual TUI and need to be specified before implementation.

## What Changes

- Make the Modern UI transcript reliably scrollable with mouse and touchpad wheel input while preserving prompt-focused history navigation.
- Keep prompt history available from the composer, including ordinary `Up`/`Down` in prompt-focused history scenarios and `Ctrl+Up`/`Ctrl+Down` as explicit shortcuts.
- Fix composer sizing so the prompt input reserves four visible lines and scrolls internally after that instead of floating between one and five lines.
- Tighten Modern UI Markdown table rendering so transcript tables use terminal-appropriate density and do not break transcript autoscroll.
- Render user-invoked `/ps` results as foreground transcript content, with task identifiers that can be used by `/stop`, while keeping AI/tool background-task output out of foreground `/ps` blocks.
- Replace the current Modern UI reset free-text form with a low-frequency setup workflow that reuses Classic UI ordering and selection semantics: provider first, provider-specific API key guidance, API key, model, base URL, thinking, then UI/theme.
- Keep tool and local command output in the transcript order users can reason about: update an existing placeholder in place when one exists, but do not move later Shell or tool output above earlier assistant/diff content without a known earlier tool anchor.
- Render model tool results with useful foreground content: Todo results should show the current todo board in a compact Modern UI style, model-invoked Shell/CMD tools should show the executed command without the model-provided description/comment text, and transcript diff blocks should rely on the parent transcript scroll instead of adding a nested vertical scroller.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `experimental-textual-tui`: tighten transcript scrolling, composer ergonomics, Markdown density and autoscroll, user-invoked background task display, tool transcript ordering and presentation, and reset/config workflow requirements for the Modern UI.

## Impact

- Affected OpenSpec capability: `experimental-textual-tui`.
- Affected code: `src/deepy/tui/app.py`, `src/deepy/tui/widgets.py`, `src/deepy/tui/screens.py`, and possibly shared setup selection helpers if needed.
- Affected tests: Textual headless tests in `tests/test_tui_app.py`; Markdown density tests may also be updated if shared rendering is touched.
- Local `!CMD` command rendering is intentionally out of scope for the new Shell/CMD display follow-up because that path has already been optimized.
- No new runtime dependencies are expected.
