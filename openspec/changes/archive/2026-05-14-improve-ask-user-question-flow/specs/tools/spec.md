## ADDED Requirements

### Requirement: AskUserQuestion Guidance

Deepy SHALL guide the model to use AskUserQuestion when clarification would materially improve the result, while avoiding unnecessary questions for low-impact details.

#### Scenario: User intent is ambiguous

- **WHEN** the user's request has multiple plausible interpretations that would lead to materially different work
- **THEN** Deepy SHALL allow the model to use AskUserQuestion to clarify the intended direction

#### Scenario: Scope or preference affects implementation

- **WHEN** missing scope, preference, or trade-off information would significantly affect the implementation plan or user-facing outcome
- **THEN** Deepy SHALL allow the model to use AskUserQuestion before committing to a path

#### Scenario: Required approval is missing

- **WHEN** the next action needs user approval or a required decision
- **THEN** Deepy SHALL allow the model to use AskUserQuestion to pause and request that decision

#### Scenario: Detail is low impact

- **WHEN** a missing detail is low impact and Deepy can make a reasonable assumption
- **THEN** Deepy SHALL guide the model to proceed with the assumption instead of asking an unnecessary question

### Requirement: AskUserQuestion Display Safety

Deepy SHALL preserve the structured AskUserQuestion contract for model/runtime communication while suppressing raw question payloads from normal user-facing tool summaries.

#### Scenario: AskUserQuestion result is produced

- **WHEN** the AskUserQuestion tool returns a result
- **THEN** the result SHALL keep `awaitUserResponse=true`
- **AND** it SHALL keep `metadata.kind="ask_user_question"`
- **AND** it SHALL keep normalized question metadata for pending-question parsing

#### Scenario: AskUserQuestion call summary is formatted

- **WHEN** Deepy formats an AskUserQuestion call for terminal progress or history display
- **THEN** it SHALL NOT render the raw `questions` argument payload
- **AND** it SHALL render a concise label suitable for user-facing output
