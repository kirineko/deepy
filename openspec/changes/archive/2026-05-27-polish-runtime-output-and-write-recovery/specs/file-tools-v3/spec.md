## MODIFIED Requirements

### Requirement: Write Tool
Deepy SHALL expose `Write` for creating new text files and explicit whole-file
replacement without exposing freshness tokens to the model.

#### Scenario: Existing file replacement is fresh
- **WHEN** the model invokes `Write` for an existing text file with explicit
  overwrite intent
- **AND** Deepy has fresh runtime-managed read state for that file or can safely
  auto-read the current file because no stale snapshot exists
- **THEN** Deepy SHALL replace the whole file through the managed text mutation
  path
- **AND** it SHALL preserve the existing file's detected encoding and
  line-ending style unless a future explicit encoding option allows otherwise

#### Scenario: Existing file replacement is stale
- **WHEN** the model invokes `Write` for an existing file after Deepy has a
  runtime-managed read state that is no longer fresh
- **THEN** Deepy SHALL reject the mutation before writing
- **AND** the result SHALL instruct the model to call `Read` for the target path
  before retrying
- **AND** the tool schema SHALL NOT require the model to pass `snapshot_id`,
  `snapshot_token`, or `expected_hash`
