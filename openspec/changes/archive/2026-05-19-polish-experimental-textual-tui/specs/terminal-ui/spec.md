## ADDED Requirements

### Requirement: Experimental TUI Stable Command Alignment
The experimental Textual TUI SHALL align with stable terminal UI commands where
the behavior is meaningful in a full-screen Textual app.

#### Scenario: User opens help in TUI
- **WHEN** a user invokes `/help` or the equivalent command discovery action in
  the experimental TUI
- **THEN** the TUI SHALL show available commands, keybindings, model settings,
  session state, loaded skills, and config path in a readable Textual surface

#### Scenario: User opens status in TUI
- **WHEN** a user invokes `/status` in the experimental TUI
- **THEN** the TUI SHALL show project root, active model, reasoning mode, active
  session, context status, MCP status, loaded skills, and UI theme
- **AND** the status view SHALL be dismissible back to the active conversation

#### Scenario: User changes theme in TUI
- **WHEN** a user invokes `/theme` in the experimental TUI
- **THEN** the TUI SHALL allow selecting `auto`, `dark`, or `light`
- **AND** it SHALL persist the selected theme using Deepy's existing settings
  path
- **AND** it SHALL update or clearly report when restart is needed for full
  theme application

#### Scenario: User changes model in TUI
- **WHEN** a user invokes `/model` in the experimental TUI
- **THEN** the TUI SHALL allow selecting a supported model and reasoning mode
- **AND** it SHALL persist completed selections through Deepy's existing model
  settings flow
- **AND** cancelling before completion SHALL leave settings unchanged

### Requirement: Experimental TUI Init And Reset Parity
The experimental Textual TUI SHALL provide TUI-native behavior for `/init` and
`/reset` instead of leaving those stable commands unsupported.

#### Scenario: User runs init in TUI
- **WHEN** a user invokes `/init` in the experimental TUI
- **THEN** the TUI SHALL build the existing AGENTS.md initialization prompt for
  the active project root
- **AND** it SHALL submit that generated prompt through the normal TUI model
  turn path
- **AND** it SHALL preserve the active session continuation behavior used by
  normal prompts

#### Scenario: User runs init with extra instruction in TUI
- **WHEN** a user invokes `/init prefer concise guidance`
- **THEN** the TUI SHALL pass `prefer concise guidance` as the init prompt's
  extra instruction
- **AND** it SHALL NOT send the literal slash command as a normal model prompt

#### Scenario: User resets config in TUI
- **WHEN** a user invokes `/reset` in the experimental TUI
- **THEN** the TUI SHALL open a Textual-native configuration reset/setup surface
- **AND** submitting that surface SHALL delete or replace the configured TOML
  config using Deepy's existing config persistence helpers
- **AND** the TUI SHALL reload settings after the config is written
- **AND** subsequent TUI output SHALL use the newly saved UI theme when possible

#### Scenario: User cancels reset in TUI
- **WHEN** the user cancels the TUI reset/setup surface
- **THEN** the TUI SHALL leave the existing config and in-memory settings
  unchanged
- **AND** it SHALL return focus to the active conversation

#### Scenario: Reset cannot write config
- **WHEN** the TUI cannot determine a writable TOML config path
- **THEN** the TUI SHALL show a concise error
- **AND** it SHALL NOT delete existing settings or start a model turn

### Requirement: Experimental TUI Local Command Safety
The experimental Textual TUI SHALL avoid accidental model turns for commands
that are meant to be handled locally by the terminal UI.

#### Scenario: TUI receives a known local command
- **WHEN** the prompt text is a known Deepy slash command
- **THEN** the TUI SHALL route it through local TUI command handling
- **AND** it SHALL NOT send the command text to the model unless the command
  explicitly starts a model turn

#### Scenario: TUI receives an invalid command form
- **WHEN** the prompt text starts with `/` but does not match a supported command
  or skill invocation
- **THEN** the TUI SHALL show a concise command error
- **AND** it SHALL keep the user's prompt context recoverable

#### Scenario: TUI receives a local command
- **WHEN** the prompt text starts with `!` after trimming
- **THEN** the TUI SHALL route the prompt through Deepy's local command mode
- **AND** it SHALL NOT send the prompt text to the model

#### Scenario: TUI receives an empty local command
- **WHEN** the user submits `!` with no command text after it
- **THEN** the TUI SHALL show a concise usage message
- **AND** it SHALL NOT start a model turn
- **AND** it SHALL NOT append a local command transcript to the session

