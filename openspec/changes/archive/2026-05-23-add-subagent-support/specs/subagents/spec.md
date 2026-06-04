## ADDED Requirements

### Requirement: Built-In Subagents

Deepy SHALL provide focused built-in subagents for common specialist workflows.

#### Scenario: Built-in subagents are available

- **WHEN** Deepy constructs the main agent with subagents enabled
- **THEN** Deepy SHALL make `explore`, `reviewer`, and `tester` available
  as model-callable subagent tools
- **AND** each built-in subagent SHALL have a concise description that tells the
  main agent when to use it
- **AND** each built-in subagent SHALL have bounded max-turn defaults

#### Scenario: Explore subagent is used

- **WHEN** the main agent needs broad codebase, documentation, or search-oriented
  investigation that can be performed independently
- **THEN** it MAY delegate the task to `explore`
- **AND** `explore` SHALL operate without source mutation tools by default

#### Scenario: Reviewer subagent is used

- **WHEN** the main agent needs focused review of code, design, security,
  correctness, test risk, or maintainability
- **THEN** it MAY delegate the task to `reviewer`
- **AND** `reviewer` SHALL operate without source mutation tools by default

#### Scenario: Tester subagent is used

- **WHEN** the main agent needs bug reproduction, command-based verification, or
  targeted test execution
- **THEN** it MAY delegate the task to `tester`
- **AND** `tester` SHALL receive constrained test execution capability
- **AND** it SHALL NOT receive source mutation tools by default

### Requirement: Custom Subagent Definitions

Deepy SHALL support user-defined subagents in Deepy-owned configuration
directories.

#### Scenario: Project custom subagent exists

- **WHEN** a project contains `.deepy/subagents/<name>.md`
- **THEN** Deepy SHALL discover that file as a project-level custom subagent
- **AND** it SHALL NOT require or read `.agents/skills` for subagent definitions

#### Scenario: User custom subagent exists

- **WHEN** the user has `~/.deepy/subagents/<name>.md`
- **THEN** Deepy SHALL discover that file as a user-level custom subagent

#### Scenario: Subagent names collide

- **WHEN** project, user, and built-in subagents share the same normalized name
- **THEN** Deepy SHALL prefer the project definition over the user definition
- **AND** it SHALL prefer the user definition over the built-in definition

#### Scenario: Custom subagent definition is valid

- **WHEN** a custom subagent Markdown file includes valid YAML frontmatter and
  body instructions
- **THEN** Deepy SHALL parse `name`, `description`, optional `model`, optional
  `tools`, optional `disallowedTools`, optional `mcp`, and optional `max_turns`
- **AND** it SHALL use the Markdown body as the subagent's system instructions

#### Scenario: Custom subagent definition is invalid

- **WHEN** a custom subagent definition is missing required fields, references
  unsupported tools, requests invalid MCP inheritance, or exceeds bounded
  runtime limits
- **THEN** Deepy SHALL ignore or reject that definition with a concise diagnostic
- **AND** the main Deepy session SHALL continue with other valid subagents

### Requirement: Subagent Tool Boundaries

Deepy SHALL give subagents explicit bounded tool sets instead of inheriting all
main-agent tools.

#### Scenario: Subagent tools are built

- **WHEN** Deepy constructs a subagent
- **THEN** Deepy SHALL derive the subagent's tools from the subagent definition
  and Deepy's supported subagent tool policy
- **AND** it SHALL exclude unsupported or forbidden tools before exposing the
  subagent to the main agent

#### Scenario: Subagent attempts nested delegation

- **WHEN** a subagent attempts to create or call another subagent
- **THEN** Deepy SHALL prevent nested subagent spawning
- **AND** it SHALL return a clear unavailable-tool result or omit subagent tools
  from the subagent's tool set

#### Scenario: Built-in subagent completes

- **WHEN** a built-in or custom subagent finishes successfully
- **THEN** it SHALL return a concise report to the main agent
- **AND** the report SHALL include the assigned scope, key findings or actions,
  relevant file paths when applicable, command results when applicable, and any
  unresolved issues

### Requirement: Subagent Lifecycle Visibility

Deepy SHALL show users when subagents are assigned and what they return.

#### Scenario: Subagent starts

- **WHEN** the main agent invokes a subagent
- **THEN** Deepy SHALL render a visible subagent-start event
- **AND** the event SHALL include the subagent name and concise task description

#### Scenario: Subagent completes

- **WHEN** a subagent completes successfully
- **THEN** Deepy SHALL render a visible subagent-completed event
- **AND** the event SHALL include a concise result summary

#### Scenario: Subagent fails

- **WHEN** a subagent fails, times out, or is blocked
- **THEN** Deepy SHALL render a visible subagent failure or blocked event
- **AND** the main agent SHALL retain control and decide how to proceed

#### Scenario: Subagent generates verbose nested output

- **WHEN** a subagent emits nested thinking, tool calls, or progress output
- **THEN** Deepy SHALL keep the main transcript readable
- **AND** it SHALL avoid flooding the main assistant response with raw nested
  output unless the user explicitly asks for details
