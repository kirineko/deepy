## ADDED Requirements

### Requirement: Clarification Question Flow

Deepy SHALL render AskUserQuestion prompts as a user-facing terminal interaction and SHALL continue the active interactive turn across repeated clarification rounds.

#### Scenario: First clarification round is requested

- **WHEN** a model turn returns `status="waiting_for_user"` with pending AskUserQuestion questions
- **THEN** Deepy SHALL display the questions and options to the user
- **AND** it SHALL collect the user's answers
- **AND** it SHALL continue the same session using the collected answers

#### Scenario: Follow-up clarification round is requested

- **WHEN** the model asks another AskUserQuestion after receiving answers from a previous AskUserQuestion round
- **THEN** Deepy SHALL display the follow-up questions and options
- **AND** it SHALL collect the user's answers
- **AND** it SHALL continue the same session using the collected answers

#### Scenario: Clarification rounds complete

- **WHEN** a continued model turn completes without `status="waiting_for_user"`
- **THEN** Deepy SHALL render the assistant output and usage footer for the completed turn
- **AND** it SHALL not drop any pending assistant output from the final continuation

#### Scenario: Clarification round limit is reached

- **WHEN** repeated AskUserQuestion rounds exceed Deepy's defensive per-turn limit
- **THEN** Deepy SHALL stop collecting further clarification rounds
- **AND** it SHALL show a concise message indicating that clarification stopped because the round limit was reached

### Requirement: Clarification Prompt Display

Deepy SHALL keep AskUserQuestion interaction readable by hiding internal tool protocol details from normal terminal output.

#### Scenario: AskUserQuestion tool call is streamed

- **WHEN** Deepy renders a streamed AskUserQuestion tool call
- **THEN** the terminal output SHALL NOT include the raw `questions` argument JSON
- **AND** it SHALL show only a concise AskUserQuestion progress label

#### Scenario: AskUserQuestion history is rendered

- **WHEN** Deepy renders session history containing an AskUserQuestion tool call
- **THEN** the history output SHALL NOT include the raw `questions` argument JSON
- **AND** it SHALL preserve a concise indication that AskUserQuestion was used

#### Scenario: User answers clarification questions

- **WHEN** Deepy sends formatted AskUserQuestion answers back to the model
- **THEN** the terminal SHALL NOT print the internal synthetic answer protocol as if it were raw user input
- **AND** it SHALL either omit that protocol message or show a human-readable answer summary

#### Scenario: Multi-select question is shown

- **WHEN** Deepy displays an AskUserQuestion item with `multiSelect=true`
- **THEN** the prompt SHALL indicate how the user can select multiple options

#### Scenario: Fallback option is shown

- **WHEN** Deepy adds a fallback custom-answer option to a question
- **THEN** the fallback option label SHALL be understandable in the terminal prompt
