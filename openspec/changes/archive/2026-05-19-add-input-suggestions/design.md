## Context

Deepy currently has two interactive prompt surfaces:

- the default Rich/prompt-toolkit terminal UI in `src/deepy/ui/terminal.py` and
  `src/deepy/ui/prompt_input.py`
- the opt-in Textual TUI in `src/deepy/tui/app.py` and
  `src/deepy/tui/widgets.py`

Both already support slash command suggestions and file mention completion, but
neither predicts the next user prompt after an assistant response. Qwen Code's
reference implementation separates this feature into a framework-independent
follow-up controller, a suggestion generator, and UI-specific input integration.
Deepy should follow the same split while keeping Deepy-specific constraints:
fixed DeepSeek V4 Flash, thinking disabled, no Enter acceptance, and separate
usage accounting.

## Goals / Non-Goals

**Goals:**

- Provide prompt-adjacent ghost-text input suggestions in the stable terminal UI
  and the experimental Textual TUI.
- Use a shared suggestion generation and state model so both UIs behave the same
  way.
- Enable suggestions by default while allowing `/input-suggestion` to toggle the
  persisted enabled state.
- Use only `deepseek-v4-flash` with thinking disabled for suggestion calls.
- Keep suggestion usage separate from ordinary turn usage and context window
  checkpoints.
- Preserve existing Enter-to-submit behavior.

**Non-Goals:**

- User-configurable suggestion model selection.
- Enter-to-accept behavior.
- Speculative execution before the user accepts a suggestion.
- Non-interactive/headless suggestion display.
- Replacing slash command completion or file mention completion.

## Decisions

### Shared follow-up module

Create a shared Python module for input suggestions instead of embedding logic in
either UI. The module should own:

- feature state and a short display delay
- in-flight generation cancellation
- acceptance and dismissal transitions
- quality filtering
- prompt construction
- fixed side-query provider settings
- suggestion usage result data

This keeps prompt-toolkit and Textual integration thin and prevents the two UIs
from drifting.

Alternative considered: implement directly in `prompt_input.py` first and port
later. That would be faster initially, but it would make the experimental TUI an
afterthought and duplicate cancellation/filtering behavior.

### Trigger after completed eligible turns

Generate suggestions after a model turn completes successfully and the UI returns
to idle. Eligibility should require at least two assistant/model replies in the
active session. Generation should be skipped while a local command is running,
while a model turn is streaming, when pending AskUserQuestion or confirmation UI
is active, when the feature is disabled, or when the session is not interactive.

The generator should use a recent conversation window rather than the entire
session to bound latency and cost. The exact limit can be implementation-defined
but should be deterministic and covered by tests.

Alternative considered: generate after every assistant reply including the first
turn. This increases cost and tends to produce lower-quality suggestions before
there is enough interaction history.

### Fixed DeepSeek V4 Flash non-thinking side query

Suggestion generation should construct a dedicated side-query model call using
`deepseek-v4-flash` and explicit DeepSeek thinking disabled settings. It should
not inherit the active conversation model, reasoning mode, or future fast-model
settings.

Alternative considered: reuse the active model with `thinking=false`. This keeps
implementation smaller, but violates the latency/cost target and makes behavior
dependent on unrelated `/model` choices.

### Ghost text and acceptance semantics

Both UIs should display visible suggestions inside the input area when the input
buffer is empty. Tab and Right Arrow should insert the suggestion into the input
buffer without submitting. Enter should continue to mean submit the current
buffer and must not accept a visible suggestion.

For Textual, the first implementation should attempt a true in-input ghost text
rendering by customizing or wrapping the prompt input widget. If Textual's
`TextArea` makes inline rendering unreliable, the fallback should still be
prompt-area ghost styling, not the existing dropdown suggestion list.

Alternative considered: use the existing suggestion dropdown. That would be
easier but visually conflicts with the requested ghost-text behavior and with
slash/file completions.

### Separate usage accounting

Suggestion usage should be stored separately from ordinary model-turn `TokenUsage`
and should not update context window checkpoints. User-facing displays may show a
separate "Input Suggestion Usage" segment or summary, but ordinary turn usage
footers must continue to represent only the submitted turn.

Alternative considered: merge suggestion usage into session usage. That hides
the cost of default-on background calls and can corrupt context-window semantics
because suggestion calls do not represent the active conversation request.

### Simple toggle command

Add `/input-suggestion` as a no-argument toggle command. Running it flips the
persisted enabled state and prints the resulting state. Arguments should be
rejected with a concise usage message so the feature does not grow an accidental
configuration surface.

Alternative considered: `/followup` or `/input-suggestion on/off/model`. The
chosen command is more descriptive for users and intentionally avoids model
customization in this change.

## Risks / Trade-offs

- Textual inline rendering may be constrained by `TextArea` internals ->
  mitigate with a small Deepy-owned prompt widget adaptation and headless TUI
  tests that assert rendered ghost text behavior.
- Default-on background calls add cost -> mitigate with the two-reply threshold,
  quality filters, cancellation on user input, and separate usage accounting.
- Suggestion generation could race with user typing -> mitigate by aborting
  in-flight generation and clearing visible suggestions on the first user edit,
  paste, command execution, or new turn.
- Suggestion text could be low quality or disruptive -> mitigate with explicit
  generation instructions plus deterministic filters for length, formatting,
  error-like text, evaluative phrases, AI voice, and meta text.
- Additional side-query provider code could drift from main DeepSeek settings ->
  mitigate with tests that assert `deepseek-v4-flash`, thinking disabled,
  storage disabled, and usage enabled for suggestion requests.

## Migration Plan

1. Add default-enabled configuration support while preserving existing config
   files that do not have an input suggestion setting.
2. Add shared suggestion generation/state/usage modules behind the config flag.
3. Wire `/input-suggestion` into both interactive surfaces.
4. Integrate ghost text into prompt-toolkit and Textual input areas.
5. Add usage display/persistence for suggestion usage without changing context
   window checkpoints.
6. Validate with focused unit tests, Textual headless tests, existing terminal UI
   tests, linting, type checks, and OpenSpec validation.

Rollback is straightforward: disable the feature by config or remove the UI
trigger path. Persisted disabled/enabled settings are safe to ignore if a future
version does not implement the feature.

## Open Questions

None. The model, toggle command, Enter behavior, two-reply threshold, Textual
target, and usage-accounting boundary are settled for this proposal.
