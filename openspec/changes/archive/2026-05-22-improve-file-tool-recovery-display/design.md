## Context

Deepy already has a v2 file mutation surface with `read_file`, `edit_text`,
`write_file`, and structured-operation `apply_patch`. Existing-file replacement
is intentionally protected by `overwrite` plus a freshness token such as
`snapshot_id` or `content_hash`, and mutation results carry structured error
metadata. The remaining UX problem is earlier in the flow: malformed but
recoverable function-tool arguments can fail before the tool reaches the managed
mutation engine. A common example is an unquoted snapshot id such as
`"snapshot_id":snapshot_6`.

The current behavior is safe, but noisy. `_tool_args()` returns
`invalid_arguments`; stable terminal rendering shows a normal failed tool output;
and the model often follows with a successful retry. From the user's point of
view, the edit eventually succeeds but the transcript contains a prominent
failure and may display large raw write arguments.

## Goals / Non-Goals

**Goals:**

- Reduce avoidable file-tool argument failures for high-confidence malformed
  argument patterns.
- Keep every repair schema-validated and deterministic before any file side
  effect is possible.
- Add a numeric freshness token to reduce model quoting mistakes while
  preserving existing `snapshot_id` and content-hash contracts.
- Distinguish retryable/recoverable argument failures from real mutation
  failures in structured metadata and UI rendering.
- Prevent malformed write/patch argument text from dumping large file content
  into stable terminal or TUI transcripts.
- Allow the experimental TUI to fold a recovered malformed attempt into the
  later successful tool block without altering persisted session history.

**Non-Goals:**

- No automatic repair for ambiguous or semantically risky write content,
  commands, old/new replacement text, or patch operation bodies.
- No bypass of overwrite, freshness-token, stale-snapshot, path-policy,
  unsupported-target, approval, or guardrail failures.
- No deletion or mutation of JSONL session history to hide failed tool calls.
- No new external dependency or provider-specific tool protocol.
- No broad fuzzy matching for file edits.

## Decisions

### 1. Add a tiny argument repair pass after JSON parse failure

`_tool_args()` should try a conservative repair only after normal JSON parsing
fails. The repair pass should be tool-aware and limited to patterns that are
syntactically wrong but semantically obvious:

- unquoted `snapshot_<number>` values for `snapshot_id`
- unquoted `snippet_<number>` values for `snippet_id`
- Python-style `None`, `True`, and `False` tokens in otherwise JSON-like input
- trailing commas before `}` or `]`

After repair, the parsed object must still be a JSON object and must pass the
same schema/field validation used by the tool invocation path. If any repair is
not high-confidence, Deepy should return the existing invalid-arguments result
with additional metadata identifying the failure as retryable.

Alternative considered: use JSON5 or a permissive parser. That would repair more
inputs but makes side-effecting tool arguments less predictable and expands the
accepted protocol beyond the model-facing schema.

### 2. Keep repair out of content-bearing fields

Repair should not rewrite string delimiters, escape sequences, or braces inside
`content`, `old_string`, `new_string`, `old_text`, `new_text`, `anchor`, shell
commands, or patch operation bodies. Those values can contain arbitrary code and
prose; guessing there is unsafe and hard to test.

Alternative considered: call a model or heuristic fixer for malformed tool
arguments. That creates a second unreliable agentic layer around file writes and
can transform user code before safety checks see it.

### 3. Introduce a numeric snapshot token

`read_file` should continue returning `snapshot_id` and `content_hash`, and also
return a numeric `snapshot_token` that represents the same managed snapshot. File
replacement paths should accept either:

- existing string `snapshot_id`
- existing `expected_hash` / `content_hash`
- numeric `snapshot_token`

The token is session-local and runtime-local, just like the current snapshot id.
It is not a cross-session durable capability. The result metadata should make
that clear enough for model guidance and tests.

Alternative considered: change `snapshot_id` to a pure number. That would be a
breaking tool-surface change and would invalidate existing prompt guidance and
tests.

### 4. Add recoverability metadata

Invalid argument results should include stable metadata such as:

- `error_code: "invalid_arguments"`
- `retryable: true`
- `recoverable: true` when Deepy knows the model can safely retry
- `repairAttempted: true/false`
- `repairApplied: true/false`
- `recovery` with a concise model-facing instruction

Successful repaired calls should include metadata identifying that argument
repair was applied. This makes telemetry, debugging, and UI folding possible
without changing the visible tool result contract for ordinary successful
mutations.

### 5. Treat UI rendering as a first-class recovery surface

Stable terminal and TUI rendering should never display large raw malformed
arguments for file tools. If argument parsing fails, the renderer should extract
only safe summary fields where possible, such as `file_path`, operation count,
or likely target paths, and show a bounded malformed-arguments summary.

The stable terminal should render retryable invalid-argument failures with a
quieter warning-like status. The experimental TUI may additionally fold a later
successful same-tool/same-target call into the earlier retryable block, while
keeping the persisted session events unchanged.

Alternative considered: hide recoverable failures entirely. That makes debugging
hard and can misrepresent what happened during replay. Folding in the TUI is a
presentation optimization, not history mutation.

## Risks / Trade-offs

- Repair accepts something the model did not literally send -> keep the repair
  grammar tiny, schema-validate after repair, and record repair metadata.
- Numeric snapshot tokens may look durable -> document and test that they are
  runtime-local freshness tokens, not persistent file handles.
- UI folding could hide useful debugging context -> keep expanded details
  available in TUI and keep stable terminal behavior as summarized status, not
  invisible suppression.
- More status vocabulary may complicate rendering -> map recoverable argument
  failures to one shared retryable state across stable and TUI surfaces.

## Migration Plan

1. Add snapshot-token metadata to `FileState` snapshots and `read_file` output
   while preserving all existing snapshot id/hash fields.
2. Extend `write_file` and `apply_patch` `replace_file` schemas and runtime
   validation to accept `snapshot_token`.
3. Add the conservative argument repair pass and metadata in
   `src/deepy/tools/agents.py`.
4. Update tool docs and model guidance for numeric freshness tokens and
   recoverable invalid-argument failures.
5. Update shared message-view parsing and stable terminal rendering to summarize
   malformed file-tool parameters safely and render retryable failures quietly.
6. Update experimental TUI tool blocks to show retryable state and fold recovered
   malformed attempts when the later success clearly matches.
7. Add focused tests for tool repair, safety preservation, rendering summaries,
   retryable status text, TUI folding, and session replay.
