## MODIFIED Requirements

### Requirement: Core Tools

Deepy SHALL expose project tools for shell execution, local code search, v3 file
reading, v3 file writing, v3 exact text updates, user questions, web search, web
fetch, skill loading, and todo planning.

#### Scenario: Tools are registered

- **WHEN** the model agent is constructed
- **THEN** Deepy SHALL make the supported tools available through the OpenAI Agents
  SDK tool flow
- **AND** the registered tool set SHALL include `Search`, `Read`, `Write`, and
  `Update`
- **AND** the registered tool set SHALL identify `Search` as the preferred tool
  for local repository text/code searches
- **AND** the registered tool set SHALL identify `Update` as the primary exact
  text editing tool for one or more replacements across one or more files
- **AND** the registered tool set SHALL NOT include old model-facing file tools
  such as `read_file`, `edit_text`, `write_file`, `apply_patch`, `read`, or
  `modify`

### Requirement: Read-Before-Write Protection

Deepy SHALL protect existing files from stale or uninformed writes by ensuring
fresh runtime-managed read state or model-authored write state exists before
committing existing-file changes.

#### Scenario: Existing file is exact-updated without a prior read

- **WHEN** the model invokes `Update` for an existing file that has no
  runtime-managed read state in the current tool runtime
- **THEN** Deepy MAY internally establish managed read state from the current
  file contents before applying the update
- **AND** Deepy SHALL apply the update only if exact-match, uniqueness,
  expected-count, encoding, line-ending, and stale-write checks pass
- **AND** the successful result SHALL include metadata indicating that an
  internal auto-read was used

#### Scenario: Existing file is full-content replaced without a prior read

- **WHEN** the model invokes `Write` with content for an existing file without
  fresh runtime-managed read state
- **THEN** Deepy SHALL reject the operation
- **AND** Deepy SHALL direct the model to use `Read` before retrying the
  replacement

#### Scenario: Existing file changed after managed read state

- **WHEN** `Write` or `Update` attempts to mutate an existing file that already
  has managed read state
- **AND** the file has changed since that read state was recorded
- **THEN** Deepy SHALL reject the operation
- **AND** it SHALL require the file to be read again before editing

#### Scenario: File changes between planning and commit

- **WHEN** a managed text mutation reads or previews an existing file for a
  side-effecting operation
- **AND** the file changes before Deepy commits the mutation
- **THEN** Deepy SHALL reject the mutation before writing whenever the change is
  detectable through the managed read-state checks
- **AND** it SHALL return structured stale-read metadata

### Requirement: Unified File Modification Path

Deepy SHALL prefer the v3 `Update` tool for exact text changes so the model does
not repeatedly choose between overlapping write, edit, and patch tools.

#### Scenario: Model changes existing code

- **WHEN** the model needs to update existing code, tests, docs, or config
- **THEN** tool descriptions SHALL steer it toward `Update` for exact text
  replacements, including one edit, multiple edits in one file, and multiple
  edits across files
- **AND** tool descriptions SHALL steer it toward `Write` only for new files or
  explicit whole-file replacement
- **AND** tool descriptions SHALL steer it toward `Read` when context or fresh
  read state is needed before mutation

#### Scenario: Model exact-updates an existing file before reading it

- **WHEN** the model invokes `Update` for an existing file before invoking `Read`
- **THEN** Deepy MAY complete the update in the same tool call when internal
  read-state creation and exact update checks succeed
- **AND** Deepy SHALL NOT require a failed update result followed by a separate
  read call for this recoverable missing-read case

#### Scenario: Model exact-updates after a partial read

- **WHEN** the model has only partially read an existing file
- **AND** it invokes `Update` with a normal file-path exact edit
- **THEN** Deepy SHALL NOT require a failed update result followed by a separate
  full-file read when the current file is fresh and the exact update checks pass
- **AND** Deepy SHALL still reject stale partial read state before writing

#### Scenario: Model performs a multi-file update

- **WHEN** the model needs to update multiple files as one logical exact-text
  change
- **THEN** Deepy's tool guidance SHALL steer the model toward one `Update` call
  containing multiple edits
- **AND** successful results SHALL identify every changed file in structured
  metadata

### Requirement: Tool Output Display

Deepy SHALL render tool activity as concise progress and readable diffs for
managed file mutations.

#### Scenario: File content changes

- **WHEN** `Write` or `Update` succeeds
- **THEN** Deepy SHALL render a diff-style preview of changed content
- **AND** additions and deletions SHALL be visually distinguishable without
  relying only on leading `+` or `-` markers

#### Scenario: Update changes multiple files

- **WHEN** `Update` succeeds for multiple target files
- **THEN** Deepy SHALL render a concise changed-file summary
- **AND** its display diff preview SHALL include each changed file
- **AND** multi-file update diffs SHALL be rendered as separate per-file
  sections so each section can use its own file path for syntax highlighting
- **AND** detailed full diff metadata SHALL remain available for UI renderers

#### Scenario: Update call arguments are summarized

- **WHEN** Deepy renders a pending `Update` tool call with one or more edits
- **THEN** it SHALL summarize the call with the edit count, number of target
  files, and concise target file paths
- **AND** it SHALL NOT render full file contents, replacement blocks, or raw
  edit JSON as the tool-call argument summary

## REMOVED Requirements

### Requirement: Edit Text Tool
**Reason**: Replaced by the v3 `Update` tool, which handles single and multiple
exact text edits without a separate model-facing `edit_text` schema.
**Migration**: Use `Update` with canonical `old` and `new` fields.

### Requirement: Write File Tool
**Reason**: Replaced by the v3 `Write` tool, which hides freshness tokens from
the model and uses runtime-managed read state.
**Migration**: Use `Write` with path, content, and explicit overwrite intent
where needed.

### Requirement: Apply Patch Primary Editing Tool
**Reason**: Structured `apply_patch` created overlapping edit paths, verbose
nullable arguments, and failure modes that increased model thinking and retry
cost.
**Migration**: Use `Update` for exact text edits and `Write` for whole-file
creation or replacement.

### Requirement: Numeric Snapshot Freshness Tokens
**Reason**: V3 file tools keep freshness tokens inside the runtime instead of
exposing them to the model-facing schema.
**Migration**: Use `Read` to establish fresh runtime-managed read state, then
invoke `Write` or `Update`.
