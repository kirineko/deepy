## Why

Localhost GPT-5.6 turns can consume reasoning tokens while `/view full` shows no
Thinking block. Other providers display thinking normally. Local CLIProxyAPI
only streams visible Responses reasoning text when `reasoning.summary` is set;
Deepy currently sends only `reasoning.effort`.

## What Changes

- When localhost thinking is enabled, `ModelSettings.reasoning` SHALL include
  `summary = "auto"` in addition to the selected effort.
- When localhost thinking mode is `none`, Deepy SHALL continue to send
  `reasoning.effort = "none"` and SHALL NOT request a reasoning summary.
- Preserve existing usage/store settings and avoid chat-style thinking
  `extra_body` payloads on the Responses path.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `deepseek-provider`: Localhost Responses Provider Model Settings must request
  a Responses reasoning summary whenever thinking is enabled so the existing
  `reasoning_delta` UI path can render Thinking output.

## Impact

- Affected code: `src/deepy/llm/thinking.py`, localhost model-settings tests.
- No UI changes; classic/modern already render `reasoning_delta` in full view.
- No config schema changes.
