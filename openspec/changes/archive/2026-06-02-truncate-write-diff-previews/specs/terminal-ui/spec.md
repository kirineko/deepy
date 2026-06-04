## MODIFIED Requirements

### Requirement: Width-Aware Diff Preview Rendering

Deepy SHALL render file change previews with a unified write/edit diff style
whose changed-line backgrounds fill the available terminal width and whose large
`Write` and `Update` previews are bounded by the shared diff preview line limit.

#### Scenario: Successful file mutation with diff preview omits redundant summary
- **WHEN** Deepy renders a successful `Write` or `Update` result that includes a
  diff preview
- **THEN** the stable terminal UI SHALL render the diff header and diff preview
- **AND** it SHALL omit the generic successful tool summary line
- **AND** the diff header SHALL continue to show the tool label, changed file
  path, and added/removed line counts

#### Scenario: Large write preview is truncated
- **WHEN** Deepy renders a `Write` result whose diff preview exceeds the shared
  diff preview line limit
- **THEN** the stable terminal UI SHALL truncate the rendered diff preview
- **AND** it SHALL indicate how many diff lines were truncated

#### Scenario: File mutation without diff preview keeps summary
- **WHEN** Deepy renders a `Write` or `Update` result without a diff preview
- **THEN** the stable terminal UI SHALL keep rendering the tool summary line

#### Scenario: Failed file mutation keeps summary
- **WHEN** Deepy renders a failed or retryable `Write` or `Update` result
- **THEN** the stable terminal UI SHALL keep rendering the tool summary line
