## Why

Deepy file mutation tools can still produce noisy user-visible failures when a
model emits almost-correct tool arguments, such as an unquoted `snapshot_id`.
The model often retries successfully, but the terminal transcript shows the
recoverable parse failure as a normal failed edit, which makes the editing
experience feel unstable.

## What Changes

- Add a conservative file-tool argument recovery path for high-confidence,
  schema-validated malformed arguments before returning an invalid-arguments
  failure.
- Add an optional numeric snapshot token alongside existing `snapshot_id` /
  `content_hash` freshness metadata so models can pass a freshness token without
  relying on string identifier quoting.
- Add structured metadata that distinguishes retryable/recoverable argument
  failures from unrecoverable tool failures.
- Update stable terminal UI rendering so malformed file-tool arguments are
  summarized without dumping large raw `content`, `old_text`, `new_text`, or
  patch payloads.
- Update terminal and experimental TUI rendering so recoverable argument
  failures use a quieter retryable state, and the TUI may fold a recovered
  malformed attempt into the later successful tool block.
- Preserve existing file mutation safety: stale snapshots, missing freshness
  tokens for existing-file replacement, path-policy failures, and text-target
  guardrails remain blocking failures.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `tools`: File mutation tools gain conservative argument recovery, numeric
  snapshot freshness tokens, and retryable/recoverable error metadata.
- `terminal-ui`: Tool call/output rendering gains safe malformed-argument
  summaries and quieter retryable failure presentation.
- `experimental-textual-tui`: TUI tool blocks gain safe malformed-argument
  summaries, retryable failure presentation, and recovered-attempt folding.

## Impact

- Affects tool invocation parsing in `src/deepy/tools/agents.py`, managed
  snapshot metadata in `src/deepy/tools/file_state.py` and file mutation result
  metadata in `src/deepy/tools/builtin.py`.
- Affects tool documentation under `src/deepy/data/tools/`, especially
  `read_file`, `write_file`, and `apply_patch`.
- Affects shared rendering helpers in `src/deepy/ui/message_view.py`, stable
  terminal stream rendering in `src/deepy/ui/terminal.py`, and experimental TUI
  tool blocks in `src/deepy/tui/`.
- Requires focused tests for argument recovery, freshness token acceptance,
  safe parameter summaries, retryable status rendering, and TUI recovery
  folding.
