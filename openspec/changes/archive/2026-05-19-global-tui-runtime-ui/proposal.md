## Superseded

Manual testing after implementation found that this proposal's
`PromptSession`-owned runtime UI approach does not satisfy the required
terminal behavior. In particular, the status/footer row is not truly fixed to
the terminal bottom, modal picker commands can crash under the active event
loop, long thinking and tool ordering remain unstable, and completion menus can
disappear near the bottom of the terminal.

Do not archive this change as the accepted terminal UI architecture. It is
superseded by `rebuild-terminal-application-ui`, which explores and specifies a
full prompt-toolkit `Application` owner instead of continuing to patch the
prompt-router design.

## Why

Deepy's previous attempt to display runtime status through a temporary
`prompt_async` lifecycle exposed a deeper ownership problem: prompt-toolkit and
Rich were both writing active terminal UI during the same turn. Runtime UI needs
one global owner and an event-driven view model so thinking, tool output,
status, footer, and subsequent input cannot corrupt each other.

## What Changes

- Introduce a global interactive UI owner for idle and running turns, modeled
  after the `CustomPromptSession` / running delegate shape observed in
  `reference/kimi-cli`.
- Split streaming event handling into event-to-view-state reducers and
  transcript commit/rendering, instead of printing Rich output directly from
  `TerminalStreamRenderer` during active runtime UI.
- Render runtime thinking, tool progress, local-command status, footer, and
  input from a single prompt-toolkit-owned surface.
- Add explicit running input routing for cancel, queue, and ignore behavior so
  the second prompt after a turn remains reliable.
- Allow modest UI display changes if they improve stability, such as a compact
  running panel above the input and a transcript commit after the runtime view
  releases ownership.
- Defer a full-screen `Application` rewrite until the event-driven shell is
  stable; this change may introduce a global shell/controller without forcing
  every existing picker into one layout.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Replace split runtime rendering with a global prompt-toolkit UI
  owner and event-driven runtime view model for model turns and interactive
  local commands.

## Impact

- Affected code:
  - `src/deepy/ui/terminal.py`
  - `src/deepy/ui/prompt_input.py`
  - `src/deepy/ui/runtime_prompt.py`
  - `src/deepy/ui/message_view.py`
  - `src/deepy/ui/app.py`
  - potentially new modules for runtime view state, prompt routing, and
    transcript commit rendering
- Affected tests:
  - PTY integration tests for long input, runtime thinking, local commands,
    second prompt recovery, and status scrollback pollution
  - unit tests for event reducers, running input routing, and transcript commit
    rendering
- No public CLI command syntax changes are expected.
- No new terminal UI dependency is expected; this should build on
  prompt-toolkit and Rich already in use.
