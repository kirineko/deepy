## 1. Baseline And Reproduction

- [x] 1.1 Add or update a scripted PTY test that reproduces thinking/status overlap from the failed `prompt_async` runtime attempt.
- [x] 1.2 Add a PTY regression where a second user prompt is submitted after a model turn and must be accepted exactly once.
- [x] 1.3 Add a PTY regression for an interactive `!` local command followed by another prompt.
- [x] 1.4 Add assertions that runtime status does not persist as duplicated normal scrollback lines.

## 2. Runtime View State

- [x] 2.1 Introduce a runtime view state model for active model turns, including status, elapsed time seed, thinking text, tool calls, tool outputs, final text, usage, and interruption state.
- [x] 2.2 Introduce a local-command runtime state model for command text, elapsed time seed, output, exit status, and interruption state.
- [x] 2.3 Add reducer functions that update runtime state from `DeepyStreamEvent` without printing to the terminal.
- [x] 2.4 Add unit tests for thinking deltas, tool call/output pairs, status updates, usage events, and final transcript data.

## 3. Transcript Commit Rendering

- [x] 3.1 Add a transcript commit renderer that prints completed model-turn state after the runtime UI releases ownership.
- [x] 3.2 Preserve existing Markdown assistant output rendering in transcript commit.
- [x] 3.3 Preserve complete thinking text with readable line breaks in transcript commit.
- [x] 3.4 Preserve tool summaries, shell output blocks, todo boards, and diff previews in transcript commit.
- [x] 3.5 Add unit tests that committed transcript output matches the important existing visible output.

## 4. Global Prompt Shell

- [x] 4.1 Refactor `InteractivePromptSession` into a global prompt shell/controller that can keep one prompt read active across idle and running states.
- [x] 4.2 Add attach/detach APIs for a running view delegate that renders runtime state through prompt-toolkit.
- [x] 4.3 Route prompt invalidation through the shell/controller with throttling for high-frequency stream updates.
- [x] 4.4 Keep existing idle prompt behavior, history, slash completion, file mentions, Ctrl+J, Ctrl+D, and footer rendering intact.

## 5. Running Input Routing

- [x] 5.1 Define a running input policy for Esc, Ctrl-C, Enter, Ctrl+J, Ctrl+D, and ordinary text.
- [x] 5.2 Implement interrupt routing so Esc/Ctrl-C requests cancellation of model turns and local commands.
- [x] 5.3 Implement queue-or-ignore behavior for ordinary text submitted while a model turn is running.
- [x] 5.4 Add tests proving running input cannot accidentally become an idle prompt before runtime finishes.

## 6. Model Runtime Migration

- [x] 6.1 Replace active model-turn `TerminalStreamRenderer` printing with runtime state reducer updates while the running view is attached.
- [x] 6.2 Render model runtime status, thinking preview/header, tool progress, interruption hint, and compact footer through the global prompt shell.
- [x] 6.3 Commit final model transcript only after the running view detaches.
- [x] 6.4 Verify repeated model turns leave the idle prompt usable.

## 7. Local Command Runtime Migration

- [x] 7.1 Run interactive `!` local commands through the same global prompt shell runtime path.
- [x] 7.2 Render command text, elapsed time, interrupt hint, and compact footer through the running view.
- [x] 7.3 Commit command output and transcript persistence after the running view detaches.
- [x] 7.4 Verify local command interruption and post-command prompt recovery.

## 8. Cleanup And Guardrails

- [x] 8.1 Remove or narrow obsolete runtime delegate code that duplicates the new runtime view state.
- [x] 8.2 Ensure no active runtime path uses `_TerminalBottomStatus`, ANSI scroll regions, or normal Rich status lines for footer ownership.
- [x] 8.3 Keep existing modal picker Applications working as blocking flows until a later full-Application migration.
- [x] 8.4 Document the boundary between live runtime view rendering and committed transcript rendering.

## 9. Verification

- [x] 9.1 Run focused prompt input, terminal UI, runtime view state, and transcript commit unit tests.
- [x] 9.2 Run PTY tests for long input, model runtime, thinking output, local command runtime, second prompt recovery, and interruption.
- [x] 9.3 Run `ruff`, `ty`, and the full pytest suite.
- [x] 9.4 Run `openspec validate global-tui-runtime-ui --type change --strict`.
