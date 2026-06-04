## ADDED Requirements

### Requirement: File Tool Surface V2

Deepy SHALL expose a v2 model-facing file tool surface with explicit read, small
edit, whole-file write, and patch-oriented mutation intents.

#### Scenario: V2 file tools are registered

- **WHEN** Deepy constructs the model agent
- **THEN** it SHALL register `read_file`, `edit_text`, `write_file`, and
  `apply_patch` through the OpenAI Agents SDK tool flow
- **AND** the tool descriptions SHALL explain the intended edit scope of each
  tool

#### Scenario: Legacy aliases are not registered

- **WHEN** Deepy constructs the model agent
- **THEN** it SHALL NOT register old model-facing file tool aliases such as
  `read` or `modify`

#### Scenario: Tool intent is unambiguous

- **WHEN** the model needs to read a file, make a small exact edit, replace a
  whole file, or apply a structured multi-file change
- **THEN** Deepy's tool guidance SHALL steer it respectively toward `read_file`,
  `edit_text`, `write_file`, or `apply_patch`

### Requirement: Read File Tool

Deepy SHALL expose `read_file` for reading regular text files and recording
managed file snapshots.

#### Scenario: Text file is read

- **WHEN** the model invokes `read_file` for a regular supported text file
- **THEN** Deepy SHALL return readable text content and metadata
- **AND** it SHALL record a managed snapshot containing a snapshot id, mtime,
  size, content hash, encoding, and line-ending metadata

#### Scenario: Partial text file is read

- **WHEN** the model invokes `read_file` with a partial range or line limit
- **THEN** Deepy SHALL return snippet metadata that can be used by later
  `edit_text` operations
- **AND** it SHALL NOT treat the partial read as permission for an unrestricted
  whole-file replacement

#### Scenario: Non-text file is read

- **WHEN** the model invokes `read_file` for a non-text target that Deepy can
  describe but not safely text-edit
- **THEN** Deepy SHALL return metadata for the target when supported
- **AND** it SHALL mark the target as not tracked for text mutation

### Requirement: Path Resolution And Mutation Policy

Deepy SHALL resolve file mutation targets through a shared path resolver and
policy layer before reading or writing bytes.

#### Scenario: Path escapes the workspace

- **WHEN** a file mutation target resolves outside the allowed workspace or
  writable roots
- **THEN** Deepy SHALL reject the mutation before any side effect
- **AND** it SHALL return a structured path-policy error

#### Scenario: Symlink escapes the workspace

- **WHEN** a file mutation target is a symlink or contains symlink components
  that resolve outside the allowed mutation boundary
- **THEN** Deepy SHALL reject the mutation before any side effect
- **AND** it SHALL include symlink policy metadata in the result

#### Scenario: Target matches ignore or sensitive-file policy

- **WHEN** a file mutation target matches a configured ignore rule or
  sensitive-file rule
- **THEN** Deepy SHALL apply the configured policy as allow, warn, require
  approval, or deny
- **AND** the tool result metadata SHALL identify the policy decision

### Requirement: Approval And Guardrail Metadata Hooks

Deepy SHALL provide a pre-commit approval and guardrail hook for managed file
mutations without requiring an interactive approval UI in this change.

#### Scenario: Mutation is allowed by policy

- **WHEN** the approval and guardrail adapter returns `allow` for a managed file
  mutation
- **THEN** Deepy SHALL continue the mutation pipeline
- **AND** the successful tool result SHALL include policy metadata when relevant

#### Scenario: Mutation receives a warning by policy

- **WHEN** the approval and guardrail adapter returns `warn` for a managed file
  mutation
- **THEN** Deepy MAY continue the mutation pipeline
- **AND** the tool result SHALL include structured warning metadata

#### Scenario: Mutation requires future approval

- **WHEN** the approval and guardrail adapter returns `requires_approval`
- **THEN** Deepy SHALL NOT launch an interactive approval UI in this change
- **AND** it SHALL return a structured policy result or failure describing the
  pending approval requirement
- **AND** it SHALL NOT commit file side effects

#### Scenario: Mutation is denied by policy

- **WHEN** the approval and guardrail adapter returns `deny`
- **THEN** Deepy SHALL reject the mutation before any file side effect
- **AND** the structured error metadata SHALL include the guardrail or approval
  policy reason when safe to expose

