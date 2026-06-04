## ADDED Requirements

### Requirement: Read Range Argument Recovery
Deepy's v3 `Read` tool SHALL recover from common malformed line-range arguments
only when they can be safely normalized to the canonical schema shape.

#### Scenario: Single read recovers unquoted line range
- **WHEN** the model invokes `Read` with JSON-like arguments containing a target
  path and an unquoted simple inclusive line range such as `range: 80-120`
- **THEN** Deepy SHALL normalize the range to the schema-valid string form
  `"80-120"` before executing the read
- **AND** it SHALL return the requested bounded line-numbered content
- **AND** the result metadata SHALL indicate that argument repair was applied

#### Scenario: Batch read recovers unquoted target ranges
- **WHEN** the model invokes `Read` with multiple file targets and one or more
  targets contain an unquoted simple inclusive line range
- **THEN** Deepy SHALL normalize those target ranges to schema-valid string
  values before executing the batch read
- **AND** it SHALL preserve the existing per-target success and failure behavior
  for the batch result

#### Scenario: Unsafe malformed range remains retryable
- **WHEN** the model invokes `Read` with malformed arguments that cannot be
  safely normalized to the canonical schema
- **THEN** Deepy SHALL return a retryable invalid-argument result
- **AND** it SHALL NOT execute the read
- **AND** the recovery guidance SHALL continue to instruct the model to pass a
  valid JSON object matching the tool schema

### Requirement: Read Range Tool Guidance
Deepy's model-facing `Read` tool guidance SHALL make the canonical line-range
argument shape explicit.

#### Scenario: Read description shows quoted range examples
- **WHEN** Deepy exposes the v3 `Read` tool to a model
- **THEN** the tool description SHALL show that `range` values are quoted
  strings such as `"80-120"`
- **AND** the guidance SHALL cover both single-target reads and multi-target
  `files` reads
