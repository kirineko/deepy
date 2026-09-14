# structured-apply-patch Specification

## Purpose

Record the removal of the legacy model-facing apply_patch tool in favor of the current file-editing tools.

## Requirements
### Requirement: Structured Apply Patch Removed
Deepy SHALL NOT expose `apply_patch` as a model-facing built-in file editing
tool for new runs.

#### Scenario: V3 file tools replace structured apply patch
- **WHEN** Deepy constructs the model-facing built-in file tool set
- **THEN** it SHALL omit `apply_patch`
- **AND** it SHALL expose `Read`, `Write`, and `Update` as the canonical file
  operation tools

