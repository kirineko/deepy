## ADDED Requirements

### Requirement: Width-Aware Diff Preview Rendering

Deepy SHALL render file change previews with a unified write/edit diff style
whose changed-line backgrounds fill the available terminal width.

#### Scenario: Edit preview renders full-width changed lines

- **WHEN** Deepy renders a successful `edit` tool result with added or removed
  lines
- **THEN** each added or removed preview line SHALL use the active diff palette
  background across the available terminal width
- **AND** unchanged context lines SHALL remain visually quieter than changed
  lines

#### Scenario: Write preview uses the edit diff visual model

- **WHEN** Deepy renders a successful `write` tool result with generated file
  content
- **THEN** the preview SHALL use the same diff line gutter, marker, and
  added/removed background style as edit previews
- **AND** the header MAY still identify the operation as `Wrote`

#### Scenario: Large write preview remains complete

- **WHEN** Deepy renders a successful `write` tool result with more lines than
  the edit preview line limit
- **THEN** the write preview SHALL keep showing the complete write diff preview
- **AND** it SHALL NOT apply the edit preview truncation policy solely because
  the visual style is unified

#### Scenario: Dark and light themes render readable changed lines

- **WHEN** the active UI theme resolves to `dark` or `light`
- **AND** Deepy renders write or edit diff preview changed lines
- **THEN** the changed-line gutter, marker, content, and terminal-width fill
  SHALL use palette-controlled colors that remain legible for that theme

#### Scenario: Programming language content receives syntax highlighting

- **WHEN** Deepy renders a write or edit diff preview for a path whose
  programming language can be inferred
- **THEN** added and removed line content SHALL use Rich/Pygments syntax token
  highlighting where available
- **AND** the old/new line number gutter, diff marker styling, and full-width
  added/removed backgrounds SHALL remain controlled by the diff preview palette
