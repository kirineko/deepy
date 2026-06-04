## ADDED Requirements

### Requirement: Audit Mode Status Display

Deepy's stable terminal UI SHALL make the active system audit mode visible
during interactive use.

#### Scenario: Prompt footer shows audit mode

- **WHEN** the stable interactive prompt is waiting for user input
- **THEN** the prompt footer SHALL include the active audit mode
- **AND** the footer SHALL keep existing model, working-directory, MCP, and
  context status segments readable

#### Scenario: Status panel shows audit mode

- **WHEN** the user opens a status surface such as `/status`
- **THEN** Deepy SHALL include the active audit mode
- **AND** it SHALL include whether the mode came from runtime state or persisted
  configuration when that distinction is available

### Requirement: Audit Mode Keyboard Cycling

Deepy's stable prompt-toolkit UI SHALL support cycling audit modes with
`Shift+Tab`.

#### Scenario: User cycles audit mode

- **WHEN** the user presses `Shift+Tab` while the stable prompt is active
- **THEN** Deepy SHALL switch to the next audit mode in the order `normal`,
  `auto`, `yolo`, `normal`
- **AND** Deepy SHALL update the visible prompt footer without submitting the
  current prompt text

#### Scenario: Tab completion remains available

- **WHEN** the user presses `Tab` without `Shift`
- **THEN** Deepy SHALL preserve the existing completion and input-suggestion
  behavior
- **AND** it SHALL NOT cycle the audit mode

### Requirement: Approval Prompt Display

Deepy's terminal UI SHALL present SDK approval interruptions as explicit approval
prompts rather than normal assistant questions.

#### Scenario: Built-in tool approval prompt is displayed

- **WHEN** an SDK run pauses for approval of a built-in side-effect tool
- **THEN** Deepy SHALL render an approval prompt that identifies the action kind,
  tool name, arguments summary, and relevant target command, path, or task id
- **AND** the user SHALL be able to approve or reject the action

#### Scenario: MCP approval prompt is displayed

- **WHEN** an SDK run pauses for approval of an MCP tool call
- **THEN** Deepy SHALL render an approval prompt that identifies the MCP server,
  MCP tool, and arguments summary
- **AND** the user SHALL be able to approve or reject the action

#### Scenario: Approval prompt is not transcript noise

- **WHEN** Deepy renders an approval prompt
- **THEN** it SHALL distinguish the prompt from model-authored
  `AskUserQuestion` content
- **AND** it SHALL NOT submit the approval prompt text as a normal user message

#### Scenario: Rejected approval resumes the turn

- **WHEN** the user rejects an approval prompt
- **THEN** Deepy SHALL resume the paused SDK run with a rejection result
- **AND** the terminal UI SHALL continue rendering subsequent assistant output
  from the resumed run
