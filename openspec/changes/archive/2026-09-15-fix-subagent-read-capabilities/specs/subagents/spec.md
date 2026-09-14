## ADDED Requirements

### Requirement: Subagent Read Model Capabilities
Deepy SHALL validate Read image results against the effective model of the agent invoking the tool without changing shared runtime settings.

#### Scenario: Image-capable child of a text-only parent
- **WHEN** a text-only parent delegates to an image-capable model override
- **THEN** the child's single and batch Read calls SHALL accept supported images

#### Scenario: Text-only child of an image-capable parent
- **WHEN** an image-capable parent delegates to a text-only model override
- **THEN** the child's Read calls SHALL return image capability errors without image attachments

#### Scenario: Inheritance and concurrent calls
- **WHEN** inherited, overridden, and parent Read calls run concurrently
- **THEN** each SHALL use its own effective model capabilities
- **AND** shared file state, audit policy, search counters, and runtime settings SHALL remain shared and unchanged by capability selection
