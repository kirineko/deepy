## 1. Prompt Input Viewport

- [x] 1.1 Add a Deepy prompt session subclass that caps the visible multiline input buffer height.
- [x] 1.2 Calculate the cap from a fixed maximum and a small terminal footer reservation.
- [x] 1.3 Keep prompt-toolkit responsible for input-buffer scrolling.

## 2. Prompt Cleanup Compatibility

- [x] 2.1 Move `erase_when_done` configuration to prompt session creation.
- [x] 2.2 Verify `PromptSession.prompt()` is not called with unsupported cleanup arguments.

## 3. Regression Coverage

- [x] 3.1 Cover prompt session construction with `erase_when_done=True`.
- [x] 3.2 Cover visible input height calculation for constrained terminal height.
- [x] 3.3 Cover the prompt session subclass height cap.

## 4. Scope Retraction

- [x] 4.1 Revert prompt footer gaps, forced runtime pre-scroll carving, and self-managed idle footer overlay attempts.
- [x] 4.2 Keep `_TerminalBottomStatus` unchanged in this archived change.
- [x] 4.3 Defer prompt-toolkit-owned runtime UI and eventual `_TerminalBottomStatus` removal to a follow-up proposal.

## 5. Verification

- [x] 5.1 Run `git diff --check`.
- [x] 5.2 Run `openspec validate improve-bottom-status-input-rendering --type change --strict`.
- [x] 5.3 Attempt targeted prompt input tests; note that `uv run pytest tests/test_prompt_input.py` was blocked by environment-level escalation rejection, not by a test failure.
