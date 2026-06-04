## Context

Deepy currently exposes a compact tool surface through the OpenAI Agents SDK
FunctionTool flow. File operations are implemented mostly inside
`src/deepy/tools/builtin.py`, with `read`, `write`, `edit`, and model-facing
`modify` sharing `FileState` snapshots and text encoding helpers. The current
implementation already preserves existing encodings and line endings, supports
GB18030-compatible text, handles UTF-16LE and UTF-8 signatures, returns diff
metadata, and protects stale existing files.

The weak point is the contract shape. `modify` is broad enough to represent new
file creation, exact text replacement, and limited whole-file recovery, so the
schema cannot make invalid states unrepresentable. `expected_occurrences` exists
in the schema but is not enforced. There is no first-class patch tool for
multi-file create/update/delete/move operations. The safety checks are also
mostly tied to edit/write implementation details rather than expressed as a
shared mutation pipeline that every side-effecting file tool must use.

OpenAI Agents SDK guidance maps this kind of side effect to local runtime tools
with clear schemas, tool-local validation, and approval/guardrail boundaries.
Deepy should keep its local runtime ownership while making the mutation surface
more explicit.

## Goals / Non-Goals

**Goals:**

- Define the v2 model-facing file tool surface as `read_file`, `edit_text`,
  `write_file`, and `apply_patch`.
- Make `edit_text` the preferred model-facing path for small single-file exact
  edits, and `apply_patch` the path for structured and multi-file changes.
- Make `edit_text` the small-scope exact/string edit path and remove the old
  model-facing `modify` alias.
- Make `write_file` the explicit new-file and whole-file replacement path.
- Give every file mutation path the same path resolution, text encoding,
  snapshot/hash, stale-check, diff, backup, and structured-error behavior.
- Preserve the established Windows policy: new managed text files are UTF-8
  without BOM, while edits preserve existing encodings and line endings.
- Align with OpenAI Agents SDK semantics: strict schemas where feasible,
  function-tool validation close to execution, structured approval/guardrail
  metadata, and explicit future hooks for approvals or guardrails around side
  effects.

**Non-Goals:**

- Replace the entire OpenAI Agents SDK integration.
- Add a full interactive diff editor or GUI approval flow in this change.
- Interrupt tool execution for interactive file-mutation approval in this
  change.
- Guarantee readability in external Windows console commands such as `cat` for
  UTF-8 files under a non-UTF-8 code page.
- Mutate binary, image, PDF, notebook, archive, database, or device-like files
  through text mutation tools.
- Preserve old `read` or `modify` as model-facing compatibility aliases.

## Model Tool Surface

The target model-facing file surface is:

- `read_file`: read regular text files and record managed snapshots.
- `edit_text`: make small exact/string replacements with replacement-count,
  no-op, stale-read, partial-read recovery, snippet-scope recovery, and
  fuzzy-diagnostic checks.
- `write_file`: create new text files or explicitly replace whole files when the
  safety contract allows that replacement.
- `apply_patch`: create, update, delete, and move one or more files as the path
  for multi-file, destructive, or large structured edits.

Old `read` and `modify` names are removed from the model-facing tool surface so
the model has only one obvious path for each file operation intent.

## Decisions

### Expose a v2 file tool surface

Deepy should make file intent explicit at the model boundary. `edit_text` and
`write_file` separate two different risk profiles that `modify` currently
combines: small exact replacements and whole-file writes. `apply_patch` becomes
the complex edit path instead of growing `modify` into a patch language.

Compatibility aliases were considered, but this change is an internal model
tool surface migration and exposing both generations makes tool choice worse.

### Prefer `edit_text` for small exact edits

Single-file changes where the model already knows the current text should use
`edit_text`. That keeps the schema small, avoids patch grammar mistakes for CSS,
HTML, and prose blocks, and matches the common "insert one block" or "replace
one known block" workflow. If the model has only a fresh partial read, Deepy may
promote the managed snapshot internally for exact full-file matching; if a
provided snippet misses but `file_path` is present and the old text matches the
full file unambiguously, Deepy may recover by using the full-file scope.

### Use `apply_patch` for structured edit API

