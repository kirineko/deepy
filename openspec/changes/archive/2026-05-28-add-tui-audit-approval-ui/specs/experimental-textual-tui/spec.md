## ADDED Requirements

### Requirement: Textual Audit Mode Visibility

The experimental Textual TUI SHALL make the active system audit mode visible
during interactive use.

#### Scenario: Status bar shows audit mode

- **WHEN** the Textual TUI is waiting for user input or running a model turn
- **THEN** the status bar SHALL include the active audit mode
- **AND** it SHALL keep existing provider, model, working-directory, MCP,
  background-task, context, and cache status segments readable

#### Scenario: Status screen shows audit mode

- **WHEN** the user opens the Textual TUI status surface such as `/status`
- **THEN** the status screen SHALL include the active audit mode
- **AND** it SHALL distinguish runtime mode from persisted configuration when
  they differ

### Requirement: Textual Audit Mode Cycling

The experimental Textual TUI SHALL support cycling audit modes with the same
runtime mode order as the stable terminal UI.

#### Scenario: User cycles audit mode

- **WHEN** the user presses `Shift+Tab` while the Textual TUI prompt is active
- **THEN** Deepy SHALL switch to the next audit mode in the order `normal`,
  `auto`, `yolo`, `normal`
- **AND** Deepy SHALL update visible Textual status surfaces without submitting
  the current prompt text

#### Scenario: Tab completion remains available

- **WHEN** the user presses `Tab` without `Shift` while the Textual TUI prompt is active
- **THEN** Deepy SHALL preserve existing slash-command completion, file-mention,
  and input-suggestion behavior
- **AND** it SHALL NOT cycle the audit mode

### Requirement: Textual Approval Prompt Display

The experimental Textual TUI SHALL present SDK approval interruptions as
explicit Textual approval prompts rather than normal assistant questions.

#### Scenario: Built-in tool approval prompt is displayed

- **WHEN** an SDK run pauses for approval of a built-in side-effect tool in the Textual TUI
- **THEN** the TUI SHALL render a Textual approval prompt that identifies the
  action kind, tool name, arguments summary, and relevant target command, path,
  or task id
- **AND** the user SHALL be able to approve or reject the action

#### Scenario: MCP approval prompt is displayed

- **WHEN** an SDK run pauses for approval of an MCP tool call in the Textual TUI
- **THEN** the TUI SHALL render a Textual approval prompt that identifies the MCP
  server, MCP tool, and arguments summary
- **AND** the user SHALL be able to approve or reject the action

#### Scenario: Approval prompt is not transcript noise

- **WHEN** the Textual TUI renders an approval prompt
- **THEN** it SHALL distinguish the prompt from model-authored `AskUserQuestion`
  content
- **AND** it SHALL NOT append the approval prompt text as a normal transcript
  message
- **AND** it SHALL NOT submit the approval prompt text as a normal user message

#### Scenario: Rejected approval resumes the turn

- **WHEN** the user rejects an approval prompt in the Textual TUI
- **THEN** Deepy SHALL resume the paused SDK run with a rejection result
- **AND** the TUI SHALL continue rendering subsequent assistant output from the
  resumed run

### Requirement: Textual Task-Focused Audit Approval Panels

The experimental Textual TUI SHALL render audit approval prompts with the same
task-focused summary rules as the stable terminal UI.

#### Scenario: Shell command approval uses task summary

- **WHEN** an SDK approval interruption requests a shell command execution in the Textual TUI
- **THEN** Deepy SHALL show a title that identifies the request as a shell
  command approval
- **AND** it SHALL show the command as the primary target
- **AND** it SHALL show meaningful secondary context such as description or
  working directory when available
- **AND** it SHALL NOT show raw internal field labels such as `action`, `agent`,
  or `arguments.*` unless no typed summary can be derived

#### Scenario: MCP approval uses server and tool summary

