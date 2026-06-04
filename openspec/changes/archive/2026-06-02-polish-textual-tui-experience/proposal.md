## Why

The redesigned Textual TUI is now a viable future-primary UI candidate, but the
current experience still feels too sparse, too modal, and too static during long
assistant replies. This change raises the TUI quality bar before any default UI
migration by tightening information density, adopting Textual-native themes,
making attachments manageable, and moving blocking decisions into the
conversation flow.

## What Changes

- Redesign the entire transcript experience to be concise, high-density, and
  visually polished: Markdown rendering, paragraph/list/code spacing, turn
  identity (`You` / `Deepy`), left rail or stripe treatment, semantic grouping,
  block spacing, metadata placement, and folding behavior all become part of one
  coherent transcript design.
- Add a Textual theme bridge so Deepy's saved `dark` and `light` settings map to
  selected Textual built-in themes instead of only `textual-dark` /
  `textual-light`.
- Select two built-in Textual themes as Deepy's curated dark/light TUI defaults:
  `atom-one-dark` for dark and `atom-one-light` for light, while still preserving
  the stable UI's `dark` / `light` config contract.
- Add image attachment management in the composer, including visible attachment
  chips/list items and keyboard deletion before submission.
- Reduce heavy borders and persistent line chrome; prefer theme contrast,
  spacing, lightweight separators, active state, and semantic color.
- Add subtle live motion and activity affordances during long model turns so the
  TUI visibly remains alive: streaming cursor/status pulse, live assistant block
  activity, running tool state, and animated new-output indicator.
- Establish a default interaction principle for every TUI surface: do not
  interrupt the transcript information flow or the main conversation workflow
  unless the task genuinely requires a separate management surface.
- Replace blocking modal approval/question flows with inline transcript decision
  blocks for audit approvals and AskUserQuestion, preserving keyboard-first
  interaction without interrupting the information flow.
- Redesign the bottom composer into an integrated prompt surface with prompt
  input, attachment state, suggestions, busy state, and action hints presented
  as one cohesive control.
- Redesign management surfaces such as sessions, skills, reset/config,
  help/status, and long detail views according to their workflows. A small
  number of surfaces, such as the skill market, may use a separate screen when
  that is the clearest task shape, but existing screen UI still needs a full UX
  and visual redesign rather than minor restyling.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `experimental-textual-tui`: transcript experience redesign, Textual theme
  mapping, attachment deletion, live activity affordances, inline audit/question
  decisions, redesigned composer behavior, and workflow-specific management
  views.
- `terminal-ui`: stable `dark` / `light` theme configuration remains the shared
  user-facing contract while Textual may map those values to richer built-in
  themes internally.
- `user-documentation`: document the curated TUI themes, inline decision model,
  attachment deletion, live activity behavior, and updated composer model.

## Impact

- Affected code: `src/deepy/tui/app.py`, `src/deepy/tui/widgets.py`,
  `src/deepy/tui/screens.py`, `src/deepy/tui/commands.py`,
  `src/deepy/tui/diff.py`, `src/deepy/config/settings.py`,
  `src/deepy/ui/styles.py`, and focused tests under `tests/test_tui_app.py`.
- Existing stable UI behavior and the default `deepy` entrypoint remain
  unchanged.
- No new runtime dependency is expected. The design should use Textual features
  already available in the locked dependency set: built-in themes, CSS variables,
  layers, absolute positioning, opacity/offset animation, and Textual widgets.
- The change is UI-behavioral and requires OpenSpec deltas plus focused Textual
  headless tests and visual/manual smoke validation, including management-view
  flows.
