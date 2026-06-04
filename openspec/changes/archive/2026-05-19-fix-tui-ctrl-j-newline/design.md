## Context

Deepy's stable prompt-toolkit UI already defines Ctrl+J as the cross-platform multiline shortcut, with Enter reserved for submission. The experimental Textual TUI still binds and documents Shift+Enter for newline insertion in the main prompt and custom question text area, and the archived experimental TUI specification preserved that older behavior.

This change is a small behavioral alignment rather than a new UI architecture. The important constraint is to update the full contract together: runtime key bindings, help text, tests, docs, and the Textual TUI specification.

## Goals / Non-Goals

**Goals:**

- Make Ctrl+J insert newlines in the experimental Textual TUI prompt.
- Keep Enter as the submit key.
- Apply the same newline shortcut to custom question text entry so multiline input behaves consistently.
- Remove TUI-facing Shift+Enter newline guidance from help, startup copy, docs, and tests.
- Keep the stable prompt-toolkit UI behavior unchanged.

**Non-Goals:**

- Do not make the Textual TUI the default interface.
- Do not add a configurable newline shortcut.
- Do not change prompt history, slash commands, file mention suggestions, Ctrl+D exit confirmation, or transcript rendering.
- Do not reintroduce terminal-specific Shift+Enter compatibility paths.

## Decisions

1. Use Ctrl+J as the single TUI newline shortcut.

   The stable terminal UI already uses Ctrl+J, and previous Windows Terminal testing showed Ctrl+J was the reliable shortcut. Keeping Shift+Enter in the Textual path creates inconsistent behavior for users moving between `deepy` and `deepy tui`.

   Alternative considered: support both Ctrl+J and Shift+Enter. That would reduce immediate surprise for anyone using the experimental TUI today, but it preserves two mental models and weakens the stable UI alignment this bugfix is meant to restore.

2. Align both prompt and custom question text areas.

   The TUI has separate `TextArea` subclasses for normal prompts and custom AskUserQuestion text. Both accept multiline text, so both should use the same newline shortcut.

   Alternative considered: update only the main prompt. That leaves a smaller patch but creates a hidden inconsistency in question flows.

3. Treat docs and specs as part of the fix.

   The current docs explicitly describe Shift+Enter as a deliberate TUI design difference, and the `experimental-textual-tui` spec requires Shift+Enter. The code fix should update those sources so future tests and proposals do not preserve the regression.

   Alternative considered: change only code and tests. That would pass local behavior checks but leave OpenSpec and user docs contradicting the implementation.

## Risks / Trade-offs

- [Risk] Textual's key name for Ctrl+J may differ from prompt-toolkit's `c-j`. -> Mitigation: add or update a focused Textual pilot test that presses Ctrl+J and verifies a newline is inserted without submission.
- [Risk] Users of the experimental TUI who learned Shift+Enter may need to adapt. -> Mitigation: update startup/help copy to advertise Ctrl+J clearly.
- [Risk] Shift+Enter references may remain in archived historical OpenSpec changes. -> Mitigation: update active specs and current docs/tests only; archived changes remain historical records.
