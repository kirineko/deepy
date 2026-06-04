## ADDED Requirements

### Requirement: Skill Management Slash Commands
Deepy SHALL provide `/skills` subcommands for local skill management and market browsing.

#### Scenario: User opens skill management
- **WHEN** a user runs `/skills` without arguments
- **THEN** Deepy SHALL show local skill management options and the available subcommands

#### Scenario: User lists local skills
- **WHEN** a user runs `/skills list`
- **THEN** Deepy SHALL list discovered project, user, and built-in skills grouped by scope

#### Scenario: User searches market skills
- **WHEN** a user runs `/skills search pdf`
- **THEN** Deepy SHALL show matching market skills or a concise market access error

### Requirement: Skill Invocation Slash Completion
Deepy SHALL complete active skill invocation commands when the user types `/skill:`.

#### Scenario: Completion after skill prefix
- **WHEN** the prompt input contains `/skill:`
- **THEN** slash completion SHALL include available skill names as `/skill:<name>` entries

#### Scenario: Skill completion includes descriptions
- **WHEN** Deepy renders completion options for `/skill:`
- **THEN** each skill completion SHALL include the skill description when available

### Requirement: Active Skill Invocation Command
Deepy SHALL treat `/skill:<name> [request]` as an active skill invocation rather than a management command.

#### Scenario: Active skill invocation submits a turn
- **WHEN** a user runs `/skill:review summarize this change`
- **THEN** Deepy SHALL submit a model turn with the `review` skill loaded and the remaining text as the user request

#### Scenario: Unknown active skill
- **WHEN** a user runs `/skill:missing`
- **THEN** Deepy SHALL report that the skill was not found and SHALL NOT submit a model turn