`apply_patch` will accept a structured patch format that can create, update,
delete, and move files. This is the right tool for multi-file, destructive, or
large structured work because it represents those changes directly, keeps
context close to the change, and maps cleanly to OpenAI Agents SDK local
`ApplyPatchTool` concepts. The implementation should hide the SDK-specific
choice behind an adapter so Deepy can start with a FunctionTool-compatible patch
payload and later switch to a custom
`ApplyPatchTool` integration without changing the runtime mutation engine.

For the first implementation, prefer a single `patch` string payload using a
Codex-style patch grammar over a JSON list of operations. That shape is easier
for models to produce, keeps multi-file changes readable in transcripts, and can
still be wrapped in a strict FunctionTool schema. The parser, not ad hoc string
splitting inside the tool body, should own validation and error reporting. The
parser may accept a conservative paired replacement-block form for exact updates
when no explicit `+` or `-` diff lines are present, because model-generated
patches often use `@@ old block @@ new block` for code with blank lines.

Alternative considered: keep expanding `modify` into a universal tool or keep it
as a compatibility adapter. Both options preserve ambiguity at the model
boundary, so this change removes `modify` from the model tool surface.

### Introduce a shared mutation engine

The implementation should split mutation logic into explicit components:

- `PathResolver`: resolve relative paths under the active cwd and reject invalid
  or unsafe text-mutation targets, including symlink escapes and paths blocked
  by sensitive-file or ignore policy.
- `TextFileService`: read bytes once, detect encoding and line endings, classify
  text vs non-text, and encode writes.
- `SnapshotStore` / `FileMutationState`: track read/write snapshots, snapshot
  ids, snippet scopes, partial-read ranges, mtime/size, and content hashes.
- `PatchMatcher`: apply exact or context-based patch chunks and report skipped
  chunks, ambiguity, closest matches, or fuzz metadata.
- `DiffBuilder`: create concise display diffs and structured diff metadata.
- `AtomicWriter`: write bytes through temp-file + rename with Windows retry,
  preserving target permissions and creating backups when policy requires it.
- `ApprovalGuardrailAdapter`: evaluate mutation intent before file side effects
  and return structured approval/guardrail metadata through a stable hook point;
  this change does not need to block on a full interactive approval UI.
- `MutationResult`: standardize `ok`, `error.code`, model-facing message,
  user-facing summary, metadata, and diff payloads.

Alternative considered: keep helpers inside `builtin.py`. That is cheaper
initially but keeps future safety fixes coupled to individual tools.

### Treat safety as a multi-stage check

Existing-file mutations should check freshness before reading for mutation
planning, after reading for TOCTOU detection, and immediately before committing
bytes. This does not eliminate all race windows, but it narrows them and gives
the model deterministic recovery instructions.

Alternative considered: rely only on the existing snapshot check. That catches
normal stale edits but leaves avoidable race windows around diff preview,
approval delays, and final writes.

### Make multi-file patch commits preflight-first

`apply_patch` should parse and validate every operation before committing any
file side effects. Validation includes path policy, text target classification,
snapshot/hash freshness, patch matching, expected operation counts, parent
directory plans, and destructive-operation backup plans. If validation fails,
Deepy should leave the filesystem unchanged.

If a commit-time platform failure still happens after preflight, the result must
identify which operations were committed, which failed, and what backup or
recovery metadata is available. This makes best-effort recovery explicit instead
of pretending multi-file filesystem edits are perfectly transactional.

### Define a stable mutation error taxonomy

File mutation errors should use stable machine-readable codes in addition to
human-readable messages. The first taxonomy should cover path policy failures,
unsupported targets, stale snapshots, absent or ambiguous matches, unexpected
replacement counts, no-op edits, patch parse failures, patch apply failures,
atomic write failures, backup failures, guardrail blocks, approval-required
decisions, and approval rejections when a future interactive approval runtime
exists.

The taxonomy should live close to the shared mutation engine so `edit_text`,
`write_file`, and `apply_patch` calls cannot drift.

### Implement approval hooks without interactive approval

