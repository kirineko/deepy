## MODIFIED Requirements

### Requirement: File Mention Completion
Deepy SHALL provide `@` file and directory mention completion in the
interactive terminal prompt without depending on external system commands.

#### Scenario: User opens top-level file mention completion
- **WHEN** a user types `@` in a prompt position that is not embedded in another
  word
- **THEN** Deepy SHALL show file and directory candidates from the active
  project root
- **AND** directory candidates SHALL include a trailing `/`
- **AND** common generated, dependency, virtual environment, cache, and VCS
  entries SHALL be excluded

#### Scenario: User narrows file mention candidates
- **WHEN** a user continues typing non-whitespace characters after `@`
- **THEN** Deepy SHALL filter candidates by the typed fragment
- **AND** candidates whose basename starts with the typed fragment SHALL rank
  ahead of weaker relative-path fuzzy matches

#### Scenario: Short fragment searches nested project paths
- **WHEN** a user types a short non-empty `@` fragment without a directory
  separator
- **THEN** Deepy SHALL include matching nested files and directories from the
  active project root in the completion candidates
- **AND** the search SHALL remain bounded by the same candidate limit, cache,
  ignore rules, symlink exclusions, and project-root containment rules used by
  file mention discovery
- **AND** basename-prefix matches SHALL rank ahead of weaker relative-path fuzzy
  matches

#### Scenario: Bare at sign remains top-level
- **WHEN** a user types only `@` without a fragment
- **THEN** Deepy SHALL keep showing top-level project candidates
- **AND** it SHALL NOT flood the completion menu with every nested project path

#### Scenario: User descends into a directory
- **WHEN** a user types an `@` fragment containing `/`
- **THEN** Deepy SHALL search from the typed directory scope when that scope is
  within the active project root
- **AND** Deepy SHALL include matching files and directories inside that scope

#### Scenario: User accepts a mention candidate
- **WHEN** a file mention candidate is selected and the user presses Tab
- **THEN** Deepy SHALL replace the current `@` fragment with the selected
  relative path mention
- **AND** the accepted mention SHALL remain editable as plain prompt text

#### Scenario: User completes an existing file mention
- **WHEN** the current `@` fragment already resolves to an existing file under
  the active project root
- **THEN** Deepy SHALL stop offering additional file mention candidates for that
  fragment

#### Scenario: User types an embedded at sign
- **WHEN** a user types an at sign embedded in another token such as an email
  address
- **THEN** Deepy SHALL NOT open file mention completion

#### Scenario: File discovery runs on a machine without search binaries
- **WHEN** the user machine does not provide `rg`, `fd`, `find`, or `git`
- **THEN** Deepy SHALL still provide file mention completion using in-process
  file discovery
- **AND** Deepy SHALL NOT require shelling out to any system search command

#### Scenario: Scoped traversal attempts to escape the project root
- **WHEN** the typed `@` directory scope would resolve outside the active
  project root
- **THEN** Deepy SHALL reject that scope for completion
- **AND** Deepy SHALL NOT include candidates outside the active project root

#### Scenario: Slash command completion remains available
- **WHEN** a user types a slash command token in the interactive prompt
- **THEN** Deepy SHALL continue to offer slash command completions
- **AND** file mention completion SHALL NOT interfere with slash command
  completion
