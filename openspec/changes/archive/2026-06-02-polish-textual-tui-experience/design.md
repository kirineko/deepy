## Context

The previous change made Textual the future-primary UI candidate and removed
the largest maintenance gap between stable UI and TUI. The current TUI still
does not yet feel like the target product surface:

- transcript blocks use too much vertical space, repeat headings/status
  information too often, and rely on visible left rails/borders that make the
  transcript feel heavier than the content;
- Markdown itself is not yet treated as a dense reading surface: paragraphs,
  lists, code blocks, headings, and assistant text spacing need a coherent
  terminal reading rhythm instead of inheriting generic widget defaults;
- output appears static during long replies because assistant markdown updates
  and scroll movement are visually quiet;
- `/theme` only maps Deepy's `dark` / `light` values to `textual-dark` /
  `textual-light`, even though Textual ships multiple built-in themes;
- image attachments are outside the prompt text, but the composer does not yet
  give users an obvious way to remove a selected image;
- audit approvals and selection flows still use `ModalScreen`, which dims the
  conversation, steals the user's focus, and breaks the sense of continuous
  chat flow;
- sessions, skills, and reset/config screens are functional but visually heavy
  and workflow-thin: they expose raw lists or broad forms more than guided
  management experiences;
- the bottom composer is functionally correct but visually reads like a thin
  status row rather than an integrated prompt control.

Research notes:

- Textual themes are Python objects that populate CSS variables and can be
  registered/applied at runtime; Textual's documentation lists built-in themes
  including `nord`, `gruvbox`, `tokyo-night`, `textual-dark`,
  `solarized-light`, `atom-one-dark`, and `atom-one-light`.
- Textual CSS supports theme variables, `position: absolute`, `offset`, layers,
  opacity, and widget style animation. These are enough for lightweight
  overlays and subtle motion without adding dependencies.
- `ModalScreen` is intentionally modal and dims the underlying app. That is
  useful for management tasks but a poor fit for frequent in-conversation
  decisions like audit approval and AskUserQuestion.

## Goals / Non-Goals

**Goals:**

- Redesign the full transcript reading experience so Markdown output, role
  identity, left-rail treatment, block grouping, metadata, and folded details
  feel concise, high-density, and visually polished.
- Make non-interruption the default interaction rule: TUI interactions should
  preserve transcript information flow and the main conversation workflow unless
  a separate management surface is clearly the better user experience.
- Make long assistant replies and running tool calls visibly alive.
- Use Textual's native theme system more fully while preserving Deepy's stable
  `dark` / `light` configuration contract.
- Provide keyboard-first image attachment deletion from the composer.
- Replace frequent blocking modal decisions with inline transcript decision
  blocks.
- Redesign management workflows so sessions, skills, reset/config, help/status,
  and long detail views have clearer task flow, denser layout, better focus
  recovery, and a visual system consistent with the polished TUI.
- Redesign the composer into a cohesive prompt surface with integrated input,
  attachments, suggestions, busy state, and action affordances.
- Keep the change testable through headless Textual tests plus targeted manual
  smoke validation.

**Non-Goals:**

- Do not remove the stable Rich/prompt-toolkit UI.
- Do not change the default `deepy` entrypoint.
- Do not add a non-Python UI runtime or a new runtime UI dependency.
- Do not force the small number of genuinely management-heavy workflows inline.
  Skill market, broad skill management, reset/config, and long detail views may
  remain screen-based when that shape gives the user more space and clearer task
  context, but their existing UI still needs workflow and visual redesign.
- Do not make Textual theme names the shared stable UI config contract in this
  change.

## Decisions

### 1. Redesign The Transcript Reading System

Introduce a small Textual transcript presentation layer that normalizes content
into compact display models before rendering widgets. This is not just usage
folding or margin tuning; it owns the visual grammar of the conversation:

- role identity (`You`, `Deepy`, tool names, question labels) should be compact
  and low-friction, with clear state but less repeated vertical overhead;
