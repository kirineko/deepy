## ADDED Requirements

### Requirement: Syntax Highlighting Consistency
Deepy SHALL render syntax-highlighted terminal code and diff content with
surface-consistent backgrounds and XML-family language recognition.

#### Scenario: XML code block uses a coherent background
- **WHEN** the stable terminal UI renders an assistant Markdown fenced code block
  tagged as XML or a recognized XML-family language
- **THEN** syntax-highlighted token foreground colors SHALL remain visible
- **AND** token backgrounds SHALL match the code block background instead of
  creating patchy theme-background blocks

#### Scenario: XML diff preserves multiline syntax
- **WHEN** the stable terminal UI renders a `Write` or `Update` diff preview for
  XML content with multiline tags, attributes, comments, or CDATA
- **THEN** Deepy SHALL preserve XML syntax highlighting across the related diff
  lines
- **AND** added and removed line backgrounds, gutters, markers, and truncation
  behavior SHALL remain unchanged

#### Scenario: XML-like files use XML highlighting
- **WHEN** the stable terminal UI renders code or diff content for a recognized
  XML-family file type such as SVG, XAML, C# project files, MSBuild props or
  targets files, or well-known XML-based config files
- **THEN** Deepy SHALL use XML syntax highlighting instead of falling back to
  unhighlighted plain text

#### Scenario: Non-XML syntax highlighting is preserved
- **WHEN** the stable terminal UI renders code or diff content for already
  supported mainstream languages such as Python, JavaScript, TypeScript, TSX,
  JSON, YAML, TOML, Rust, CSS, shell, or SQL
- **THEN** Deepy SHALL preserve existing syntax highlighting behavior
- **AND** unsupported or unknown languages SHALL continue to fall back to
  readable plain text rather than failing rendering
