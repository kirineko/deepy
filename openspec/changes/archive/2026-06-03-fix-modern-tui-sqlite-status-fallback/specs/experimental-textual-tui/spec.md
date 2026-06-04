## ADDED Requirements

### Requirement: Textual Status Session Metadata Resilience
The experimental Textual TUI SHALL treat session metadata used by the status bar
and side panel as best-effort display data. Failures while reading session
metadata MUST NOT crash the Textual app, interrupt stream rendering, or prevent
the active turn from completing.

#### Scenario: Status metadata read fails during idle rendering
- **WHEN** the experimental TUI renders its status bar or side panel
- **AND** reading the active session metadata fails
- **THEN** the TUI SHALL continue rendering the status bar and side panel
- **AND** it SHALL show unknown or unavailable context/cache metadata
- **AND** it SHALL NOT raise the session metadata read failure through the
  Textual message loop

#### Scenario: Status metadata read fails during streaming
- **WHEN** a model turn is streaming text, reasoning, raw response, tool call, or
  tool output events
- **AND** reading the active session metadata fails
- **THEN** the TUI SHALL continue processing stream events
- **AND** it SHALL preserve live progress status such as running state, token
  progress, or tool status
- **AND** it SHALL show unknown or unavailable context/cache metadata until a
  later successful metadata refresh

### Requirement: Textual Status Session Metadata Refresh Frequency
The experimental Textual TUI SHALL avoid high-frequency repeated session-list
reads when updating live status. Session metadata for status bar and side-panel
context/cache display MUST be cached or otherwise reused across stream status
updates, and refreshed only at meaningful lifecycle points.

#### Scenario: Streaming status updates reuse cached metadata
- **WHEN** a model turn emits multiple stream events that update live status
- **THEN** the TUI SHALL NOT call the session-list reader once per stream event
- **AND** it SHALL render status bar and side-panel context/cache information
  from cached metadata or from an unavailable fallback

#### Scenario: Metadata refreshes after session lifecycle changes
- **WHEN** the active session changes, a model turn completes, a session is
  resumed, a new session starts, or an explicit session lifecycle command
  refreshes session state
- **THEN** the TUI SHALL refresh the cached session metadata used by status bar
  and side-panel context/cache display
- **AND** subsequent status renders SHALL use the refreshed metadata until the
  next lifecycle refresh or fallback state

#### Scenario: Explicit session commands remain fresh
- **WHEN** a user invokes a Textual TUI command whose purpose is to list, resume,
  inspect, or summarize sessions
- **THEN** the command MAY read the session list directly
- **AND** the direct read SHALL NOT be part of per-token or per-stream-event
  status rendering