### Requirement: Edit Text Tool

Deepy SHALL expose `edit_text` for small-scope exact or string-based edits.

#### Scenario: Exact text edit succeeds

- **WHEN** the model invokes `edit_text` with a target file, `old_string`, and
  `new_string`
- **AND** the target is a supported text file within the allowed mutation
  boundary
- **THEN** Deepy SHALL apply the replacement through the managed text mutation
  engine
- **AND** it SHALL preserve the target file's detected encoding and line-ending
  style

#### Scenario: Expected replacement count is enforced

- **WHEN** the model invokes `edit_text` with `expected_occurrences`
- **AND** the actual replacement count differs from `expected_occurrences`
- **THEN** Deepy SHALL reject the edit
- **AND** it SHALL return structured metadata containing the expected and actual
  replacement counts

#### Scenario: No-op edit is rejected

- **WHEN** the model invokes `edit_text` with an edit that would not change file
  bytes
- **THEN** Deepy SHALL reject the edit unless the tool contract explicitly allows
  no-op confirmation
- **AND** the structured error SHALL identify the no-op condition

#### Scenario: Recoverable snippet argument mistakes

- **WHEN** the model invokes `edit_text` with a literal string such as `"null"`
  for `snippet_id`
- **THEN** Deepy SHALL treat that value as absent and continue with the provided
  `file_path` when present
- **AND** when the model passes a managed snapshot id in `snippet_id`, Deepy MAY
  infer the snapshot file path and continue as a full-file exact edit
- **AND** recovered edits SHALL still enforce exact-match, ambiguity,
  expected-count, stale-snapshot, encoding, and line-ending checks

#### Scenario: Partial read exact edit is auto-promoted

- **WHEN** the model invokes `edit_text` with `file_path`, `old_string`, and
  `new_string`
- **AND** the file has a fresh partial-read snapshot but no full-read snapshot
- **AND** the edit is not explicitly scoped to a snippet
- **THEN** Deepy MAY internally promote the snapshot from the current file
  contents and complete the exact edit in the same tool call
- **AND** the result metadata SHALL identify that the edit used an internal
  auto-read and the previous snapshot reason was partial

#### Scenario: Snippet scope miss can fall back to full file

- **WHEN** the model invokes `edit_text` with both `file_path` and a `snippet_id`
- **AND** `old_string` is not found inside the snippet scope
- **AND** the same `old_string` matches the full file under the normal exact,
  expected-count, ambiguity, stale-snapshot, encoding, and line-ending checks
- **THEN** Deepy MAY apply the edit as a full-file exact edit
- **AND** the result metadata SHALL identify the snippet id that was bypassed

### Requirement: Write File Tool

Deepy SHALL expose `write_file` for new text files and explicit whole-file
replacement.

#### Scenario: New file is written

- **WHEN** the model invokes `write_file` for a path that does not exist
- **THEN** Deepy SHALL create the file through the managed text mutation path
- **AND** the new file SHALL use UTF-8 without BOM by default

#### Scenario: Existing file replacement requires explicit safety

- **WHEN** the model invokes `write_file` for a path that already exists
- **THEN** Deepy SHALL treat the operation as an explicit whole-file replacement
- **AND** it SHALL require an explicit overwrite intent plus a managed snapshot
  id, content hash, or equivalent freshness token for existing-file replacement
- **AND** it SHALL preserve the existing file's detected encoding and line-ending
  style unless the tool explicitly requests an allowed encoding change

#### Scenario: Whole-file replacement is non-text

- **WHEN** the model invokes `write_file` for a non-text or unsupported target
- **THEN** Deepy SHALL reject the operation before writing
- **AND** it SHALL return a structured unsupported-target error

### Requirement: Apply Patch Primary Editing Tool

Deepy SHALL expose `apply_patch` as the primary model-facing tool for structured
file mutations.

#### Scenario: Apply patch tool is registered

- **WHEN** Deepy constructs the model agent
- **THEN** it SHALL register an `apply_patch` tool through the OpenAI Agents SDK
  tool flow
- **AND** the tool description SHALL identify it as the preferred tool for
  multi-file and structured file edits

#### Scenario: Patch creates a file

