## ADDED Requirements

### Requirement: Textual Slash Command Discovery Ranking
The experimental Textual TUI SHALL use the shared Deepy slash command ranking
for prompt-adjacent slash suggestions and command discovery surfaces.

#### Scenario: Bare slash suggestions reveal all command kinds
- **WHEN** a user types `/` at the beginning of the Textual TUI prompt
- **THEN** the TUI SHALL provide selectable suggestions for built-in commands,
  subagent commands, and skill invocation commands
- **AND** subagent and skill suggestions SHALL NOT be hidden solely because the
  first visible rows are occupied by built-in commands
- **AND** the suggestion surface SHALL allow keyboard access to additional
  ranked candidates when more candidates exist than visible rows

#### Scenario: Bare slash suggestions prioritize useful actions
- **WHEN** the Textual TUI displays slash suggestions for a bare `/`
- **THEN** common workflow commands SHALL rank before lower-frequency
  management or exit commands
- **AND** subagent commands SHALL rank before otherwise equivalent unloaded skill
  commands
- **AND** loaded skills SHALL rank ahead of otherwise equivalent unloaded skills

#### Scenario: Typed slash suggestions share stable UI ranking
- **WHEN** a user types a partial slash command token in the Textual TUI prompt
- **THEN** the TUI SHALL rank exact matches before prefix matches
- **AND** it SHALL rank prefix matches before weaker description or substring
  matches
- **AND** it SHALL use the same shared slash command priority tie-breakers as
  the stable UI

#### Scenario: Selecting a suggestion only inserts the command
- **WHEN** a user selects a Textual TUI slash suggestion
- **THEN** the TUI SHALL insert the selected command token into the prompt
- **AND** it SHALL NOT submit the prompt or start a model turn until the user
  submits the prompt explicitly
