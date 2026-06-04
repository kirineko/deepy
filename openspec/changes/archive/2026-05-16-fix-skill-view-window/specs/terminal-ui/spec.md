## MODIFIED Requirements

### Requirement: Skill Management Slash Commands

Deepy SHALL provide `/skills` subcommands and a dedicated full-screen skill
management menu for local skill management and market browsing.

#### Scenario: User opens skill management

- **WHEN** a user runs `/skills` without arguments
- **THEN** Deepy SHALL show local skill management options and the available subcommands

#### Scenario: User lists local skills

- **WHEN** a user runs `/skills list`
- **THEN** Deepy SHALL list discovered project, user, and built-in skills grouped by scope

#### Scenario: User searches market skills

- **WHEN** a user runs `/skills search pdf`
- **THEN** Deepy SHALL show matching market skills or a concise market access error

#### Scenario: User views an installed skill from the menu

- **WHEN** a user selects an installed project, user, or market-managed skill in the `/skills` menu
- **AND** the user invokes the view action
- **THEN** Deepy SHALL show the skill details in a dedicated full-screen viewer
- **AND** it SHALL render Markdown structure from the skill body for readable viewing
- **AND** it SHALL NOT print the skill body into the main Deepy output area

#### Scenario: User views an uninstalled market skill from the menu

- **WHEN** a user selects an uninstalled market skill in the `/skills` menu
- **AND** the user invokes the view action
- **THEN** Deepy SHALL show available market metadata in a dedicated full-screen viewer
- **AND** it SHALL render Markdown structure from market description fields when present
- **AND** it SHALL NOT report that the skill is missing solely because no local install path exists

#### Scenario: User chooses install scope for a market skill

- **WHEN** a user selects an uninstalled market skill in the `/skills` menu
- **AND** the user invokes the install action
- **THEN** Deepy SHALL show a dedicated scope selection window for user or project installation
- **AND** the selected scope SHALL control the install destination