- **WHEN** the model invokes `apply_patch` with a create-file operation
- **AND** the target path does not exist
- **THEN** Deepy SHALL create the file through the managed text mutation path
- **AND** the new file SHALL use UTF-8 without BOM by default

#### Scenario: Patch updates a file

- **WHEN** the model invokes `apply_patch` with an update-file operation
- **AND** the target file is a supported text file
- **THEN** Deepy SHALL apply the patch through the managed text mutation path
- **AND** it SHALL preserve the target file's detected encoding and line-ending
  style
- **AND** skipped chunks, fuzzy matches, or ambiguous matches SHALL be reported
  through structured warning or failure metadata

#### Scenario: Patch updates with paired replacement blocks

- **WHEN** the model invokes `apply_patch` with an update-file operation using
  paired `@@` old-block and new-block sections without explicit `+` or `-` diff
  line prefixes
- **AND** each old block matches the target file exactly and unambiguously
- **THEN** Deepy SHALL apply each replacement through the managed text mutation
  path
- **AND** blank lines and indentation inside the paired blocks SHALL be preserved
- **AND** common content prefixes such as CSS selectors, CSS custom properties,
  and YAML list markers SHALL NOT force the patch into strict diff parsing

#### Scenario: Patch input uses common model wrappers

- **WHEN** the model invokes `apply_patch` with a patch wrapped in a single
  Markdown code fence
- **THEN** Deepy SHALL parse the patch body inside the fence
- **AND** standard unified diff file headers such as `--- a/path` and `+++ b/path`
  MAY be ignored inside an update operation
- **AND** `a/` or `b/` path prefixes MAY be resolved to the unprefixed project
  path when that is the actual target
- **AND** omitted prefixes on blank context lines or unmarked HTML/context lines
  MAY be treated as context when exact patch matching still succeeds

#### Scenario: Patch matches file ending without newline

- **WHEN** an update hunk old block differs from the target only by an added
  trailing newline in the patch text
- **THEN** Deepy MAY match the existing no-newline-at-EOF file content and apply
  the corresponding newline-trimmed replacement
- **AND** all other exact-match, ambiguity, stale, encoding, and line-ending
  checks SHALL still apply

#### Scenario: Patch preflight fails

- **WHEN** the model invokes `apply_patch`
- **AND** any operation fails parsing, path policy, target classification,
  snapshot freshness, patch matching, parent-directory planning, or backup
  planning
- **THEN** Deepy SHALL reject the patch before committing any file side effects
- **AND** the result SHALL identify every failed operation that can be reported
  safely

#### Scenario: Patch deletes a file

- **WHEN** the model invokes `apply_patch` with a delete-file operation
- **AND** the target file is within the allowed file-mutation boundary
- **THEN** Deepy SHALL delete the file through the managed mutation path
- **AND** the result SHALL include structured metadata identifying the deletion

#### Scenario: Patch moves a file

- **WHEN** the model invokes `apply_patch` with a move operation
- **AND** the source and destination are within the allowed file-mutation boundary
- **THEN** Deepy SHALL apply the move through the managed mutation path
- **AND** it SHALL include both source and destination paths in result metadata

#### Scenario: Patch commit partially fails

- **WHEN** a late platform error occurs after patch preflight succeeds and after
  one or more operations have committed
- **THEN** Deepy SHALL return a structured partial-commit error
- **AND** the result metadata SHALL identify committed operations, failed
  operations, and available backup or recovery metadata

### Requirement: Managed Text Mutation Engine

Deepy SHALL route all built-in text file mutation tools through a shared managed
text mutation engine.

#### Scenario: Text mutation is executed

- **WHEN** `edit_text`, `write_file`, or `apply_patch` performs a text file
  mutation
- **THEN** Deepy SHALL use shared path resolution, text decoding, snapshot,
  stale/hash checks, diff, and byte-writing behavior

#### Scenario: Non-text target is rejected

- **WHEN** a built-in text mutation tool targets a binary, image, video, PDF,
  notebook, archive, database, directory, device, socket, or other unsupported
  non-regular text target
- **THEN** Deepy SHALL reject the mutation
- **AND** it SHALL return a structured error explaining that the target cannot be
  safely mutated through text tools

#### Scenario: Parent directories are created after validation

- **WHEN** a managed text mutation needs to create parent directories
- **THEN** Deepy SHALL create those directories only after path, target, snapshot,
  and pre-write validation has passed
