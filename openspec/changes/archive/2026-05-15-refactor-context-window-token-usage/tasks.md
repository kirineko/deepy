## 1. Usage Semantics

- [x] 1.1 Add or refine helpers in `src/deepy/usage.py` to expose latest request context occupancy without double counting cache detail fields.
- [x] 1.2 Preserve cumulative Token Usage aggregation for per-turn and session reporting.
- [x] 1.3 Ensure request-level usage entries retain enough data to derive latest request Context Window values.
- [x] 1.4 Add usage normalization tests for DeepSeek-style `prompt_tokens` plus cache detail fields and SDK-style `input_tokens`/`output_tokens` payloads.

## 2. Session Context Boundary

- [x] 2.1 Keep `DeepyJsonlSession.record_usage()` preserving latest request usage entries for Context Window calculations.
- [x] 2.2 Update `ensure_context_ready()` so latest Context Window used tokens drive auto compact timing when available.
- [x] 2.3 Add or update regression tests proving a smaller latest request does not trigger auto compaction merely because legacy session pressure is high.
- [x] 2.4 Add or update tests proving latest Context Window usage at or above threshold triggers auto compaction.
- [x] 2.5 Add regression tests proving manual compaction, auto compaction, shortened history, and `/new` do not leave stale Context Window used values in the statusline.
- [x] 2.6 Ensure manual and automatic compaction summaries use the same pre-compaction Context Window used value shown in the statusline.

## 3. Terminal UI Display

- [x] 3.1 Update the bottom toolbar formatting to show Context Window and Token Usage without a separate compaction pressure label.
- [x] 3.2 Show Context Window as latest request used tokens, total configured window, remaining tokens, and percentage when latest usage is known.
- [x] 3.3 Show Context Window as unknown or estimated when latest request usage is unavailable, without falling back to cumulative Token Usage.
- [x] 3.4 Show only a `compact next` hint when latest Context Window usage reaches the configured threshold.
- [x] 3.5 Update per-turn usage footer wording so cumulative/request usage is not confused with Context Window occupancy.

## 4. Validation

- [x] 4.1 Update terminal UI tests covering short latest turns, known latest request usage, unknown latest request usage, threshold `compact next`, compact reset, and `/new` reset display.
- [x] 4.2 Update compaction tests to assert auto compact trigger behavior now follows latest Context Window used tokens and resets after compaction.
- [x] 4.3 Run the focused test suite for usage, session context, compaction, and terminal UI.
- [x] 4.4 Run the broader project test command if focused tests pass.
