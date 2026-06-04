## Why

Recent usage logs show repeated retryable `Read` failures when the assistant
requests a line range as JSON-like `range: 80-120` instead of the schema-valid
string form `range: "80-120"`. The same logs also expose a usability gap in
`@` file mentions: users expect short fragments such as one letter to reveal
matching nested files and directories, but the current completion only deep
searches after longer fragments or explicit directory scopes.

## What Changes

- Make `Read` more resilient to the common unquoted line-range argument shape
  while preserving the canonical schema and retryable invalid-argument behavior
  for unsafe malformed inputs.
- Improve `Read` tool guidance so model calls prefer schema-valid range examples
  for single-target and multi-target reads.
- Extend `@` file mention completion so short non-empty fragments can fuzzy
  match nested project files and directories in both the stable terminal UI and
  the experimental Textual TUI, subject to the existing ignore rules and result
  limits.
- Preserve the current bare `@` behavior of showing top-level project entries
  without immediately flooding the completion menu with deep project paths.
- Add an experimental TUI prompt shortcut where pressing Esc followed by a
  deletion key clears the current draft in one step, matching the stable UI's
  user-facing editing ergonomics.
- Keep existing slash command completion and input suggestion precedence
  unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `file-tools-v3`: `Read` argument handling gains a narrow recovery path for
  unquoted line-range values and clearer model-facing guidance for range usage.
- `terminal-ui`: `@` file mention completion gains short-fragment fuzzy search
  across nested project files and directories.
- `experimental-textual-tui`: Textual prompt input gains matching short-fragment
  file mention fuzzy search and an Esc-then-delete draft clearing shortcut.

## Impact

- Affected code likely includes `src/deepy/tools/agents.py` for model-facing
  tool descriptions and conservative argument repair, `src/deepy/tools/builtin.py`
  if range normalization needs to remain close to `Read` parsing, and
  `src/deepy/ui/file_mentions.py` / `src/deepy/tui/widgets.py` for candidate
  discovery strategy and prompt editing behavior.
- Focused tests should cover malformed `Read` range repair, batch `Read` range
  repair, unsafe malformed input remaining retryable, short-fragment file
  mention fuzzy search, ranking stability, ignore filtering, and slash
  completion interaction.
- No dependency or public CLI changes are expected.
