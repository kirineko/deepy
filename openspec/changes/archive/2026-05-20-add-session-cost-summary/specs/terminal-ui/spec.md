## MODIFIED Requirements

### Requirement: Redesigned Exit Summary Panel
Deepy SHALL render a compact exit summary panel in the stable interactive
terminal UI with local usage and DeepSeek session-cost information when
available.

#### Scenario: User exits stable interactive session
- **WHEN** the user exits the stable interactive terminal UI through `/exit`,
  `/quit`, or confirmed Ctrl+D
- **THEN** Deepy SHALL render an exit summary panel
- **AND** the panel SHALL use the same compact visual language and label
  hierarchy as the `/status` panel
- **AND** the panel SHALL include local cumulative model usage when known
- **AND** the panel SHALL include input-suggestion usage when known
- **AND** the panel SHALL include the active model and session identity when
  known
- **AND** the panel SHALL include DeepSeek session cost when a reliable
  start/end account balance delta is available
- **AND** the panel SHALL label the cost as based on the DeepSeek account
  balance delta during the session
- **AND** the panel SHALL remain readable when usage or cost is unknown

#### Scenario: Exit summary has no usage
- **WHEN** the user exits a stable interactive session with no known usage
- **THEN** Deepy SHALL still render a concise exit summary panel
- **AND** it SHALL omit empty usage tables instead of showing zero-filled noise

#### Scenario: Session cost cannot be computed
- **WHEN** Deepy cannot retrieve starting or ending balance, cannot parse a
  balance response, or cannot compute a reliable positive balance delta
- **THEN** the stable exit summary SHALL still render
- **AND** it SHALL keep local usage information visible
- **AND** it SHALL show concise cost unavailable text when cost tracking was
  attempted
- **AND** it SHALL NOT print a traceback
