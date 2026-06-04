# Design

## Interaction Ownership

Modern UI will treat audit and ask-user-question surfaces as modal workflow
owners even though they are rendered in the bottom interaction sheet. While such
a surface is active:

- prompt input is disabled or prevented from taking focus;
- app-level `Esc` resolves the active interaction before normal interrupt or
  draft-clear handling;
- focus is restored to the active interaction if it drifts;
- completion restores prompt focus.

This keeps the non-modal visual design while preventing the prompt from stealing
the decision flow.

## Diff Ordering

Write/Update tool outputs will be routed through a single transcript path:

1. receive tool output;
2. parse diff metadata;
3. remove or avoid mounting the compact tool output row;
4. mount the diff block at the current stream position;
5. update status.

Diff block rendering must not depend on a later cleanup pass that can reorder
content.

## Scroll Containment

Diff blocks should have stable height constraints and internal overflow where
needed. Transcript wheel/scroll commands should continue to target the
transcript unless an explicitly focused child widget owns scrolling.

## Composer

The composer should reserve five visible lines for the prompt by default. Longer
drafts scroll inside the prompt input instead of expanding into the transcript or
status bar.

## Markdown Density

Markdown tables and code-adjacent block spacing should be tightened at the TUI
stylesheet/widget layer. The goal is not to rewrite Markdown parsing, but to
reduce padding/margins that create large empty regions in terminal output.
