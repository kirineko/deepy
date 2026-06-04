## Why

The last two terminal UI attempts proved that incremental fixes around
`PromptSession`, inline status text, and toolbar-style footer rendering are not a
stable foundation for Deepy's interactive UI. The current failures are
structural:

- the model/context status line is not owned by a true bottom layout row;
- prompt completions disappear near the terminal bottom;
- runtime thinking/tool output competes with input rendering;
- modal pickers can nest prompt-toolkit event loops and crash;
- the code path is now difficult to reason about because ownership is split
  across prompt input helpers, terminal stream rendering, runtime prompts, and
  picker Applications.

This change makes the replacement explicit: rebuild the terminal UI as a clean
Application-owned subsystem. Internal compatibility with the current UI modules
is not a goal. Existing code may be deleted, split, or rewritten where that
produces a clearer architecture. Existing implementation details may be reused
only when they fit the new ownership model.

This change supersedes `global-tui-runtime-ui` for the terminal runtime/input
architecture. That proposal should not be archived as the accepted UI design.

## What Changes

- Introduce a clean prompt-toolkit Application shell as the single owner of the
  interactive terminal screen.
- Organize the new UI around a small set of explicit parts:
  - controller/effects for running commands and model turns;
  - event/action model for user input, runtime updates, modals, completions, and
    shutdown;
  - reducer/view-model state for transcript, runtime blocks, input buffer,
    completion state, modal state, and footer state;
  - component views for transcript, runtime blocks, input editor, completions,
    modals, and fixed footer;
  - adapters to existing Deepy session/model/tool/config services.
- Treat CLI command syntax, session data, tool execution semantics, model
  routing, and config behavior as the public compatibility boundary.
- Treat internal UI modules and APIs as replaceable implementation details.
  The rewrite may remove old prompt-router code, bottom-toolbar shims, runtime
  prompt helpers, old picker `run()` APIs, and tests that assert obsolete
  behavior.
- Render the bottom model/context/status line as a real fixed Application row
  that spans the terminal width. Runtime status may be folded into this footer,
  but it must not be printed as scrollback or prompt text.
- Render live thinking, tools, local commands, assistant output, and usage as
  ordered runtime/transcript blocks from the event model.
- Move slash-command and file-mention completion into an Application-owned
  completion component so `/` and `@` suggestions remain visible near the
  terminal bottom.
- Replace modal picker event-loop nesting with Application-owned modal
  components.
- Add PTY and unit regression coverage for the reported failures before
  declaring the new UI complete.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Replace the current prompt-session-centered UI with a
  clean-slate, componentized prompt-toolkit Application architecture for idle
  input, running turns, completions, modal flows, fixed footer rendering, and
  ordered runtime/transcript output.

## Impact

- Affected code:
  - `src/deepy/ui/terminal.py`
  - `src/deepy/ui/prompt_input.py`
  - `src/deepy/ui/runtime_prompt.py`
  - `src/deepy/ui/runtime_view.py`
  - `src/deepy/ui/session_picker.py`
  - `src/deepy/ui/model_picker.py`
  - `src/deepy/ui/theme_picker.py`
  - `src/deepy/ui/skill_picker.py`
  - new UI package/modules under `src/deepy/ui/`
  - related session-loading call sites such as `src/deepy/sessions/jsonl.py`
- Affected tests:
  - PTY tests for startup layout, fixed footer placement, long thinking,
    thinking/tool ordering, `/resume`, completions, local commands, and `/exit`
  - unit tests for reducers, component state projection, modal state,
    completion state, transcript commit, and footer truncation
- Compatibility:
  - Public interactive commands and core Deepy behavior should remain stable.
  - Internal UI module APIs do not need backward compatibility.
  - Visual details may change where the new layout is clearer and more stable.
- Dependencies:
  - No new TUI dependency is expected; this should use prompt-toolkit and Rich
    already present in the project.
