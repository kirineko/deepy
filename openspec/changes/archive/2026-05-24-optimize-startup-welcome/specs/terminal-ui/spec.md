## ADDED Requirements

### Requirement: Fast Startup Readiness

Deepy SHALL render the stable terminal UI welcome screen and prompt without
waiting for startup network checks or MCP connection to complete.

#### Scenario: Welcome renders before version check completes

- **WHEN** Deepy starts the stable terminal UI
- **AND** the startup version check has not completed
- **THEN** Deepy SHALL render the welcome screen without waiting for the version
  check result
- **AND** Deepy SHALL show concise pending update state in the startup UI or
  prompt footer

#### Scenario: Welcome renders before MCP connection completes

- **WHEN** Deepy starts the stable terminal UI
- **AND** configured MCP servers have not completed connection
- **THEN** Deepy SHALL render the welcome screen without waiting for MCP
  connection
- **AND** Deepy SHALL show concise pending MCP state in the prompt footer

#### Scenario: Prompt is available during startup background work

- **WHEN** the welcome screen has rendered
- **AND** startup version or MCP work is still pending
- **THEN** Deepy SHALL allow the user to enter prompt input
- **AND** prompt input SHALL remain visually coherent while startup state changes

#### Scenario: MCP completes after prompt is visible

- **WHEN** MCP connection completes after the prompt is visible
- **THEN** Deepy SHALL refresh the prompt footer state from pending MCP state to
  connected MCP count when active servers are available
- **AND** Deepy SHALL NOT print raw background output that corrupts the prompt
  input row

#### Scenario: Update is found before prompt starts

- **WHEN** the startup version check discovers a newer version before prompt
  input starts
- **THEN** Deepy SHALL include the update state in the welcome information before
  the first prompt is shown

#### Scenario: Update is found after prompt starts

- **WHEN** the startup version check discovers a newer version after prompt input
  has started
- **THEN** Deepy SHALL show one concise prompt-toolkit-safe terminal notification
- **AND** Deepy SHALL NOT redraw the full welcome panel while prompt input owns
  the terminal

#### Scenario: User submits before MCP is ready

- **WHEN** the user submits the first model prompt before MCP connection has
  completed
- **THEN** Deepy SHALL wait for MCP readiness before starting the model turn
- **AND** Deepy SHALL show runtime progress while waiting
- **AND** the model turn SHALL use the configured MCP runtime after it is ready

#### Scenario: MCP startup fails

- **WHEN** MCP connection fails during background startup
- **THEN** Deepy SHALL continue the stable terminal session
- **AND** the first model turn SHALL proceed with the failed MCP state recorded
  in the MCP runtime
- **AND** MCP status inspection SHALL remain available through existing MCP
  status surfaces

#### Scenario: Terminal ownership is preserved

- **WHEN** startup update or MCP state changes while prompt-toolkit is reading
  input
- **THEN** Deepy SHALL update the UI through prompt-toolkit-safe mechanisms
- **AND** Deepy SHALL NOT directly write Rich output from the background startup
  task into the active prompt area
