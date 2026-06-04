## ADDED Requirements

### Requirement: Task-Focused Audit Approval Panels

Deepy's stable terminal UI SHALL render audit approval prompts as concise
task-focused decision panels rather than raw SDK argument dumps.

#### Scenario: Shell command approval uses task summary

- **WHEN** an SDK approval interruption requests a shell command execution
- **THEN** Deepy SHALL show a title that identifies the request as a shell
  command approval
- **AND** it SHALL show the command as the primary target
- **AND** it SHALL show meaningful secondary context such as description or
  working directory when available
- **AND** it SHALL NOT show raw internal field labels such as `action`, `agent`,
  or `arguments.*` unless no typed summary can be derived

#### Scenario: MCP approval uses server and tool summary

- **WHEN** an SDK approval interruption requests an MCP tool call
- **THEN** Deepy SHALL show a title that identifies the request as an MCP tool
  approval
- **AND** it SHALL show the MCP server and tool as the primary target
- **AND** it SHALL show only the most relevant bounded argument fields, such as
  `url`, `urls`, `query`, or `format`, when available
- **AND** it SHALL NOT render the full raw argument JSON by default

#### Scenario: Unknown approval falls back to bounded summary

- **WHEN** an SDK approval interruption cannot be classified as shell, file
  mutation, or MCP
- **THEN** Deepy SHALL show the tool name and a bounded structured argument
  summary
- **AND** the fallback summary SHALL remain visually distinct from normal
  assistant messages

### Requirement: File Mutation Approval Diff Review

Deepy's stable terminal UI SHALL render `Write` and `Update` audit approvals
with highlighted diff previews and relative target paths when possible.

#### Scenario: Write approval shows new-file diff

- **WHEN** an SDK approval interruption requests writing content to a file under
  the active project root
- **THEN** Deepy SHALL display the file path relative to the project root
- **AND** it SHALL show a highlighted diff preview representing the proposed new
  file content
- **AND** it SHALL keep the final decision area limited to `Approve` and
  `Reject`

#### Scenario: Update approval shows changed lines

- **WHEN** an SDK approval interruption requests updating content in a file
- **AND** the approval arguments contain enough before-and-after information to
  derive a diff
- **THEN** Deepy SHALL display the file path relative to the project root when
  the file is under that root
- **AND** it SHALL show a highlighted diff preview that includes removed and
  added lines

#### Scenario: File path outside project remains explicit

- **WHEN** an SDK approval interruption targets a file outside the active project
  root
- **THEN** Deepy SHALL NOT display the path as project-relative
- **AND** it SHALL display a home-relative path when possible or the absolute
  path otherwise

#### Scenario: Truncated diff exposes inspect control above decisions

- **WHEN** a `Write` or `Update` diff preview exceeds the compact preview budget
- **THEN** Deepy SHALL render an auxiliary expand control above the final
  `Approve` and `Reject` decision area
- **AND** activating the expand control SHALL show the expanded diff without
  approving or rejecting the tool call
- **AND** activating the collapse control SHALL restore the compact diff without
  approving or rejecting the tool call

#### Scenario: Missing update diff context uses safe fallback

- **WHEN** an `Update` approval does not contain enough before-and-after
  information to derive a reliable diff
- **THEN** Deepy SHALL show a compact typed summary instead of fabricating a diff
- **AND** it SHALL still display the target path using the relative-path rules

### Requirement: Approval Prompt Keyboard Interaction

Deepy's stable terminal approval picker SHALL resolve approvals only through
navigation selection, `Enter`, and `Esc`.

#### Scenario: Arrow keys move selection

- **WHEN** an approval prompt is active
- **AND** the user presses `Up` or `Down`
- **THEN** Deepy SHALL move the selection among visible approval controls,
  including auxiliary inspect controls and final decisions
- **AND** it SHALL NOT approve or reject the tool call only because selection
  moved

#### Scenario: Enter activates selected control

- **WHEN** an approval prompt is active
- **AND** the user presses `Enter`
- **AND** the selected control is `Approve` or `Reject`
- **THEN** Deepy SHALL resolve the SDK approval with the selected decision

#### Scenario: Enter on inspect control does not resolve approval

- **WHEN** an approval prompt is active
- **AND** the selected control is an auxiliary expand or collapse control
- **AND** the user presses `Enter`
- **THEN** Deepy SHALL toggle the displayed preview state
- **AND** it SHALL keep the approval prompt active

#### Scenario: Escape rejects approval

- **WHEN** an approval prompt is active
- **AND** the user presses `Esc`
- **THEN** Deepy SHALL resolve the SDK approval as rejected

#### Scenario: Letter shortcuts do not resolve approval

- **WHEN** an approval prompt is active
- **AND** the user presses `Y`, `A`, `N`, `R`, or their lowercase equivalents
- **THEN** Deepy SHALL NOT resolve the SDK approval because of that keypress
- **AND** visible approval hints SHALL NOT advertise those letter shortcuts
