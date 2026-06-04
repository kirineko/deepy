## MODIFIED Requirements

### Requirement: On-Demand DeepSeek Balance Lookup
Deepy SHALL support read-only DeepSeek account balance lookups for explicit
user-visible status and session-cost surfaces.

#### Scenario: Status command requests balance
- **WHEN** the user runs `/status`
- **AND** a DeepSeek API key is configured
- **AND** the configured API base URL resolves to an official DeepSeek API host
- **THEN** Deepy SHALL request `GET /user/balance`
- **AND** it SHALL authenticate with `Authorization: Bearer <api_key>`
- **AND** it SHALL use a short timeout suitable for an interactive status command

#### Scenario: Session cost snapshot requests balance
- **WHEN** Deepy records a start or end balance snapshot for an interactive
  session cost summary
- **AND** a DeepSeek API key is configured
- **AND** the configured API base URL resolves to an official DeepSeek API host
- **THEN** Deepy SHALL request `GET /user/balance`
- **AND** it SHALL authenticate with `Authorization: Bearer <api_key>`
- **AND** it SHALL use a short timeout suitable for interactive shutdown paths

#### Scenario: Balance response is valid
- **WHEN** Deepy receives a valid balance response
- **THEN** it SHALL parse `is_available`
- **AND** it SHALL parse each `balance_infos` entry's `currency`,
  `total_balance`, `granted_balance`, and `topped_up_balance`
- **AND** it SHALL expose those parsed values to status and session-cost
  renderers

#### Scenario: Balance lookup is unavailable
- **WHEN** the API key is missing, the configured base URL is not an official
  DeepSeek API host, the request times out, the provider returns an error
  status, or the response cannot be parsed
- **THEN** Deepy SHALL return a balance unavailable result
- **AND** it SHALL include a concise reason suitable for display
- **AND** it SHALL NOT raise an uncaught exception into the interactive UI

#### Scenario: Non-balance paths run
- **WHEN** Deepy starts up, renders a welcome panel, renders a footer or status
  bar, runs `deepy doctor`, runs a model turn, records usage, prepares input
  suggestions, renders usage after a turn, or renders normal model-turn output
- **THEN** Deepy SHALL NOT request `GET /user/balance`
- **AND** it SHALL NOT perform any other DeepSeek balance network call

#### Scenario: Secrets are displayed
- **WHEN** Deepy renders balance, cost, or status information
- **THEN** it SHALL NOT print the configured API key
- **AND** it SHALL NOT include the API key in error text
