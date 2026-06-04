## Context

Deepy's terminal UI has reached the point where small fixes are making the
system harder to control. The failed iterations share the same root problem:
there is no single UI owner.

Today the interactive screen is assembled from prompt-toolkit `PromptSession`,
Rich terminal writes, bottom toolbar fragments, runtime prompt text, and
separate picker Applications. Those pieces can work in isolation, but they
compete for the same terminal rows during real interaction. This caused the
reported issues: fake bottom status placement, blank gaps below the status
line, disappearing completions, nested event-loop crashes, thinking/tool output
order bugs, and input corruption after turns.

The replacement should be a clean UI subsystem, not another compatibility layer
around those parts.

## Goals / Non-Goals

**Goals:**

- Make one prompt-toolkit `Application` the owner of the whole interactive TTY.
- Build the UI as composable components backed by a single view model.
- Keep data flow explicit: actions/events update state; components render state;
  effects call Deepy services and emit more events.
- Make adding or removing a component a local change with a clear interface.
- Preserve public Deepy behavior: command syntax, session persistence, model
  routing, tool execution, local commands, config, and slash-command meanings.
- Fix the known UI failures through architecture, not through terminal cursor
  patches.
- Prefer deleting obsolete UI code over keeping compatibility shims.

**Non-Goals:**

- Do not preserve internal APIs from `prompt_input.py`, runtime prompt helpers,
  old picker `run()` methods, or status/footer shims.
- Do not keep `PromptSession.bottom_toolbar` as a footer strategy.
- Do not keep Rich live writes as the owner of runtime UI during an interactive
  turn.
- Do not introduce ANSI scroll-region hacks as the long-term layout owner.
- Do not add a new TUI framework dependency.
- Do not change the model/tool/session semantics outside the UI boundary.

## Architecture

The implementation should introduce a new terminal UI subsystem under
`src/deepy/ui/`. The exact package name can be chosen during implementation,
but the structure should keep these responsibilities separate:

```text
ui/
  tui/
    app.py              # builds and runs the prompt-toolkit Application
    controller.py       # effects: submit input, run turns, route commands
    state.py            # AppState, reducer, derived selectors
    events.py           # user actions and runtime events
    layout.py           # root container and region wiring
    components/
      transcript.py     # scrollable committed transcript/runtime viewport
      input.py          # editing buffer, key bindings, submit/newline/exit
      footer.py         # fixed one-row status/model/context footer
      completions.py    # slash and file-mention suggestions
      modals.py         # picker and command modal surfaces
      runtime.py        # live thinking/tool/local-command blocks
    adapters/
      commands.py       # slash/local command bridge to existing behavior
      sessions.py       # async session list/load/save bridge
      render.py         # Rich/style conversion helpers where useful
```

This package does not need to preserve old file names. Old helpers can be moved
or deleted as needed.

## Data Flow

The new UI should use unidirectional flow:

```text
keyboard/input event
  -> UI action
  -> reducer updates AppState
  -> controller runs effects when needed
  -> model/tool/session/local-command events
  -> reducer updates AppState
  -> prompt-toolkit invalidates and components re-render
```

Rules:

- Components read state and emit actions; they do not run model turns or write
  directly to the terminal.
- The controller owns side effects such as model streaming, slash-command
  execution, session loading, local command execution, and exit handling.
- Runtime stream chunks become ordered events, not prompt fragments.
- Committed transcript output is produced from the same ordered event model used
  by the live runtime view.
- Session-loading APIs used by UI code must be awaited in async contexts; modal
  code must not call `asyncio.run()` inside the running Application.

## Layout Model

The Application owns these regions:

```text
┌────────────────────────────────────┐
│ transcript/runtime viewport         │  weight=1, scrollable
│                                    │
├────────────────────────────────────┤
│ completion/menu or modal overlay    │  visible only when active
├────────────────────────────────────┤
│ input editor                        │  bounded height, Ctrl+J newline
├────────────────────────────────────┤
│ fixed footer                        │  exactly one bottom row
└────────────────────────────────────┘
```

The footer should be one permanent row at the terminal bottom. It can combine
idle metadata and running state, for example elapsed time / interrupt hint /
model / cwd / context. Long content must be truncated or elided within the row;
it must not wrap into a second row or spill into scrollback.