This change should implement the `ApprovalGuardrailAdapter` as a deterministic
pre-commit decision point that can return `allow`, `warn`, `requires_approval`,
or `deny` metadata. For now, `allow` and `warn` may continue through the
mutation pipeline, `deny` must block the mutation, and `requires_approval` must
return a structured failure or policy result rather than launching an
interactive approval flow.

That keeps the file-mutation engine aligned with OpenAI Agents SDK approval and
guardrail concepts while avoiding a coupled terminal UI approval refactor in the
same change.

### Preserve Windows text policy

Deepy should keep plain UTF-8 without BOM for new managed text files on all
platforms. Existing text files should be written back with their detected
encoding and line-ending style. Additional detection may be added for UTF-16BE
or UTF-32, but the default new-file policy should not change. `.bat` and `.cmd`
new-file writes may receive CRLF defaults if tests prove that policy is useful,
but `.ps1` must not automatically opt into a UTF-8 BOM without a separate
decision because Deepy's current constraint is UTF-8 without BOM for new managed
text files.

Alternative considered: add a UTF-8 BOM to new PowerShell files on Windows.
That can help Windows PowerShell 5.1, but Deepy's current target includes
PowerShell 7 and prior testing established that BOM can break source parser
expectations.

### Make schemas stricter without forcing one impossible shape

`apply_patch` should have a strict input schema or a custom-tool grammar if the
runtime supports it cleanly. Existing JSON function tools should move toward
strict schemas by making optional fields nullable and required where the
OpenAI strict-schema rules require it.

`write_file` should make existing-file replacement explicit with an overwrite
intent and a snapshot id, hash, or equivalent freshness token. New-file writes
should remain simple; overwriting existing text is the risky case that needs a
clear model-side contract.

Alternative considered: keep a non-strict `modify` schema for migration. That
keeps a union-shaped tool in the model surface and undermines the v2 contract.

## Risks / Trade-offs

- Patch matching accepts the wrong location when fuzzy matching is too generous
  -> keep exact/context matching as the default, require low fuzz, return
  warnings, and do not silently apply skipped chunks.
- Strict schemas cause provider regressions -> keep the v2 surface small,
  explicit, and covered by schema tests.
- Atomic rename behaves differently on Windows, symlinks, or cross-device paths
  -> resolve symlink targets deliberately, retry rename on `EPERM`/`EACCES`, and
  fall back only with explicit metadata when atomicity cannot be guaranteed.
- Additional pre-write checks reject legitimate concurrent workflows -> return
  structured stale-read errors with re-read instructions, and keep checks scoped
  to managed text mutations.
- Patch output becomes too large for the transcript -> include concise summaries
  and diff previews, with full diff metadata available for renderers.
- Tool implementations diverge -> route `edit_text`, `write_file`, and
  `apply_patch` through the same mutation engine and share tests for encoding,
  stale checks, and diff metadata.
- Multi-file patch partially commits after a late platform error -> preflight all
  operations first, use backups for destructive steps, and report committed and
  failed operations separately if the late error cannot be prevented.
- Path policy accidentally blocks legitimate generated-file edits -> surface
  ignore/sensitive-file policy decisions in structured metadata so approval
  rules can distinguish warning, requires-approval, and hard-deny cases; in this
  change, requires-approval is reported rather than interactively resolved.

## Migration Plan

1. Add the shared mutation engine behind the existing tools without changing
   behavior.
2. Add v2 tool adapters for `read_file`, `edit_text`, `write_file`, and
   `apply_patch` using the shared engine.
3. Update tool docs and registration order so `edit_text` is preferred for
   small exact edits, `apply_patch` is used for complex or multi-file edits, and
   `write_file` covers explicit whole-file write cases.
4. Remove old `read` and `modify` from model tool registration and tool docs.
5. Add strict schema coverage for the v2 model-facing tools.
6. Expand regression tests for Windows encodings, line endings, stale/hash
   checks, partial snippets, patch failures, and schema stability.

Rollback is to revert the model tool registration back to the previous file
tools and restore the old tool docs. If the shared engine itself regresses,
restore the previous `builtin.py` edit/write paths before release.

## Resolved Questions

- Approval scope: this change implements hook points and structured metadata
  only. Full interactive approval, tool interruption, and approval UI are left
  for a later UI/runtime change.