- the current heavy left stripe/rail treatment should be replaced or softened
  with a lighter semantic marker, active-state accent, or compact gutter that
  improves scanning without dominating the transcript;
- Markdown paragraphs, headings, lists, code blocks, tables, and inline
  emphasis should use explicit dense spacing and readable wrapping rules
  instead of default large blocks;
- assistant replies should read like a compact document stream, not a set of
  separated cards;
- user prompts should be visually distinct but should not consume a large block
  when the prompt is short;
- usage moves to a compact turn footer or status summary instead of a full block
  after every turn when possible;
- reasoning/tool metadata is folded by default when it is low value;
- tool blocks show state, tool name, target, and elapsed/streaming indicators
  before showing full details;
- errors and approval/question blocks remain visually distinct but avoid large
  borders and excessive vertical padding.

Alternative considered: only tune CSS margins. That helps the screenshot, but
does not solve generic Markdown spacing, heavy identity/rail treatment, repeated
usage blocks, noisy metadata, or long-output folding.

### 2. Map Deepy Themes To Curated Textual Themes

Keep `Settings.ui.theme` as `dark` or `light` for project compatibility. Add a
TUI-only mapping:

- `dark` -> `atom-one-dark`
- `light` -> `atom-one-light`

The TUI may expose Textual theme names in a picker or preview, but saving a
plain `/theme dark` or `/theme light` keeps the shared config value stable. If
explicit Textual theme selection is added in this change, persist it under a new
TUI-specific field such as `ui.textual_theme`, not by overloading `ui.theme`.

Alternative considered: persist raw Textual theme names in `ui.theme`. That
would force stable UI to understand Textual-only values and would break the
current cross-surface `dark` / `light` contract.

### 3. Make Inline Flow The Default Interaction Pattern

Every TUI interaction should first be evaluated against the main-flow rule:
does it need to interrupt the transcript, or can it live inside the transcript,
composer, side surface, or an inline command surface?

Default placements:

- conversation decisions: inline transcript blocks;
- short choices and command arguments: inline choice blocks or composer-adjacent
  command surfaces;
- status/help summaries: inline or side/detail surfaces that preserve context
  when practical;
- long management tasks: screen/full-surface only when the task benefits from
  extra space and focused mode.

This rule applies to existing UI too. Keeping a screen is not approval to keep
the current screen design; every retained screen must still get a workflow and
visual redesign.

Alternative considered: only replace audit and AskUserQuestion modals. That
solves the most obvious interruption but leaves other command choices and
management surfaces inconsistent with the target TUI experience.

### 4. Replace Frequent Decision Modals With Inline Decision Blocks

Add reusable inline decision widgets mounted in the transcript:

- `AuditDecisionBlock` for audit approval, with summary, preview toggle,
  Approve/Reject options, and keyboard focus;
- `QuestionDecisionBlock` for AskUserQuestion, supporting single-select,
  multi-select, custom answer, cancel, and same-session continuation;
- a generic `InlineChoiceBlock` for stop/theme/model steps where inline flow is
  more natural than a modal.

These blocks emit messages to the app, just like current question widgets. They
should retain transcript position, show a completed/cancelled state after
submission, and avoid pushing a `ModalScreen` for frequent decisions.

Alternative considered: restyle existing modals. That reduces visual roughness
but does not address the interruption of the conversation flow.

### 5. Redesign Management Workflows, Not Just Their Chrome

Not all screens should be inline. Skill market, broad skills management,
reset/config, and long help/status/detail views can still use separate surfaces
when they are intentional management tasks. They should still be redesigned as
workflow surfaces, not just restyled containers:

- sessions should prefer a non-disruptive inline or side-surface resume flow
  when practical; if a screen is used, it should prioritize resume decision
  quality: searchable recent list, compact metadata, clear active/current
  marker, readable preview, cancel path, and return-to-conversation focus;
