## Why

XML and XML-like content currently renders inconsistently in terminal output.
Fenced XML code can show blocky mixed backgrounds, while diff previews highlight
some XML lines but lose syntax styling on split tags, attributes, comments, or
CDATA. XML-family files such as SVG, XAML, and project files can also fall back
to plain text.

## What Changes

- Normalize syntax language selection for XML-family code fences and file paths
  so recognized XML-like formats use XML highlighting instead of plain text.
- Keep syntax token colors while rebasing token backgrounds to the active code
  block or diff background, avoiding patchy color blocks in terminal output.
- Highlight diff content with enough old/new-side context for XML lexer state to
  survive multiline tags, attributes, comments, and CDATA.
- Preserve existing diff gutters, added/removed backgrounds, truncation, and
  behavior for non-XML languages.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: stable terminal Markdown code blocks and file-change diff
  previews gain consistent XML-family syntax highlighting.
- `experimental-textual-tui`: Textual TUI diff blocks use the same XML-family
  syntax highlighting behavior as the stable terminal diff renderer.

## Impact

- Affected code is expected around shared terminal rendering helpers,
  `deepy.ui.markdown`, `deepy.ui.message_view`, and `deepy.tui.diff`.
- Focused tests should cover stable Markdown rendering, stable diff preview
  rendering, and Textual TUI diff rendering.
- No CLI, provider, tool API, dependency, or persisted-data format changes are
  expected.