- **AND** rejected mutations SHALL NOT leave newly created empty parent
  directories behind

### Requirement: Structured File Mutation Errors

Deepy SHALL return structured error metadata for built-in file mutation failures.

#### Scenario: File mutation error is returned

- **WHEN** a built-in file mutation fails
- **THEN** Deepy SHALL include a stable machine-readable error code in result
  metadata
- **AND** it SHALL include a human-readable recovery hint when the model can
  safely retry

#### Scenario: Old string is absent

- **WHEN** a focused text edit cannot find the requested `old_string`
- **THEN** Deepy SHALL return a structured tool failure
- **AND** the failure metadata SHALL include an error code identifying an absent
  match
- **AND** it SHALL include closest-match or candidate metadata when available

#### Scenario: Replacement count is unexpected

- **WHEN** a mutation declares an expected number of replacements or patch chunks
- **AND** the actual number does not match
- **THEN** Deepy SHALL reject the mutation
- **AND** it SHALL include the expected and actual counts in structured metadata

#### Scenario: Mutation has no effect

- **WHEN** a built-in text mutation would produce the same bytes as the current
  file
- **THEN** Deepy SHALL return a structured no-op error or warning according to
  the tool contract
- **AND** it SHALL NOT silently report a successful content change

#### Scenario: Error taxonomy is stable

- **WHEN** file mutation errors are serialized
- **THEN** Deepy SHALL use stable codes for path-policy failures, unsupported
  targets, stale snapshots, absent matches, ambiguous matches, expected-count
  mismatches, no-op edits, patch parse failures, patch apply failures, atomic
  write failures, backup failures, guardrail blocks, approval-required policy
  decisions, future approval rejections, and partial commits

#### Scenario: File changed during mutation

- **WHEN** a managed text mutation detects that a target changed after the model's
  readable snapshot
- **THEN** Deepy SHALL reject the mutation
- **AND** the structured error SHALL instruct the model to re-read the file before
  retrying

### Requirement: Atomic Managed Text Writes

Deepy SHALL write managed text mutations through an atomic or best-effort atomic
byte-writing path with backup support where policy requires it.

#### Scenario: Managed text file is written

- **WHEN** Deepy commits updated text bytes for a managed mutation
- **THEN** it SHALL write bytes to a temporary file in the target directory and
  rename it over the target when the platform supports that operation
- **AND** it SHALL preserve existing file permissions when possible

#### Scenario: Backup is requested by policy

- **WHEN** the managed mutation policy requires a backup for a target file
- **THEN** Deepy SHALL create backup metadata before committing the mutation
- **AND** the tool result SHALL include enough metadata to locate or describe the
  backup

#### Scenario: Windows rename is temporarily denied

- **WHEN** a Windows managed text write receives a retryable rename error such as
  `EPERM` or `EACCES`
- **THEN** Deepy SHALL retry the rename with a bounded backoff before failing

#### Scenario: Atomic write fallback is used

- **WHEN** Deepy cannot complete an atomic rename and must use a non-atomic
  fallback
- **THEN** the tool result metadata SHALL identify that fallback
- **AND** the mutation SHALL still use Deepy's selected byte encoding

## MODIFIED Requirements

### Requirement: Core Tools

Deepy SHALL expose project tools for shell execution, file reading, small-scope
text editing, explicit file writing, patch-oriented file mutation, user
questions, web search, web fetch, skill loading, and todo planning.

#### Scenario: Tools are registered

- **WHEN** the model agent is constructed
- **THEN** Deepy SHALL make the supported tools available through the OpenAI Agents
  SDK tool flow
- **AND** the registered tool set SHALL include `read_file`, `edit_text`,
  `write_file`, and `apply_patch`
- **AND** the registered tool set SHALL identify `apply_patch` as the primary
  complex editing tool
- **AND** the registered tool set SHALL NOT include old `read` or `modify` file
  aliases

### Requirement: Read-Before-Write Protection

Deepy SHALL protect existing files from stale or uninformed writes by ensuring a
managed readable snapshot or model-authored write snapshot exists before
committing existing-file changes.

#### Scenario: Existing file is exact-edited without a prior snapshot

- **WHEN** the model invokes `edit_text` with `old_string` and `new_string` for
  an existing file that has no managed snapshot in the current tool runtime
