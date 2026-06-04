## 1. Baseline And Deletion Boundary

- [x] 1.1 Add a superseded note to `global-tui-runtime-ui` so it is not archived as the accepted terminal UI architecture.
- [x] 1.2 Inventory UI files changed by the failed prompt-router/runtime attempt and classify each as delete, move/adapt, or preserve-outside-UI.
- [x] 1.3 Define the public compatibility boundary: CLI command syntax, session persistence, model routing, tool execution, local commands, and config semantics.
- [x] 1.4 Remove or quarantine code paths that require competing terminal ownership before wiring the new Application as the default.
- [x] 1.5 Update `docs/terminal-ui.md` to describe the clean-slate Application architecture and the superseded prompt-router boundary.

## 2. Regression Harness For Known Failures

- [x] 2.1 Add PTY helpers that can assert terminal row placement, visible bottom footer, completion visibility, and process exit without relying on screenshots.
- [x] 2.2 Add a PTY regression that startup renders the footer on the actual terminal bottom row with no large blank area below it.
- [x] 2.3 Add a PTY regression for `/resume` without arguments that proves no nested `asyncio.run()` crash or un-awaited coroutine warning occurs.
- [x] 2.4 Add a PTY regression for long thinking text that wraps naturally, scrolls in the viewport, and leaves input/footer usable.
- [x] 2.5 Add a PTY regression for thinking-tool-thinking ordering where tool output is not appended to thinking text and later thinking remains visible.
- [x] 2.6 Add PTY regressions for `/` and `@` completions when the prompt is already at the terminal bottom.
- [x] 2.7 Strengthen `/exit`, Esc, Ctrl-C, and Ctrl-D PTY tests so the process exits or cancels cleanly after model turns, local commands, and modal flows.

## 3. New Application Architecture Scaffold

- [x] 3.1 Create the new terminal UI package with Application builder, controller, state/reducer, events/actions, layout, components, and adapters.
- [x] 3.2 Implement idle/running/modal/exiting state transitions in reducer-level unit tests before connecting model effects.
- [x] 3.3 Build the root layout with transcript/runtime viewport, completion/menu region, modal host, bounded input editor, and fixed one-row footer.
- [x] 3.4 Implement the controller effect loop for input submission, slash-command routing, turn execution, modal open/close, interruption, and shutdown.
- [x] 3.5 Connect the new Application shell from `run_interactive` through a narrow entry-point API.

## 4. Core Components

- [x] 4.1 Implement `Footer` as a real one-row bottom component with truncation/elision for long model/cwd/context/status content.
- [x] 4.2 Implement `InputEditor` with Enter submit, Ctrl+J newline, bounded height, Ctrl+D confirmation, and focus restore after modal/turn completion.
- [x] 4.3 Implement `CompletionMenu` using existing slash command and file mention sources but Application-owned rendering.
- [x] 4.4 Implement `TranscriptViewport` with committed messages and live runtime blocks in a scrollable region.
- [x] 4.5 Implement `ModalHost` and a shared picker component contract for resume/model/theme/skills.

## 5. Runtime Event Pipeline

- [x] 5.1 Define ordered runtime block state for user input, thinking blocks, tool blocks, local command output, assistant output, usage, and errors.
- [x] 5.2 Feed model stream events into runtime blocks without direct terminal writes during active runtime.
- [x] 5.3 Render live thinking with natural terminal-width wrapping and preserved explicit newlines.
- [x] 5.4 Render tool calls and outputs as distinct ordered blocks between thinking blocks.
- [x] 5.5 Commit final transcript from the same ordered runtime blocks after the turn finishes.
- [x] 5.6 Ensure runtime status updates the fixed footer in place and is not duplicated as repeated scrollback lines.

## 6. Commands, Modals, And Session Flows

- [x] 6.1 Migrate slash-command dispatch into the Application controller while preserving command syntax.
- [x] 6.2 Migrate local command execution and transcript persistence into async controller effects.
- [x] 6.3 Migrate `/resume` to an Application modal with awaited async session preview loading.
- [x] 6.4 Migrate `/model`, `/theme`, and `/skills` to the shared modal host.
- [x] 6.5 Verify Esc behavior closes modals first, interrupts running turns second, and never corrupts input/footer state.

## 7. Remove Historical UI Code

- [x] 7.1 Delete obsolete prompt-router delegates, inline footer shims, and `PromptSession.bottom_toolbar` ownership paths.
- [x] 7.2 Delete or rewrite old picker blocking `run()` APIs from interactive paths.
- [x] 7.3 Delete obsolete `runtime_prompt`/`runtime_view` helpers that flatten runtime output into prompt fragments.
- [x] 7.4 Replace obsolete tests that assert old prompt-session behavior with Application-level tests.
- [x] 7.5 Keep only pure helpers that are reused by the new architecture, such as stable formatting, theme, or completion-source logic.

## 8. Verification

- [x] 8.1 Run focused reducer, component, completion, modal, runtime-block, and transcript-commit tests.
- [x] 8.2 Run PTY regressions for startup footer, no blank bottom gap, completions, long thinking, tool ordering, `/resume`, local commands, interruption, and `/exit`.
- [x] 8.3 Run `ruff`.
- [x] 8.4 Run `ty`.
  - Changed UI source/tests pass focused `ty`; full-repo `uv run ty check` still reports existing test typing diagnostics outside this UI change.
- [x] 8.5 Run the full pytest suite.
- [x] 8.6 Run `openspec validate rebuild-terminal-application-ui --type change --strict`.

## 9. Manual Acceptance Fixes

- [x] 9.1 Restore Modify/Write diff previews to the tuned added/removed diff renderer, including Modify tool output.
- [x] 9.2 Add output scroll key support and keep input bounded/multiline scroll behavior while preserving prompt history on Up/Down.
- [x] 9.3 Migrate `/compact` into the TUI controller and keep auto-compact footer context status visible.
- [x] 9.4 Clean MCP servers before Application exit completes and clear active server state after cleanup.
- [x] 9.5 Move running status text out of the footer into a dedicated runtime status row with distinct background styling.
- [x] 9.6 Keep AskUserQuestion turns waiting for user input without committing a turn-ending usage line before the answer.
- [x] 9.7 Re-run PTY, component, AskUserQuestion, MCP, diff, compaction, tools, shell, full pytest, `ruff`, `ty`, and OpenSpec strict validation.
