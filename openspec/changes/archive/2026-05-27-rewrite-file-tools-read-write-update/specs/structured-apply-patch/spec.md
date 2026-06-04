## ADDED Requirements

### Requirement: Structured Apply Patch Removed
Deepy SHALL NOT expose `apply_patch` as a model-facing built-in file editing
tool for new runs.

#### Scenario: V3 file tools replace structured apply patch
- **WHEN** Deepy constructs the model-facing built-in file tool set
- **THEN** it SHALL omit `apply_patch`
- **AND** it SHALL expose `Read`, `Write`, and `Update` as the canonical file
  operation tools

## REMOVED Requirements

### Requirement: Structured Apply Patch Protocol
**Reason**: The v3 file tool rewrite removes `apply_patch` from the
model-facing built-in file tool surface.
**Migration**: Use `Read`, `Write`, and `Update` for model-facing file
operations.

### Requirement: Apply Patch Operation Types
**Reason**: Patch operation variants are replaced by simpler v3 tool intents:
read context, write whole file content, or update exact text.
**Migration**: Use `Update` for exact replacement edits and `Write` for file
creation or whole-file replacement.

### Requirement: Structured Patch Preflight
**Reason**: V3 `Update` owns multi-edit validation and preflight. The
structured patch batch protocol is no longer a canonical model-facing contract.
**Migration**: Use `Update` multi-edit preflight semantics.

### Requirement: Structured Patch Result Metadata
**Reason**: V3 `Write` and `Update` provide canonical mutation result metadata
and diff previews.
**Migration**: Read mutation metadata from `Write` and `Update` results.
