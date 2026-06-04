## ADDED Requirements

### Requirement: Breaking File Tool History Boundary
Deepy SHALL treat the v3 file tool rewrite as a breaking history boundary paired
with the session/history storage rewrite.

#### Scenario: Old file-tool transcript is encountered
- **WHEN** Deepy encounters old persisted session content that contains
  `read_file`, `edit_text`, `write_file`, or `apply_patch` tool calls or results
  after the v3 file tool release
- **THEN** Deepy SHALL NOT be required to replay, resume, execute, or render
  those old file-tool records through compatibility shims
- **AND** it MAY report that the old session content is unsupported by the
  current breaking release

#### Scenario: New session records v3 file tools
- **WHEN** a new model turn records file tool activity after the v3 file tool
  release
- **THEN** session history SHALL persist the model-visible `Read`, `Write`, and
  `Update` calls and results as the canonical file-tool records
- **AND** it SHALL NOT synthesize old v2 file-tool records for compatibility
