## ADDED Requirements

### Requirement: Subagent Responses Model Resolution
Deepy SHALL resolve subagent models within the active provider through the same Responses path as the main agent.

#### Scenario: Inherited model
- **WHEN** a subagent has no explicit model
- **THEN** it SHALL inherit the active provider model, credentials and supported settings

#### Scenario: Explicit override
- **WHEN** a custom subagent specifies a model in the active provider catalog
- **THEN** Deepy SHALL construct a Responses model for that provider/model
- **AND** it SHALL NOT let an unqualified string select an SDK default provider

#### Scenario: Invalid override
- **WHEN** a subagent model belongs to another provider or is not supported
- **THEN** Deepy SHALL reject that override with a concise diagnostic and keep other valid agents usable

#### Scenario: Search boundary
- **WHEN** a subagent is allowed WebSearch or inherits search-class MCP tools
- **THEN** it SHALL retain the existing tool/MCP inheritance and priority boundaries
- **AND** built-in WebSearch SHALL use independent DeepSeek credentials
