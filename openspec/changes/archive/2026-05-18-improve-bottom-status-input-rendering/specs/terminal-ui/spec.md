## ADDED Requirements

### Requirement: Multiline Prompt Input Viewport

Deepy SHALL cap the visible height of multiline prompt input so composing long
prompts remains bounded inside the prompt editing area.

#### Scenario: Long multiline input exceeds visible prompt height

- **WHEN** a user enters multiline prompt text whose rendered height exceeds the
  prompt input viewport
- **THEN** Deepy SHALL keep the visible prompt input area within a configured
  maximum row count
- **AND** prompt-toolkit SHALL remain responsible for scrolling the editable
  prompt buffer
- **AND** Deepy SHALL leave room for the prompt footer when calculating the
  visible input cap

#### Scenario: Prompt cleanup is configured

- **WHEN** Deepy creates the interactive prompt session
- **THEN** Deepy SHALL configure prompt cleanup at session initialization
- **AND** Deepy SHALL NOT pass unsupported cleanup arguments to
  `PromptSession.prompt()`
