## Why

Deepy's write and edit previews currently render with different visual styles,
and changed-line backgrounds stop at the end of the code text instead of filling
the terminal row. This makes large generated changes look fragmented and makes
write previews feel disconnected from edit previews.

## What Changes

- Use a unified diff preview visual style for both `write` and `edit` tool
  results.
- Render added and removed line backgrounds across the available terminal width
  instead of only behind the code text.
- Preserve `write` previews for large files without applying the edit preview
  line truncation policy.
- Keep unchanged/context lines visually quiet while changed lines form a
  continuous block.
- Validate rendering in both dark and light UI themes so background fills remain
  legible.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Tool diff previews should render write/edit changes with a
  unified, terminal-width-aware, theme-safe visual style.

## Impact

- Affected code: Rich rendering for tool diff previews, stream/history tool
  output rendering, and UI palette usage.
- Affected tests: message view and terminal UI rendering tests for edit/write
  previews, large write previews, and dark/light theme contrast.
- No tool schema, session format, model contract, or CLI command changes are
  expected.
