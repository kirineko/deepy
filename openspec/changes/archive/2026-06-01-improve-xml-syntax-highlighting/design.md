## Context

Deepy has multiple terminal rendering paths that can show code:

- Stable assistant Markdown code blocks are rendered by `deepy.ui.markdown`.
- Stable file mutation diff previews are rendered by `deepy.ui.message_view`.
- Experimental Textual TUI diff blocks reuse the shared diff renderer through
  `deepy.tui.diff`.
- Experimental Textual TUI assistant Markdown currently uses Textual's Markdown
  widget, so full parity for final-message fenced code would require separate
  Textual integration work.

The current diff highlighter chooses a lexer per diff preview and then
highlights each changed line independently. This loses lexer state for XML
constructs that span lines, such as split tags, multiline attributes, comments,
and CDATA. Stable Markdown code blocks also preserve syntax token backgrounds
from the Rich/Pygments theme, which can conflict with Deepy's code-block
background and create patchy color blocks.

## Goals / Non-Goals

**Goals:**

- Make stable terminal XML and XML-like fenced code blocks visually coherent.
- Make stable and Textual TUI diff previews preserve XML syntax highlighting
  across multiline tags, attributes, comments, and CDATA.
- Normalize common XML-family languages and paths such as `xml`, `svg`, `xaml`,
  `csproj`, `.props`, `.targets`, and well-known `.config` project files to XML
  highlighting when appropriate.
- Keep existing added/removed diff backgrounds, gutters, markers, truncation,
  and fallback behavior.
- Avoid new runtime dependencies.

**Non-Goals:**

- Replacing Textual's built-in Markdown renderer for final assistant messages.
- Changing diff generation, mutation tool payloads, or session transcript data.
- Building a custom lexer or parser for XML.
- Expanding syntax highlighting to every possible niche extension.

## Decisions

1. Add a shared syntax-language normalization helper.

   Rendering paths should resolve language tags and file paths through a small
   shared helper before constructing `Syntax`. The helper should use explicit
   XML-family mappings first, then keep existing Rich/Pygments guessing behavior
   for other languages. This avoids duplicating ad hoc extension rules across
   Markdown, stable diff previews, and TUI diff previews.

   Alternative considered: rely entirely on `Syntax.guess_lexer`. That leaves
   `*.svg`, `*.csproj`, `*.xaml`, and similar files on the current plain-text
   fallback path.

2. Rebase syntax token backgrounds to the active surface background.

   Markdown code block rendering should keep syntax token foreground styles but
   replace token backgrounds with Deepy's selected code-block background. Diff
   rendering should keep using added/removed backgrounds for changed lines. This
   preserves highlighting while removing patchy token background blocks.

   Alternative considered: choose a Rich theme whose background matches Deepy's
   palette exactly. That is brittle across light/dark palettes and does not solve
   diff surfaces where each changed line has a semantic background.

3. Highlight diff content by old/new side before mapping spans back to lines.

   For each parsed file diff section, build one source stream from removed plus
   context lines and one target stream from added plus context lines. Highlight
   each stream once, then map spans back onto the corresponding visible diff
   lines. This preserves lexer state for multiline XML while keeping per-line
   diff rendering intact.

   Alternative considered: add XML-specific heuristics to individual lines. That
   would be fragile for comments, CDATA, namespaces, and other lexer state.

4. Keep Textual final-message Markdown out of this change.

   The TUI diff path already routes through Deepy's shared diff renderer and can
   benefit from the same fix. Textual final assistant Markdown is a separate
   widget-level rendering path and should not be partially replaced in this
   narrowly scoped change.

## Risks / Trade-offs

- Span mapping errors could shift colors by one character. Mitigation: add
  focused tests for multiline XML attributes, comments, CDATA, and existing
  Python/Rust diff cases.
- Whole-stream highlighting may cost more than per-line highlighting. Mitigation:
  apply it only to already-limited preview sections and keep the existing
  truncation budget.
- XML-family normalization could over-classify generic config files. Mitigation:
  map conservative extensions and well-known filenames only; otherwise keep the
  current fallback behavior.
- Textual final-message fenced code remains governed by Textual's Markdown
  renderer. Mitigation: document that this change targets stable Markdown code
  blocks and shared diff previews; consider a later change if final-message TUI
  parity becomes necessary.
