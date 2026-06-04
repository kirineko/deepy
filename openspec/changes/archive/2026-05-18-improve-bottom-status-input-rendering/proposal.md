## Why

Deepy's multiline prompt input can grow into the terminal bottom area when the
user composes a long prompt near the bottom of the screen. Initial attempts to
make prompt input, runtime status, and the compact footer share a fixed bottom
contract proved too invasive: prompt-toolkit, Rich output, and Deepy's ANSI
runtime footer can compete for the same rows and produce regressions.

This change is archived as the safe, narrow portion that survived terminal
testing: cap the visible prompt input height and keep prompt cleanup compatible
with the installed prompt-toolkit API. A larger prompt-toolkit-owned runtime UI
will be handled by a follow-up proposal.

## What Changes

- Use a Deepy prompt session subclass to cap the visible multiline input buffer
  height so long input scrolls inside the prompt area.
- Reserve a small amount of terminal height when calculating the input cap so
  the prompt footer has room to render.
- Configure `erase_when_done` at prompt session creation instead of passing it
  to `PromptSession.prompt()`, which is unsupported by the installed
  prompt-toolkit version.
- Do not change Deepy's runtime status overlay behavior in this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Improve multiline prompt input viewport behavior without
  changing model turn rendering, local command rendering, or footer ownership.

## Impact

- Affected code:
  - `src/deepy/ui/prompt_input.py`
- Affected tests:
  - `tests/test_prompt_input.py`
- No new runtime dependency is expected.
- No public CLI command syntax changes are expected.

## Follow-up

The broader bottom-area problem remains architectural. The follow-up change
will move running model/local-command UI into a prompt-toolkit-owned runtime
surface and will make `_TerminalBottomStatus` removable after the refactor.
