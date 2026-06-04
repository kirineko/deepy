# background-tasks Specification

## Purpose
TBD - created by archiving change add-background-task-management. Update Purpose after archive.
## Requirements
### Requirement: Background Task Lifecycle
Deepy SHALL manage background tasks it starts through a Deepy-owned task lifecycle.

#### Scenario: Background task is launched
- **WHEN** Deepy starts a command as a background task
- **THEN** Deepy SHALL assign a stable task id
- **AND** it SHALL record command, cwd, start time, status, pid when available, and output log location
- **AND** the task SHALL appear in background task listings while it is running

#### Scenario: Background task completes successfully
- **WHEN** a managed background task exits with code 0
- **THEN** Deepy SHALL mark the task as `completed`
- **AND** it SHALL record the exit code and end time
- **AND** it SHALL retain the task long enough for `/ps` and task output inspection

#### Scenario: Background task fails
- **WHEN** a managed background task exits with a non-zero code or launch/runtime failure
- **THEN** Deepy SHALL mark the task as `failed`
- **AND** it SHALL record the failure reason, exit code when available, and end time

#### Scenario: Background task is stopped
- **WHEN** a managed running background task is stopped by Deepy
- **THEN** Deepy SHALL request process termination
- **AND** it SHALL mark the task as `stopped` once termination is observed or forced during shutdown
- **AND** repeated stop requests for the same terminal task SHALL be safe and idempotent

### Requirement: Background Output Isolation
Deepy SHALL isolate background task output from active assistant thinking and response output.

#### Scenario: Background task writes output while AI is responding
- **WHEN** a background task writes stdout or stderr while a foreground model turn is streaming
- **THEN** Deepy SHALL capture the task output in the task output log
- **AND** it SHALL NOT print that output into the active thinking block, assistant response, or foreground tool transcript

#### Scenario: Task output is requested
- **WHEN** a user or model explicitly requests output for a managed background task
- **THEN** Deepy SHALL return a bounded preview or tail of the task output
- **AND** it SHALL indicate whether more output is available
- **AND** it SHALL include task status metadata with the output result

### Requirement: Background Task Shutdown
Deepy SHALL stop managed background tasks during user-requested exit.

#### Scenario: User exits with running background tasks
- **WHEN** the user exits Deepy while managed background tasks are running
- **THEN** Deepy SHALL request termination for all running background tasks before completing process shutdown
- **AND** it SHALL wait a bounded grace period before force-killing tasks that do not exit
- **AND** it SHALL not close the interactive runtime before issuing background task cleanup

#### Scenario: No background tasks are running on exit
- **WHEN** the user exits Deepy and no managed background tasks are running
- **THEN** Deepy SHALL complete exit cleanup without printing spurious background task errors

### Requirement: Background Task Limits
Deepy SHALL prevent unbounded background task growth.

#### Scenario: Background task capacity is reached
- **WHEN** a new background task launch would exceed Deepy's configured or default running task limit
- **THEN** Deepy SHALL reject the launch with a structured error
- **AND** it SHALL keep existing background tasks running

#### Scenario: Terminal task history grows
- **WHEN** background tasks have reached terminal states
- **THEN** Deepy SHALL retain a bounded recent terminal task history for inspection
- **AND** it SHALL never evict running tasks because of terminal history retention