### Requirement: Experimental TUI Local Command Execution
The experimental Textual TUI SHALL execute user-entered `!command` prompts by
reusing Deepy's existing local command execution helpers and rendering the
result through TUI shell output blocks.

#### Scenario: POSIX local command runs in TUI
- **WHEN** the TUI handles a non-empty local command on macOS or Linux
- **THEN** it SHALL use Deepy's existing POSIX PTY-backed local command runner
- **AND** it SHALL render command output, exit status, truncation, timeout, and
  interruption metadata in the transcript

#### Scenario: Windows PowerShell local command runs in TUI
- **WHEN** the TUI handles a non-empty local command on Windows with PowerShell
  or PowerShell Core detected
- **THEN** it SHALL use Deepy's existing non-interactive pipe-based Windows
  local command runner
- **AND** it SHALL NOT allocate a Windows pseudo-terminal or depend on
  `pywinpty`
- **AND** it SHALL invoke the shell with the detected PowerShell command
  dialect
- **AND** it SHALL decode Windows-compatible output, normalize line endings,
  and remove terminal control sequences before rendering
- **AND** it SHALL report shell kind, command dialect, TTY mode, cwd, exit code,
  duration, timeout, and interruption metadata when available

#### Scenario: Windows cmd local command boundary in TUI
- **WHEN** the TUI handles a non-empty local command on Windows with `cmd.exe`
  detected
- **THEN** the TUI MAY reuse Deepy's existing non-interactive `cmd` dialect path
- **AND** if the TUI implementation does not support that shell path, it SHALL
  show a clear unsupported message
- **AND** it SHALL NOT allocate a pseudo-terminal, call the model, or treat the
  command as normal prompt text

#### Scenario: TUI local command tries interactive terminal behavior
- **WHEN** a Windows local command requires interactive stdin, an editor, a
  pager, or full-screen terminal UI
- **THEN** the TUI SHALL preserve Deepy's non-interactive Windows boundary
- **AND** it SHALL render captured output or failure state without corrupting
  subsequent prompt input

### Requirement: Experimental TUI Skill Market Management
The experimental Textual TUI SHALL connect Deepy's skill market and full skill
management flows instead of limiting `/skills` to local list/use/show output.

#### Scenario: User opens skill management in TUI
- **WHEN** a user invokes `/skills` without arguments in the experimental TUI
- **THEN** the TUI SHALL open a Textual skill management surface
- **AND** the surface SHALL distinguish installed/local skills from market
  skills
- **AND** it SHALL provide keyboard navigation and a clear return path to the
  conversation

#### Scenario: User searches market skills in TUI
- **WHEN** a user invokes `/skills search pdf`
- **THEN** the TUI SHALL show matching market skills or a concise market access
  error
- **AND** it SHALL NOT start a model turn

#### Scenario: User installs a market skill in TUI
- **WHEN** a user invokes `/skills install NAME` or selects install from the TUI
  skill management surface
- **THEN** the TUI SHALL use Deepy's existing skill market install helper
- **AND** it SHALL collect user/project install scope when required
- **AND** it SHALL show success or failure without dumping package contents into
  the main transcript

#### Scenario: User updates or removes market skills in TUI
- **WHEN** a user invokes `/skills uninstall NAME`, `/skills installed`,
  `/skills update NAME`, or `/skills update --all`
- **THEN** the TUI SHALL use Deepy's existing skill market helpers
- **AND** it SHALL keep loaded skill state consistent with installed and removed
  skills

#### Scenario: User views a skill in TUI
- **WHEN** a user views a local, installed, or market skill from the TUI
- **THEN** the TUI SHALL show details in a dedicated Textual surface
- **AND** it SHALL avoid dumping full `SKILL.md` bodies into the main transcript

### Requirement: Experimental TUI Exit Summary
The experimental Textual TUI SHALL provide a clean exit path consistent with
Deepy's stable terminal experience.

#### Scenario: User exits active TUI session
- **WHEN** the user exits the experimental TUI
- **THEN** Deepy SHALL close the Textual app cleanly
- **AND** it SHALL return terminal control without leaving a stale full-screen
  status area
- **AND** it SHALL show any configured concise exit summary that is safe to show
  after leaving the full-screen app