The input editor is directly above the footer. The completion region is owned by
the Application and must remain visible even when the input editor is near the
terminal bottom.

## Component Model

Each UI component should have a small contract:

- input state it reads from `AppState`;
- actions/events it may emit;
- render method/control factory;
- optional lifecycle hooks for focus, open/close, and cleanup.

Components should not know about each other's internals. Cross-component
coordination should happen through shared state and actions. For example,
opening `/resume` updates modal state and focus; it does not start a second
Application.

Initial components:

- `TranscriptViewport`: committed messages plus live runtime blocks.
- `RuntimeBlocks`: thinking/tool/local-command/assistant/usage blocks in event
  order.
- `InputEditor`: text buffer, multiline input, submit, exit confirmation.
- `CompletionMenu`: slash commands and file mentions.
- `Footer`: fixed one-row model/context/runtime status.
- `ModalHost`: resume/model/theme/skills picker views.

## Runtime Rendering

Live runtime rendering must match terminal behavior rather than manual word
wrapping. Thinking text should be preserved as text with original newlines and
rendered in a wrapping viewport. The renderer should not split by words to force
new lines, and it should not flatten everything into one prompt line.

Runtime events must remain ordered:

```text
> user input
[Thinking]
thinking before tool
[Read] src/lib.rs ok
[Thinking]
thinking after tool
Deepy
assistant response
turn Token Usage ...
```

Tool events must be separate blocks. Tool labels and summaries must not be
appended to a thinking block.

## Modal And Command Strategy

All modal interactions should be owned by the Application:

- `/resume` opens a modal view backed by async session previews.
- `/model`, `/theme`, and `/skills` reuse the same modal host pattern.
- Esc closes the active modal before it interrupts a running turn.
- Cancellation returns focus to the input editor without corrupting footer or
  completion state.

If a legacy picker is useful, its rendering or list-navigation logic may be
copied into a component. Its blocking `run()` API should not remain in the
interactive path.

## Deletion Strategy

The implementation should classify old UI code into three groups:

- **Delete**: prompt-router glue, bottom-toolbar/inline-footer shims, nested
  picker `run()` calls in interactive paths, tests for obsolete behavior.
- **Move or adapt**: pure formatting helpers, theme styles, command metadata,
  completion source logic.
- **Preserve outside UI**: model/tool/session/config/core command semantics.

No compatibility layer should be added just to keep old internal UI imports
alive. Call sites should move to the new architecture.

## Test Strategy

Acceptance requires both unit tests and PTY tests.

Unit tests:

- reducer transitions for idle/running/modal/exiting;
- event ordering for thinking/tool/thinking;
- footer truncation to one row;
- completion state and modal state;
- transcript commit from runtime blocks.

PTY tests:

- startup footer is truly at the terminal bottom;
- no large blank gap below footer;
- `/` and `@` completions are visible at the bottom;
- long thinking wraps naturally and scrolls without corrupting input/footer;
- tool blocks stay separate from thinking blocks;
- `/resume` does not crash or emit un-awaited coroutine warnings;
- `/exit`, Esc, Ctrl-C, and Ctrl-D paths exit or cancel cleanly.

## Migration Plan

1. Contain the failed UI attempt.
   - Keep the existing superseded note on `global-tui-runtime-ui`.
   - Identify dirty/obsolete files from the failed prompt-router attempt.
   - Remove or quarantine code that fights the clean Application owner.

2. Build the new shell next to the old entry point.
   - Introduce the new UI package, state, actions, reducer, controller, layout,
     and core components.
   - Connect a minimal idle prompt, footer, submit, and `/exit`.

3. Port runtime behavior.
   - Feed model stream events into runtime blocks.
   - Commit final transcript from the same block model.
   - Keep footer/input/completions stable while turns run.

4. Port commands and modal flows.
   - Move slash commands, local commands, `/resume`, `/model`, `/theme`, and
     `/skills` into Application-owned flows.

5. Delete old UI paths.
   - Remove obsolete prompt input/router/runtime/picker code once the new path
     covers the behavior.
   - Replace obsolete tests with architecture-level tests.

6. Validate.
   - Run PTY regressions, focused unit tests, `ruff`, `ty`, full pytest, and
     OpenSpec strict validation.

## Open Questions

None for proposal scope. Exact module names and visual microcopy can be decided
during implementation as long as the ownership, component, and compatibility
boundaries above are preserved.
