## 1. Regression Coverage

- [x] 1.1 Add message view tests showing `edit` added/removed lines fill to a provided preview width.
- [x] 1.2 Update write preview tests so `write` uses the same diff line gutter, marker, and changed-line styles as `edit`.
- [x] 1.3 Add a large write preview test proving writes over `MAX_DIFF_LINES` are still not truncated.
- [x] 1.4 Add dark theme and light theme tests for changed-line span styles after width fill.
- [x] 1.5 Add terminal stream rendering coverage proving live tool output passes console width into diff preview rendering.

## 2. Width-Aware Rendering

- [x] 2.1 Add an optional width parameter to `render_tool_diff_preview()` and related diff preview line rendering helpers.
- [x] 2.2 Implement changed-line padding with palette-controlled background styles so added/removed lines fill the available width.
- [x] 2.3 Use Rich cell measurement or equivalent display-cell accounting so padding remains correct with wide characters.
- [x] 2.4 Keep context/unchanged lines visually quiet and avoid applying full-width added/removed backgrounds to them.

## 3. Write/Edit Style Unification

- [x] 3.1 Remove the separate write preview line visual path or make it delegate to the shared diff line renderer.
- [x] 3.2 Preserve operation-specific headers so write previews still say `Wrote` and edit previews still say `Edited`.
- [x] 3.3 Preserve the existing write no-truncation behavior while edit previews continue to use `MAX_DIFF_LINES`.
- [x] 3.4 Remove or repurpose obsolete write-specific palette usage only if it is no longer needed by any UI path.

## 4. Terminal Integration

- [x] 4.1 Pass `console.width` from live tool output rendering into `render_tool_diff_preview()`.
- [x] 4.2 Pass a best-effort width from history/message rendering paths where a console width is available.
- [x] 4.3 Keep non-width-aware fallback behavior stable for call sites that cannot provide terminal width.

## 5. Verification

- [x] 5.1 Run focused message view and terminal UI tests.
- [x] 5.2 Run style/theme tests related to palette contrast.
- [x] 5.3 Run the broader relevant UI test suite.
- [x] 5.4 Manually inspect a write preview and an edit preview in a dark terminal theme.
- [x] 5.5 Manually inspect or snapshot a write preview and an edit preview in a light terminal theme.

## 6. Syntax Highlighting

- [x] 6.1 Use Rich/Pygments to infer a programming language lexer from the changed file path and diff content.
- [x] 6.2 Apply syntax token styles to added/removed content while preserving diff palette backgrounds, gutters, markers, and width fill.
- [x] 6.3 Add dark and light theme regression tests proving syntax highlighting does not reintroduce syntax theme backgrounds.
- [x] 6.4 Run focused message view, terminal UI, style, and lint checks after the syntax-highlighting change.
