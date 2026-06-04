## ADDED Requirements

### Requirement: Background Shell Execution
Deepy's shell tool SHALL support explicit background execution for long-running commands without changing the default foreground behavior.

#### Scenario: Model launches a foreground shell command
- **WHEN** the model invokes the shell tool without background execution enabled
- **THEN** Deepy SHALL execute the command through the existing foreground shell path
- **AND** it SHALL return command output only after the foreground command completes, fails, times out, or is interrupted

#### Scenario: Model launches a background shell command
- **WHEN** the model invokes the shell tool with background execution enabled
- **THEN** Deepy SHALL start the command as a managed background task
- **AND** it SHALL return promptly with a structured tool result containing the task id, command, cwd, status, and output inspection guidance
- **AND** it SHALL NOT wait for the command to finish before allowing the model turn to continue

#### Scenario: Background shell launch fails
- **WHEN** Deepy cannot launch a requested background shell command
- **THEN** the shell tool SHALL return a structured failure
- **AND** it SHALL NOT register a running background task for the failed launch

### Requirement: Background Task Management Tools
Deepy SHALL expose model-facing tools for listing, inspecting, and stopping managed background tasks.

#### Scenario: Model lists background tasks
- **WHEN** the model invokes the task listing tool
- **THEN** Deepy SHALL return running and recent terminal background tasks
- **AND** each listed task SHALL include id, status, description or command, cwd, start time, and terminal outcome when available

#### Scenario: Model reads background task output
- **WHEN** the model invokes the task output tool for an existing task id
- **THEN** Deepy SHALL return task status and a bounded output preview or tail
- **AND** it SHALL indicate whether the task is still running
- **AND** it SHALL indicate whether more output is available beyond the returned preview

#### Scenario: Model waits for task output
- **WHEN** the model invokes the task output tool with blocking enabled and a timeout
- **THEN** Deepy SHALL wait up to the requested timeout for the task to reach a terminal state
- **AND** it SHALL return the latest status and output when the task completes or the wait times out

#### Scenario: Model stops a background task
- **WHEN** the model invokes the task stop tool for a running task id
- **THEN** Deepy SHALL request termination for that task
- **AND** the tool result SHALL report the task id and current stop status

#### Scenario: Model manages an unknown task
- **WHEN** the model invokes a background task management tool with an unknown task id
- **THEN** Deepy SHALL return a structured "task not found" failure
- **AND** the interactive session SHALL continue without an uncaught exception
