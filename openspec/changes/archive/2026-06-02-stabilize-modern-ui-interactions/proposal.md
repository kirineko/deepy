# Stabilize Modern UI Interactions

## Summary

Fix Modern UI interaction deadlocks and layout regressions that interrupt the
main transcript flow. This change keeps the current Modern UI direction, but
makes audit and ask-user-question decisions resilient, restores diff ordering
and scrolling, improves table density, and gives the composer enough vertical
space for real prompts.

## Motivation

Modern UI currently has several user-facing failure modes:

- Audit and ask-user-question sheets can lose keyboard ownership when the prompt
  regains focus, leaving the user unable to approve, reject, or cancel.
- Diff output can appear after unrelated output or leave an extra output row in
  the wrong place.
- Streaming assistant text can appear before a later `Write` or `Update` diff
  in the same turn, making the transcript read as if the result explanation
  happened before the file change preview.
- Markdown table output is too sparse for terminal transcript reading.
- The prompt composer is constrained to one visible line, making multi-line
  prompts feel cramped.
- Large or malformed diff blocks can break transcript scrolling, causing wheel
  input to affect prompt history instead of conversation content.

These are all Modern UI interaction/presentation issues and should be fixed
together before deeper audit architecture work.

## Scope

- Modern UI interaction sheet focus ownership.
- Audit and ask-user-question keyboard behavior.
- Diff block ordering and scroll containment.
- Markdown table density in transcript output.
- Prompt composer default height and internal scrolling.
- Focus and wheel routing between transcript, interaction sheet, and composer.

## Out of Scope

- Changing Classic UI behavior.
- Changing audit policy semantics.
- Preflight file mutation diff approval. That is handled by
  `preflight-file-mutation-approval`.
- Changing model-facing tool schemas.

## Success Criteria

- Pending audit and ask-user-question flows can always be completed or cancelled
  with keyboard controls even if the user attempts to focus the prompt.
- Write/Update diff blocks replace the corresponding compact tool output in the
  transcript and maintain chronological order.
- Write/Update diff blocks remain visually before the assistant text that
  describes the same file mutation, even when assistant text deltas arrive
  before the tool output event.
- Tables render more tightly without losing readability.
- The composer shows five lines by default and supports scrolling longer drafts.
- Large diff blocks do not break transcript scroll navigation.
