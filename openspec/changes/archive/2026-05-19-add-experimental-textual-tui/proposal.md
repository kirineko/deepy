## Why

Deepy's current Rich and prompt-toolkit interface is stable enough to keep as
the default, but it limits live layout, animation, navigable transcript blocks,
and richer tool surfaces. A separate experimental Textual TUI lets willing users
try a more expressive terminal experience without destabilizing the existing
interactive UI.

## What Changes

- Add an opt-in `deepy tui` command that starts an experimental Textual-powered
  full-screen terminal UI.
- Keep the existing `deepy` interactive command and Rich/prompt-toolkit UI as
  the default path.
- Introduce a Textual app shell in a new `src/deepy/tui/` package for chat,
  prompt input, live model progress,
  thinking blocks, tool activity, status, skills, sessions, and question flows.
- Add visually distinctive experimental UX that uses Textual strengths such as
  screens, reactive widgets, keyboard bindings, focusable blocks, themed TCSS,
  subtle transitions, live progress, and navigable transcript regions.
- Add a Deepy-owned diff experience for write/modify tools that may be inspired
  by toad and textual-diff-view, but does not copy AGPL code or require an AGPL
  dependency.
- Add Textual as a runtime dependency in a way that remains compatible with
  Deepy's supported Python version and does not require Python 3.14.
- Explicitly avoid binding Deepy to toad, toad's AGPL codebase,
  `textual-diff-view`, or toad's Python 3.14 dependency floor.

## Capabilities

### New Capabilities

- `experimental-textual-tui`: Opt-in Textual app experience, including its
  visual shell, input model, transcript rendering, live stream integration,
  tool/diff surfaces, navigation, and compatibility guardrails.

### Modified Capabilities

- `product`: Add the experimental `deepy tui` command while preserving `deepy`
  as the default stable interactive command.

## Impact

- Affected code:
  - `src/deepy/cli.py`
  - new Textual TUI modules under `src/deepy/tui/`
  - `src/deepy/llm/events.py` and `src/deepy/llm/runner.py` integration points
  - existing skill, session, status, AskUserQuestion, and tool rendering models
- Affected tests:
  - CLI parser tests for `deepy tui`
  - Textual headless/Pilot tests for the experimental app
  - rendering tests for transcript, tool, diff, and question widgets
  - regression tests proving the default `deepy` UI remains unchanged
- Dependencies:
  - Add Textual with a Python 3.12-compatible version constraint.
  - Do not add toad or `textual-diff-view` as dependencies unless a future
    license decision explicitly allows it.
- User impact:
  - Existing users keep the current UI by default.
  - Users who choose `deepy tui` get an experimental, visually richer,
    potentially faster-moving interface with clear experimental labeling.