- **THEN** Deepy SHALL internally establish a managed snapshot from the current
  file contents before applying the edit
- **AND** Deepy SHALL apply the edit only if the existing exact-match,
  uniqueness, encoding, and line-ending checks pass
- **AND** the successful result SHALL include metadata indicating that an
  internal auto-read snapshot was used

#### Scenario: Existing file is full-content replaced without a prior snapshot

- **WHEN** the model invokes `write_file` with `content` for an existing file
  without the required replacement snapshot
- **THEN** Deepy SHALL reject the operation
- **AND** Deepy SHALL direct the model to use the managed existing-file edit,
  `apply_patch`, or replacement flow instead

#### Scenario: Existing file changed after a managed snapshot

- **WHEN** a tool attempts to edit, write, or patch an existing file that already
  has a managed snapshot
- **AND** the file has changed since that snapshot was recorded
- **THEN** Deepy SHALL reject the operation
- **AND** it SHALL require the file to be read again before editing

#### Scenario: File changes between planning and commit

- **WHEN** a managed text mutation reads or previews an existing file for a
  side-effecting operation
- **AND** the file changes before Deepy commits the mutation
- **THEN** Deepy SHALL reject the mutation before writing whenever the change is
  detectable through the managed snapshot checks
- **AND** it SHALL return structured stale-read metadata

### Requirement: Unified File Modification Path

Deepy SHALL prefer a patch-oriented file modification path for structured file
changes so the model does not repeatedly call write, read, and edit for related
updates.

#### Scenario: Model changes existing code

- **WHEN** the model needs to update existing code, tests, docs, or config
- **THEN** tool descriptions SHALL steer it toward `edit_text` for one small
  single-file exact replacement or insertion
- **AND** tool descriptions SHALL steer it toward `apply_patch` when the change
  has multiple edits in one file, touches multiple files, deletes or moves files,
  creates files as part of a broader change, or replaces a larger block
- **AND** the `apply_patch` description SHALL include concrete patch grammar
  cues such as `*** Begin Patch`, file operation headers, `-old`/`+new` update
  lines, and paired `@@` replacement blocks

#### Scenario: Model exact-edits an existing file before reading it

- **WHEN** the model invokes `edit_text` with `old_string` and `new_string` for
  an existing file before invoking `read_file`
- **THEN** Deepy SHALL complete the edit in the same tool call when the internal
  snapshot and exact edit checks succeed
- **AND** Deepy SHALL NOT require a failed edit result followed by a separate
  read call for this recoverable missing-snapshot case

#### Scenario: Model exact-edits after a partial read

- **WHEN** the model has only partially read an existing file
- **AND** it invokes `edit_text` with a `file_path` for a normal single-file
  exact edit
- **THEN** Deepy SHALL NOT require a failed edit result followed by a separate
  full-file read when the current file is fresh and the exact edit checks pass
- **AND** Deepy SHALL still reject stale partial snapshots before writing

#### Scenario: Model performs a multi-file edit

- **WHEN** the model needs to create, update, delete, or move multiple files as
  one logical change
- **THEN** Deepy's tool guidance SHALL steer the model toward `apply_patch`
- **AND** successful results SHALL identify every changed file in structured
  metadata

### Requirement: Tool Output Display

Deepy SHALL render tool activity as concise progress and readable diffs for
managed file mutations.

#### Scenario: File content changes

- **WHEN** `write_file`, `edit_text`, or `apply_patch` succeeds
- **THEN** Deepy SHALL render a diff-style preview of changed content
- **AND** additions and deletions SHALL be visually distinguishable without
  relying only on leading `+` or `-` markers

#### Scenario: Patch changes multiple files

- **WHEN** `apply_patch` succeeds for multiple file operations
- **THEN** Deepy SHALL render a concise changed-file summary
- **AND** its display diff preview SHALL include visible sections for multiple
  changed files instead of allowing the first large file to consume the whole
  preview
- **AND** detailed full diff metadata SHALL remain available for UI renderers

#### Scenario: Patch call arguments are summarized

- **WHEN** Deepy renders a pending `apply_patch` tool call
- **THEN** it SHALL summarize the call with the number of target files and
  concise target file paths
- **AND** it SHALL NOT render the full patch body as the tool-call argument
  summary
