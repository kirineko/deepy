## 1. Baseline And Test Harness

- [x] 1.1 Add or extend a Unix PTY integration harness for Deepy interactive sessions with configurable terminal width and height.
- [x] 1.2 Add a failing PTY regression for a long multiline prompt that reaches the terminal bottom before submission.
- [x] 1.3 Add a failing PTY regression for model-turn runtime status and footer stability after prompt submission.
- [x] 1.4 Add a failing PTY regression for `!` local-command runtime status and command output stability.

## 2. Prompt Session Ownership Boundary

- [x] 2.1 Introduce a Deepy `InteractivePromptSession` wrapper around prompt-toolkit session creation, prompt submission, invalidation, and footer rendering.
- [x] 2.2 Move existing prompt toolbar/status-footer rendering behind the wrapper without changing idle prompt behavior.
- [x] 2.3 Add attach/detach APIs for a runtime UI delegate that can render status/progress above the editable prompt area.
- [x] 2.4 Ensure prompt cleanup and history behavior remain compatible with the existing Enter, Ctrl+J, Ctrl+D, slash-command, and file-mention flows.

## 3. Model Runtime UI Migration

- [x] 3.1 Create a model-turn runtime delegate that renders elapsed time, spinner, Esc interrupt guidance, active work state, and compact progress blocks through prompt-toolkit.
- [x] 3.2 Route `TerminalStreamRenderer` status/progress updates into the runtime delegate instead of `_TerminalBottomStatus` for interactive TTY model turns.
- [x] 3.3 Keep completed user echo, final assistant output, and usage footer flushing in Rich after the runtime delegate detaches.
- [x] 3.4 Throttle prompt invalidation so thinking/tool deltas do not repaint the footer on every token.

## 4. Local Command Runtime UI Migration

- [x] 4.1 Route interactive `!` local-command runtime status through the same prompt-toolkit runtime delegate model.
- [x] 4.2 Keep command stdout/stderr readable without letting it compete with prompt-toolkit footer placement.
- [x] 4.3 Preserve local command semantics, including not sending local commands to the model and preserving Esc/Ctrl-C interruption behavior.

## 5. Remove Transitional ANSI Runtime Footer

- [x] 5.1 Delete `_TerminalBottomStatus` once model and local-command runtime paths no longer use it.
- [x] 5.2 Remove or rewrite ANSI scroll-region tests that only asserted `_TerminalBottomStatus` internals.
- [x] 5.3 Keep non-TTY fallback behavior intact for captured output and test consoles.

## 6. Verification

- [x] 6.1 Run focused prompt input and terminal UI unit tests.
- [x] 6.2 Run the new PTY integration tests for prompt-at-bottom, model runtime UI, and local-command runtime UI.
- [x] 6.3 Manually verify in a small terminal window that long input, model turns, local commands, and subsequent prompts do not overlap or hide the footer.
- [x] 6.4 Run `openspec validate prompt-toolkit-runtime-ui --type change --strict`.

## 7. Active Prompt-Toolkit Runtime Surface

The experimental active `prompt_async` running-turn surface was implemented and
then reverted after manual testing showed prompt/input corruption and missing
thinking output. Runtime status display is deferred to the follow-up global TUI
proposal instead of being archived in this change.
