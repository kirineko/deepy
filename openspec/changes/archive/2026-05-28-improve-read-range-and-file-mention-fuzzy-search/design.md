## Context

Deepy already exposes `Read` as a v3 model-facing file tool with `range` encoded
as a string such as `"20-80"`. The runtime parser accepts that string form, but
tool argument parsing happens before runtime parsing, so JSON-like inputs such
as `"range": 80-120` fail as malformed JSON and are surfaced as retryable tool
attempts. The generic repair layer currently fixes only a small set of safe JSON
mistakes.

Deepy's stable prompt already has in-process `@` file mention completion with
fuzzy ranking. The ranking can match nested relative paths, but short fragments
without `/` currently use only top-level project candidates to avoid expensive
or noisy deep searches.

The experimental Textual TUI has its own prompt widget and suggestion panel.
It already uses the shared file mention discovery and ranking helpers, but its
candidate selection still uses top-level candidates for every fragment without
`/`. Its prompt editing is Textual-native, so stable prompt-toolkit editing
shortcuts do not automatically carry over.

## Goals / Non-Goals

**Goals:**

- Recover the common `Read` line-range shape where a model emits an unquoted
  inclusive line range, while keeping the canonical model-facing schema simple.
- Make the model-facing `Read` description less likely to produce the malformed
  range shape in the first place.
- Allow `@` mentions with short non-empty fragments to find nested files and
  directories through the existing fuzzy ranking and ignore rules in both
  terminal prompt implementations.
- Add a Textual prompt shortcut that clears the current draft when the user
  presses Esc and then a deletion key.
- Preserve low-noise bare `@` behavior and existing completion precedence with
  slash commands and input suggestions.

**Non-Goals:**

- Introduce a new `Read` schema variant for arrays, objects, or arithmetic
  range expressions.
- Repair arbitrary malformed JSON or evaluate general expressions in tool
  arguments.
- Add external search binaries or new dependencies for file mention discovery.
- Replace the existing file mention ranking algorithm.

## Decisions

1. Keep `range` as a string in the public `Read` schema.

   The current `"20-80"` shape is compact and already supported by the runtime
   parser. Expanding the schema would increase model-facing ambiguity for a
   single observed failure mode. The repair path should normalize the common
   malformed shape into the canonical string form instead.

2. Add a narrow repair operation for unquoted `Read` range values.

   The repair should be limited to object fields named `range` whose value is a
   simple positive integer pair separated by `-`, for example `80-120`. The
   repaired payload must still parse as JSON and validate against the tool
   schema before execution. Unsafe inputs, unrelated arithmetic, and malformed
   mutation content should continue to return retryable invalid-argument
   results.

3. Improve `Read` tool guidance with concrete examples.

   The description should explicitly show `"range": "80-120"` for single-file
   reads and the same string form inside `files=[...]` for batch reads. This is
   cheaper than relying entirely on recovery and should reduce retryable noise
   in normal turns.

4. Change file mention candidate selection, not fuzzy ranking.

   The current ranking already captures the expected matching behavior once a
   candidate is available. For short non-empty fragments, the completer should
   draw from the bounded deep-path cache, then let existing ranking and limits
   decide which paths are shown. Bare `@` should continue to use only top-level
   candidates. The same candidate-selection rule should be applied to the
   Textual `PromptPanel`.

5. Keep discovery bounded and in-process.

   The existing limit, cache interval, ignored-name filtering, symlink skipping,
   and project-root containment checks should remain the safety boundary for
   short-fragment deep search.

6. Implement Esc-then-delete as explicit Textual prompt state.

   The Textual prompt should record a two-second deadline when Esc is pressed
   while the prompt is focused. If the next deletion action is Delete or
   Backspace before that deadline and the prompt contains text, it should clear
   the entire draft and refresh suggestion state. Expired shortcuts and other
   editing actions should keep normal TextArea behavior. This keeps single
   Delete and single Backspace unchanged.

## Risks / Trade-offs

- Short-fragment deep search may surface more candidates than users expect.
  Mitigation: keep bare `@` top-level only, keep existing result limits, and
  preserve basename-prefix ranking ahead of weaker fuzzy matches.
- Narrow argument repair could hide a model prompt issue if over-broad.
  Mitigation: repair only simple `range` fields and require schema validation
  after repair.
- Batch `Read` repair may require careful parsing because malformed range values
  can appear inside nested `files` entries. Mitigation: implement repair at the
  raw argument string layer before JSON parsing, but keep the pattern field-name
  specific and test both single and batch inputs.
- A one-letter query can match many generated or dependency files if ignore rules
  regress. Mitigation: add regression tests that ignored directories remain
  excluded from short-fragment fuzzy results.
- Esc as a global interrupt key could conflict with prompt editing. Mitigation:
  scope the clear-draft marker to `PromptTextArea`; it only changes behavior
  when a deletion key follows within two seconds while the prompt is focused.
