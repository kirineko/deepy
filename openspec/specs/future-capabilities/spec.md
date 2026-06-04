# Future Capabilities Catalog

## Purpose

This spec captures completed planning decisions from `spec/advanced.md`. It is a
local baseline for evaluating future changes, not a claim that every listed
capability is already implemented.

## Requirements

### Requirement: Future Work Classification

Deepy SHALL classify future feature work before implementation.

#### Scenario: A new large feature is proposed

- **WHEN** a new capability such as MCP, plan mode, approval runtime, subagents,
  indexing, model routing, or document processing is proposed
- **THEN** the proposal SHALL state whether it belongs to core agent behavior,
  DeepSeek-specific optimization, terminal UI, session management, or ecosystem
  integration

### Requirement: DeepSeek Differentiation

Deepy SHALL prioritize DeepSeek-specific value when choosing future work.

#### Scenario: A future enhancement is evaluated

- **WHEN** multiple enhancements compete for priority
- **THEN** DeepSeek KV-cache optimization, stable prompt layering, context
  compaction quality, thinking controls, and DeepSeek error adaptation SHALL be
  treated as high-value differentiators

### Requirement: Controlled Expansion

Deepy SHALL avoid turning early feature work into an uncontrolled platform
rewrite.

#### Scenario: A high-complexity feature is proposed

- **WHEN** a proposal involves MCP, subagents, Web UI, SQLite migration, OAuth, or
  plugin systems
- **THEN** the proposal SHALL include a staged rollout, explicit non-goals, and
  verification gates before implementation
