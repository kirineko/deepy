## ADDED Requirements

### Requirement: Provider-Compatible Tool Schemas
Deepy SHALL expose built-in tool schemas in a provider-compatible form while
preserving the same built-in tool names and runtime semantics.

#### Scenario: MiMo receives a tool schema with nullable optional arguments
- **WHEN** Deepy constructs built-in tools for a MiMo-compatible model
- **AND** a tool schema has a property whose JSON schema type includes `null`
- **AND** that property appears in the schema's `required` list
- **THEN** the model-visible schema SHALL remove that property from `required`
- **AND** it SHALL remove `null` from that property's model-visible type while
  leaving the property available as optional in `properties`
- **AND** it SHALL preserve the tool name, description, strict mode, and
  invocation handler

#### Scenario: MiMo omits an optional nullable tool argument
- **WHEN** a MiMo-compatible model invokes a built-in tool without an optional
  nullable argument
- **THEN** Deepy SHALL interpret the missing argument using the same runtime
  default as an explicit `null`
- **AND** the tool SHALL execute through the normal OpenAI Agents SDK tool flow

#### Scenario: Non-MiMo provider receives built-in tools
- **WHEN** Deepy constructs built-in tools for DeepSeek or a non-MiMo provider
- **THEN** Deepy SHALL preserve the existing model-visible tool schemas
- **AND** it SHALL NOT remove nullable fields from `required`

#### Scenario: Nested schema contains nullable required fields
- **WHEN** a MiMo-compatible model receives a built-in tool schema with nested
  object schemas
- **THEN** Deepy SHALL apply the nullable-required compatibility transformation
  recursively to nested object schemas
- **AND** it SHALL preserve non-nullable required fields at every level
