## 1. Baseline And Spike Verification

- [x] 1.1 Record the current Textual version and available native `TextArea`/`Input` capabilities used by this change.
- [x] 1.2 Add or update focused tests for Textual compact composer geometry, including idle one-line height and bounded multiline growth.
- [x] 1.3 Add or update focused tests for CJK input, wide/emoji text preservation, Ctrl+J newline insertion, Enter submission, and defensive keyboard-protocol normalization.
- [x] 1.4 Identify current TUI tests that assume image attachment labels are inserted into prompt text and mark the intended replacement behavior.

## 2. Shared Command Metadata

- [x] 2.1 Refactor shared slash command definitions into a command metadata registry with name, label, description, category, aliases, and surface availability.
- [x] 2.2 Update stable slash completion helpers to read from the shared metadata without changing stable UI behavior.
- [x] 2.3 Update Textual slash suggestions, command provider, and help rendering to read from the shared metadata instead of `deepy.tui.commands.TUI_COMMANDS`.
- [x] 2.4 Add tests proving stable and Textual command ordering, aliases, categorized help, and unsupported-command handling are derived from the shared registry.

## 3. Textual Composer Rewrite

- [x] 3.1 Extract a focused Textual composer module or widget that owns prompt text, attachment state, generated input suggestion state, slash/file suggestion state, and submission payload construction.
- [x] 3.2 Replace the separate ghost-label input suggestion path with Textual-native `TextArea.suggestion` where compatible with Deepy's Tab/Right acceptance semantics.
- [x] 3.3 Move slash command suggestions into a selectable Textual overlay or bounded suggestion surface that does not write descriptions into prompt text.
- [x] 3.4 Move `@file` suggestions into the same composer suggestion architecture while preserving short-fragment nested search behavior.
- [x] 3.5 Replace prompt-text image labels with composer attachment state rendered outside the editable text buffer.
- [x] 3.6 Preserve image submission payload behavior so submitted prompts still pass selected `PromptImageAttachment` values to the runner.
- [x] 3.7 Add tests for accepting suggestions, removing attachments, submitting text plus attachments, clearing drafts, and keeping prompt text free of UI-only replacement tokens.

## 4. Compact Textual Shell

- [x] 4.1 Redesign the Textual app layout around transcript scrollback, lightweight status line, bottom composer, and on-demand overlays.
- [x] 4.2 Remove or hide persistent heavy header/footer/sidebar chrome from the default idle layout.
- [x] 4.3 Rework transcript block styling so user, assistant, thinking, tool, diff, error, usage, and question content remain compact and readable.
- [x] 4.4 Preserve navigable transcript behavior, block focus, expansion/collapse, autoscroll, and new-output indication in the compact shell.
- [x] 4.5 Add layout tests across narrow and wide terminal sizes to prove composer, status, overlays, and transcript do not overlap.

## 5. Interaction Flow Migration

- [x] 5.1 Migrate `/help`, `/status`, `/model`, `/theme`, `/mcp`, `/skills`, `/sessions`, `/resume`, `/compact`, `/ps`, `/stop`, `/view`, `/input-suggestion`, `/new`, `/exit`, and `/quit` to the redesigned Textual shell.
- [x] 5.2 Preserve audit approval prompts, file mutation diff review, and keyboard approve/reject behavior in the redesigned shell.
- [x] 5.3 Preserve AskUserQuestion single-select, multi-select, custom-answer, cancel, and same-session continuation behavior.
- [x] 5.4 Preserve background task cleanup and exit summary behavior after Textual shutdown.
- [x] 5.5 Preserve live runner event rendering for reasoning, assistant output, tool calls, tool output, usage, errors, and stream token progress.
- [x] 5.6 Add tests proving unsupported or unknown commands are not sent to the model as ordinary prompts.

## 6. Documentation And Migration Messaging

- [x] 6.1 Update English and Chinese UI documentation to describe the redesigned Textual TUI as the future primary UI candidate while `deepy` remains the current default.
- [x] 6.2 Update README references to `deepy tui` and any UI/TUI screenshots so they match the redesigned behavior and current entrypoints.
- [x] 6.3 Remove or replace stale screenshots of the old Textual layout, verifying every referenced asset exists.
- [x] 6.4 Document the redesigned composer model: prompt text, attachments, generated suggestions, slash suggestions, and file suggestions are distinct UI states.

## 7. Validation

- [x] 7.1 Run focused Textual tests for composer, layout, commands, approvals, questions, sessions, skills, status, background tasks, diffs, and runner event rendering.
- [x] 7.2 Run focused stable UI tests for shared command metadata and unchanged stable prompt behavior.
- [x] 7.3 Run `openspec validate make-textual-primary-terminal-ui --type change --strict`.
- [x] 7.4 Run `uv run ruff check src tests`.
- [x] 7.5 Run `uv run ty check src`.
- [x] 7.6 Run `uv run pytest -q`.
- [x] 7.7 Manually validate the redesigned Textual composer in at least the current terminal with CJK input, emoji input or paste, multiline input, slash suggestions, file suggestions, image attachment, and prompt submission.
