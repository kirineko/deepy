## Context

Deepy currently has two interactive terminal surfaces:

- Stable UI: Rich + prompt-toolkit, launched by `deepy`.
- Experimental TUI: Textual, launched by `deepy tui`.

The stable UI has the strongest everyday UX and input reliability today, but it
is increasingly difficult to extend into an app-like terminal interface. The
experimental TUI has a better long-term framework foundation, but its current
visual design, interaction model, and composer implementation are not good
enough to become the default surface.

The local spike against Textual 8.2.6 showed that Textual already provides
useful native primitives for the desired direction:

- `TextArea` supports compact mode, soft wrapping, native suggestion state,
  cursor APIs, selection, and headless testing.
- `Input` also supports compact mode and built-in suggestion styling.
- Textual CSS supports border removal, padding control, docked regions,
  bounded heights, layers, and overlay-friendly layout.
- A compact shell can keep the composer at one row while idle and grow it as
  multiline input expands.

The same spike also showed that the current Deepy TUI composer is too coupled:
image labels, ghost suggestions, slash/file suggestions, and terminal-protocol
normalization all touch the prompt text or prompt-adjacent fixed rows. The
future primary UI needs a cleaner composer boundary before visual work can
safely continue.

Hermes provides two useful lessons but not a direct technology target:

- Its command metadata is centralized and reused by help, autocomplete, and
  platform surfaces.
- Its modern TUI is React/Ink/Node-based, which is not appropriate for Deepy's
  Python-only packaging target in this change.

## Goals / Non-Goals

**Goals:**

- Make Textual the primary investment surface for future Deepy terminal UX.
- Rebuild the Textual composer around Textual-native input behavior.
- Preserve stable UI command and prompt semantics in the redesigned Textual TUI.
- Improve visual density so Textual can feel as direct as the stable UI while
  gaining app-shell capabilities.
- Introduce shared command metadata so future UI changes do not require parallel
  command definitions.
- Keep the migration staged: redesigned Textual first, default-entrypoint switch
  and stable UI removal later.

**Non-Goals:**

- Do not delete the stable Rich/prompt-toolkit UI in this change.
- Do not make `deepy` launch Textual by default in this change.
- Do not add Node.js, React, Ink, or Hermes TUI runtime dependencies.
- Do not copy Hermes source code or adopt its frontend architecture.
- Do not preserve the current Textual visual layout if it conflicts with the
  compact stable-UX goal.

## Decisions

### 1. Textual-first rewrite, not current-TUI promotion

The implementation should not simply polish the current TUI and make it the
primary surface. It should refactor the TUI around a smaller set of Textual
components:

- app shell
- transcript view
- composer
- command/suggestion overlays
- status line
- modal/picker screens
- runtime event adapter

Alternative considered: keep stable UI as the only serious surface and remove
the TUI. This avoids TUI bugs short term, but it leaves Deepy with a UI base
that is poorly suited to overlays, panels, and richer interaction.

### 2. Prompt text must contain only user-authored text

The Textual composer should not encode UI state in the input buffer. Image
attachments, generated suggestions, slash suggestions, and file mention
candidates are UI state and should be rendered adjacent to or over the input.

This means replacing the current image-label-in-prompt behavior in the Textual
surface with an attachment strip or equivalent composer state. Submission still
passes the same `PromptImageAttachment` data to the runner.

Alternative considered: keep `[图片1]` labels and make deletion smarter. That
keeps compatibility with current tests but continues to mix editable text with
structured prompt state and is the source of several experience problems.

### 3. Use native Textual suggestion support for generated prompt suggestions

Textual `TextArea` has a native `suggestion` property. The redesigned composer
should prefer it over a separate ghost `Label` row. Slash and file mention
suggestions remain distinct selectable overlays because they are command/file
completion lists, not a single auto-suggestion.

Alternative considered: keep the existing `#prompt-ghost` row. It works in
tests, but it consumes layout space, can overlap conceptually with other
suggestion surfaces, and does not use the widget's own suggestion rendering.

### 4. Keep terminal-protocol handling invisible and bounded

The current TUI decodes Kitty keyboard protocol sequences that can leak into
the text buffer in some terminals. The redesigned input boundary may retain a
defensive normalizer, but it must not be the normal display path and must be
covered by focused tests. The UX target is that users never see replacement
sequences or broken intermediate text.

Alternative considered: remove all normalization. The spike proves Textual
headless CJK input works, but the existing regression tests show real terminal
sequence leakage has occurred, so removing the guard without live terminal
evidence would be risky.

### 5. Compact shell by default

The Textual app should look closer to the stable UI than to a dashboard. The
default layout should avoid a persistent heavy header, broad sidebar, and thick
per-message cards. It should favor:

- transcript as the main scrollback
- one-line status/footer
- bottom composer that grows only as needed
- command/file overlays on layers
- modal screens for explicit auxiliary workflows

Alternative considered: retain the existing Header/Footer/side-panel layout.
That preserves current code but does not meet the user's visual or interaction
goals.

### 6. Shared command metadata before more command UX

Deepy should evolve `src/deepy/ui/slash_commands.py` into shared command
metadata that can drive Textual slash suggestions, categorized help, command
palette entries, and future stable UI retirement. The TUI should not keep an
independent static command list once the shared registry exists.

Alternative considered: continue aligning separate stable/TUI command lists.
That preserves local simplicity but is exactly the parity burden this migration
is meant to reduce.

## Risks / Trade-offs

- [Risk] Textual input has terminal-specific behavior not reproduced by
  headless tests. -> Mitigation: keep focused tests for Kitty sequence handling,
  CJK input, emoji/API insertion, multiline input, suggestions, and attachment
  submission; add manual terminal validation notes before any default switch.
- [Risk] Replacing image labels changes user-visible prompt editing behavior. ->
  Mitigation: keep runner payload behavior unchanged and document the Textual
  composer attachment strip as the new TUI behavior.
- [Risk] Large TUI refactor can regress existing supported flows. -> Mitigation:
  migrate in phases and keep focused tests for prompt, slash, file mention,
  AskUserQuestion, approval, skills, status, sessions, background tasks, and
  exit summary.
- [Risk] Command registry refactor can couple UI and handler behavior too
  tightly. -> Mitigation: keep metadata and execution separated: registry
  describes commands, handlers execute commands.
- [Risk] Stable UI remains during this change, so maintenance cost is not
  immediately eliminated. -> Mitigation: treat this as a prerequisite change;
  future default switch and stable UI retirement should be separate OpenSpec
  changes after Textual quality gates pass.

## Migration Plan

1. Refactor Textual composer and shell structure while keeping `deepy tui` as
   the entrypoint.
2. Move command metadata toward a shared registry and route Textual help and
   suggestions through it.
3. Rework visual layout into the compact shell and migrate existing TUI flows to
   the new components.
4. Run focused TUI and shared UI tests, then the standard quality gates.
5. Update documentation to describe Textual as the future primary UI candidate
   while preserving the current entrypoints.
6. Leave default-entrypoint migration and stable UI removal for a later change.

## Open Questions

- Which real terminals should be treated as mandatory manual validation targets
  before Textual can become the default UI?
- Should busy-mode queue/steer behavior be implemented in this change, or only
  prepared by the command/composer architecture?
- Should external editor prompt editing be included in this change, or captured
  as a future Hermes-inspired enhancement after the composer refactor lands?