- **WHEN** an SDK approval interruption requests an MCP tool call in the Textual TUI
- **THEN** Deepy SHALL show a title that identifies the request as an MCP tool
  approval
- **AND** it SHALL show the MCP server and tool as the primary target
- **AND** it SHALL show only the most relevant bounded argument fields, such as
  `url`, `urls`, `query`, or `format`, when available
- **AND** it SHALL NOT render the full raw argument JSON by default

#### Scenario: Unknown approval falls back to bounded summary

- **WHEN** an SDK approval interruption cannot be classified as shell, file
  mutation, or MCP in the Textual TUI
- **THEN** Deepy SHALL show the tool name and a bounded structured argument
  summary
- **AND** the fallback summary SHALL remain visually distinct from normal
  assistant messages

### Requirement: Textual File Mutation Approval Diff Review

The experimental Textual TUI SHALL render `Write` and `Update` audit approvals
with diff previews and relative target paths when possible.

#### Scenario: Write approval shows new-file diff

- **WHEN** an SDK approval interruption requests writing content to a file under
  the active project root in the Textual TUI
- **THEN** Deepy SHALL display the file path relative to the project root
- **AND** it SHALL show a diff preview representing the proposed new file content
- **AND** it SHALL keep the final decision area limited to `Approve` and `Reject`

#### Scenario: Update approval shows changed lines

- **WHEN** an SDK approval interruption requests updating content in a file in
  the Textual TUI
- **AND** the approval arguments contain enough before-and-after information to
  derive a diff
- **THEN** Deepy SHALL display the file path relative to the project root when
  the file is under that root
- **AND** it SHALL show a diff preview that includes removed and added lines

#### Scenario: File path outside project remains explicit

- **WHEN** an SDK approval interruption targets a file outside the active project
  root in the Textual TUI
- **THEN** Deepy SHALL NOT display the path as project-relative
- **AND** it SHALL display a home-relative path when possible or the absolute
  path otherwise

#### Scenario: Long diff preview uses scrolling without extra decision controls

- **WHEN** a `Write` or `Update` diff preview exceeds the compact preview budget
  in the Textual TUI
- **THEN** Deepy SHALL render the diff preview in a bounded scrollable Textual
  region
- **AND** it SHALL keep the decision controls limited to `Approve` and `Reject`

#### Scenario: Missing update diff context uses safe fallback

- **WHEN** an `Update` approval in the Textual TUI does not contain enough
  before-and-after information to derive a reliable diff
- **THEN** Deepy SHALL show a compact typed summary instead of fabricating a diff
- **AND** it SHALL still display the target path using the relative-path rules

### Requirement: Textual Approval Prompt Keyboard Interaction

The experimental Textual TUI approval prompt SHALL resolve approvals only through
navigation selection, `Enter`, and `Esc`.

#### Scenario: Arrow keys move selection

- **WHEN** an approval prompt is active in the Textual TUI
- **AND** the user presses `Up` or `Down`
- **THEN** Deepy SHALL move the selection among visible approval decision controls
- **AND** it SHALL NOT approve or reject the tool call only because selection
  moved

#### Scenario: Enter activates selected control

- **WHEN** an approval prompt is active in the Textual TUI
- **AND** the user presses `Enter`
- **AND** the selected control is `Approve` or `Reject`
- **THEN** Deepy SHALL resolve the SDK approval with the selected decision

#### Scenario: Escape rejects approval

- **WHEN** an approval prompt is active in the Textual TUI
- **AND** the user presses `Esc`
- **THEN** Deepy SHALL resolve the SDK approval as rejected

#### Scenario: Letter shortcuts do not resolve approval

- **WHEN** an approval prompt is active in the Textual TUI
- **AND** the user presses `Y`, `A`, `N`, `R`, or their lowercase equivalents
- **THEN** Deepy SHALL NOT resolve the SDK approval because of that keypress
- **AND** visible approval hints SHALL NOT advertise those letter shortcuts
