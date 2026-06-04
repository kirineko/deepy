## ADDED Requirements

### Requirement: Textual Diff Syntax Highlighting Consistency
The experimental Textual TUI SHALL render Deepy-owned diff blocks with the same
XML-family syntax highlighting guarantees as the stable terminal diff renderer.

#### Scenario: TUI diff preserves multiline XML syntax
- **WHEN** the experimental Textual TUI renders a `Write` or `Update` diff block
  for XML content with multiline tags, attributes, comments, or CDATA
- **THEN** the TUI SHALL preserve XML syntax highlighting across the related
  diff lines
- **AND** the diff block SHALL keep readable added and removed line colors,
  gutters, markers, hunk navigation data, and truncation behavior

#### Scenario: TUI diff recognizes XML-like files
- **WHEN** the experimental Textual TUI renders a diff block for a recognized
  XML-family file type such as SVG, XAML, C# project files, MSBuild props or
  targets files, or well-known XML-based config files
- **THEN** the TUI SHALL use XML syntax highlighting instead of falling back to
  unhighlighted plain text

#### Scenario: TUI non-XML diff highlighting is preserved
- **WHEN** the experimental Textual TUI renders diff blocks for already
  supported mainstream languages such as Python, JavaScript, TypeScript, TSX,
  JSON, YAML, TOML, Rust, CSS, shell, or SQL
- **THEN** the TUI SHALL preserve existing syntax highlighting behavior
- **AND** unsupported or unknown languages SHALL continue to fall back to
  readable plain text rather than failing rendering