- skills should separate market and installed work clearly, show install/update/
  uninstall/use affordances without requiring memorized hotkeys, and keep skill
  detail readable without dumping long bodies into cramped list rows;
- reset/config should become a guided form or staged flow with provider-aware
  model/thinking choices, validation feedback near the field, and clear save/
  cancel outcomes;
- help/status/detail views should use compact sections, tabs or segmented
  groups where useful, and dense command strips instead of persistent Footer
  chrome;
- all management views should use fewer round borders, denser title/action
  rows, theme-aware surfaces using `$surface`, `$panel`, `$boost`, and muted
  text, plus predictable focus restoration when closed.

Alternative considered: only remove Footer and round borders. That improves the
surface look but leaves sessions/skills/reset as awkward workflows and leaves
the app with inconsistent interruption patterns.

### 6. Use Motion As State Feedback, Not Decoration

Use Textual's existing animation/style tools for subtle state changes:

- streaming assistant block shows a cursor/pulse or low-frequency activity mark;
- busy status line animates a small token/progress indicator;
- newly mounted tool blocks fade or slide in through opacity/offset animation
  when supported by the current Textual version;
- when the user is scrolled away from bottom, the new-output indicator pulses
  until acknowledged;
- all animation should be disabled or reduced in tests and must not corrupt
  scroll position.

Alternative considered: add large spinners or progress bars. That consumes
space and can distract from transcript content.

### 7. Redesign Composer As One Integrated Control

The composer should become a compact bottom surface with internal regions:

- prompt text area with a stronger active affordance;
- attachment row with removable chips such as `[图片1] x`;
- suggestion overlay visually attached to the composer;
- right-side or bottom command strip for current state (`Enter send`,
  `Ctrl+J newline`, `Tab accept`, `Esc clear/interrupt`);
- busy/disabled state that still allows navigation and interrupt.

The composer should remain Textual-native: no prompt-text replacement tokens
for images, no custom character substitution for CJK/emoji input, and no hidden
dependency on prompt-toolkit.

## Risks / Trade-offs

- [Risk] Denser transcript rendering can hide important details or make
  Markdown harder to read. -> Define explicit transcript display models,
  Markdown spacing rules, deterministic fold/expand controls, and tests for
  each content type.
- [Risk] Inline approval blocks can conflict with live model streaming focus. ->
  Pause the current decision boundary until the user answers, focus the decision
  block, and keep the prompt disabled or clearly secondary while a decision is
  pending.
- [Risk] More theme options can confuse users. -> Keep persisted stable values
  as `dark` / `light` and treat Textual theme names as TUI-specific aliases or
  previews.
- [Risk] Animation can make tests flaky. -> Use injectable animation policy or
  deterministic reduced-motion mode for tests.
- [Risk] Attachment deletion shortcuts can collide with prompt editing. -> Keep
  deletion explicit through focused attachment chips and a documented shortcut,
  not through hidden prompt-text parsing.

## Migration Plan

1. Add theme mapping and tests without changing stable UI behavior.
2. Extract transcript display models, Markdown presentation rules, and updated
   block widgets.
3. Add the integrated composer layout and attachment deletion.
4. Add live activity indicators and reduced-motion test mode.
5. Replace audit, AskUserQuestion, and other frequent short-choice modals with
   inline or composer-adjacent interaction surfaces.
6. Redesign retained management screens and verify their workflow behavior.
7. Update documentation and run full validation.

Rollback is straightforward because the default stable UI remains unchanged. If
the TUI polish regresses, revert the TUI widgets/screens/app changes while
keeping the previous opt-in TUI entrypoint.

## Open Questions

- Should explicit Textual theme selection be shipped in this change as
  `ui.textual_theme`, or should this change only map `dark` / `light` to curated
  built-ins and leave free-form theme selection for later?
- Should attachment deletion support mouse clicks in addition to keyboard focus
  and Delete/Backspace?
