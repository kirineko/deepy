## ADDED Requirements

### Requirement: Thinking Language Guidance

Deepy SHALL guide DeepSeek to match visible thinking language to the user's
latest natural language when thinking is enabled.

#### Scenario: User asks in Chinese

- **WHEN** the user's latest natural-language request is primarily Chinese
- **AND** DeepSeek thinking is enabled
- **THEN** Deepy's model prompt SHALL instruct DeepSeek to use Chinese for
  visible thinking unless the user requested another language

#### Scenario: User asks in another language

- **WHEN** the user's latest natural-language request is primarily not Chinese
- **AND** DeepSeek thinking is enabled
- **THEN** Deepy's model prompt SHALL instruct DeepSeek to match that language
  for visible thinking unless the user requested another language
