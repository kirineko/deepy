## 1. Shared Syntax Resolution

- [x] 1.1 Add a shared syntax helper for normalizing language tags and file paths.
- [x] 1.2 Map conservative XML-family languages and paths to XML highlighting, including XML, SVG, XAML, C# project files, MSBuild props/targets, and well-known XML config files.
- [x] 1.3 Keep existing Rich/Pygments guessing and plain-text fallback behavior for non-XML and unknown languages.

## 2. Stable Markdown Code Blocks

- [x] 2.1 Route stable terminal fenced code block rendering through the shared syntax helper.
- [x] 2.2 Rebase syntax token backgrounds to the active code block background while preserving token foreground styles.
- [x] 2.3 Add focused tests for XML code block background coherence and XML-like language fallback.
- [x] 2.4 Add regression coverage that already supported code block languages still receive syntax styling.

## 3. Shared Diff Rendering

- [x] 3.1 Replace per-line syntax highlighting in diff previews with per-section old/new-side highlighting and line-span remapping.
- [x] 3.2 Preserve existing diff gutters, added/removed backgrounds, marker styles, width padding, truncation, and multi-file section behavior.
- [x] 3.3 Add stable terminal diff tests for multiline XML attributes, comments, CDATA, and XML-like file paths.
- [x] 3.4 Add regression tests for mainstream non-XML diff highlighting such as Python, Rust, JavaScript/TypeScript, JSON, YAML, TOML, CSS, shell, and SQL.

## 4. Experimental Textual TUI Diff

- [x] 4.1 Ensure Textual TUI diff rendering uses the shared diff syntax behavior without changing final-message Textual Markdown rendering.
- [x] 4.2 Add TUI diff tests for multiline XML and XML-like files.
- [x] 4.3 Add TUI diff regression coverage for an existing non-XML language.

## 5. Validation

- [x] 5.1 Run `openspec validate improve-xml-syntax-highlighting --type change --strict`.
- [x] 5.2 Run focused tests for markdown, message view, and TUI diff rendering.
- [x] 5.3 Run `uv run ruff check src tests`.
- [x] 5.4 Run `uv run ty check src`.
