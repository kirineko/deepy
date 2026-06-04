## 1. Transcript, Composer, And Markdown

- [x] 1.1 Add focused tests for transcript wheel/touchpad scrolling behavior that does not trigger prompt history.
- [x] 1.2 Make the transcript scroll container reliably receive vertical wheel scrolling while preserving prompt-focused history behavior.
- [x] 1.3 Change the Modern UI prompt composer to reserve exactly four visible input lines and scroll internally for longer drafts.
- [x] 1.4 Tighten Modern UI Markdown table spacing and add/adjust tests for compact transcript table output.

## 2. Background Task Commands

- [x] 2.1 Add tests that user-invoked `/ps` appends a foreground transcript block with stoppable task identifiers.
- [x] 2.2 Change `/ps` from a detached info screen to explicit foreground transcript output.
- [x] 2.3 Cover that AI/tool background task output does not render as user-invoked `/ps` foreground output.

## 3. Reset Workflow

- [x] 3.1 Add tests for Modern UI reset ordering: provider selection before provider-specific API key guidance, then API key, model, base URL, thinking, and UI/theme.
- [x] 3.2 Replace the free-text reset form with a guided Modern UI flow that reuses Classic UI setup selection semantics and preserves cancellation behavior.
- [x] 3.3 Update existing reset tests to assert saved config reload and cancellation outcomes through the guided flow.

## 4. Validation

- [x] 4.1 Run `openspec validate fix-modern-ui-transcript-and-command-ux --type change --strict`.
- [x] 4.2 Run focused TUI and Markdown tests covering the changed behavior.
- [x] 4.3 Run `uv run ruff check src tests` and `uv run ty check src`.

## 5. Follow-up Fixes

- [x] 5.1 Reproduce and fix transcript wheel scrolling when the scroll event lands on transcript child blocks.
- [x] 5.2 Record user-submitted slash commands in prompt history and transcript before executing them.
- [x] 5.3 Add reset UI/theme restart guidance when the selected UI or theme differs from the current settings.
- [x] 5.4 Re-run focused TUI tests, OpenSpec validation, and quality gates.

## 6. Second Follow-up Fixes

- [x] 6.1 Compare reset UI/theme warnings against the currently running UI, not only the stale config value, in both Classic and Modern UI.
- [x] 6.2 Prevent Modern transcript wheel events from also running Textual's default scroll handler.
- [x] 6.3 Re-run focused reset and transcript scrolling tests plus OpenSpec validation.

## 7. Mouse And Light Theme Follow-up

- [x] 7.1 Enable Modern UI Textual mouse event handling while preserving the CJK Kitty keyboard guard.
- [x] 7.2 Add tests that prompt/composer wheel gestures do not recall prompt history.
- [x] 7.3 Keep late tool calls/results anchored before the active assistant answer block.
- [x] 7.4 Add light-theme-specific colors for prompt suggestions and bottom-sheet choice lists.
- [x] 7.5 Re-run focused TUI tests and OpenSpec validation.

## 8. Tool Ordering And Table Autoscroll Follow-up

- [x] 8.1 Replace the overly broad late-tool anchoring rule with placeholder-only in-place updates and append-order behavior for later tool or Shell output.
- [x] 8.2 Add regression coverage that Shell output after `/update` approval remains visible after earlier assistant/diff content.
- [x] 8.3 Await assistant Markdown table rendering before autoscrolling and add focused table autoscroll coverage.
- [x] 8.4 Re-run focused TUI tests, OpenSpec validation, and quality gates.

## 9. Audited Tool Placeholder Follow-up

- [x] 9.1 Add regression coverage for streamed audited `tool_call` events that arrive before the matching approval prompt is rendered.
- [x] 9.2 Associate pending approvals with `call_id` and suppress/reposition audited tool placeholders so final Shell output does not inherit a stale position above approval diff or command context.
- [x] 9.3 Make inline audit decision summaries visible so shell command approvals show the command before the Approve/Reject options.
- [x] 9.4 Re-run focused TUI tests and OpenSpec validation.

## 10. Yolo Diff And Assistant Segmentation Follow-up

- [x] 10.1 Add yolo-mode regression coverage for Update diff output followed by assistant text, Read/Shell outputs, and later assistant Markdown/table text.
- [x] 10.2 Split active assistant rendering at visible tool/diff boundaries so later model text does not appear above Read/Shell output.
- [x] 10.3 Preserve single-block assistant rendering when an existing early placeholder remains before the assistant block and is updated in place.
- [x] 10.4 Re-run focused TUI tests and OpenSpec validation.

## 11. Tool Result Presentation Follow-up

- [x] 11.1 Add regression coverage that `todo_write` results render visible progress, current task, and task item content in the Modern UI transcript.
- [x] 11.2 Adjust Todo tool result rendering to use compact transcript styling that fits the current Modern UI block layout without a nested todo scroller.
- [x] 11.3 Add regression coverage that model-invoked Shell/CMD tool calls, approval summaries, and results display the executable command without appending the model-provided description/comment text.
- [x] 11.4 Adjust model Shell/CMD tool rendering while preserving existing local `!CMD` command rendering.
- [x] 11.5 Add regression coverage that transcript diff blocks do not create an inner vertical scroll region.
- [x] 11.6 Remove nested vertical scrolling from transcript diff blocks while preserving existing diff truncation.
- [x] 11.7 Re-run focused TUI tests and OpenSpec validation.

## 12. Compact Tool Result Presentation Follow-up

- [x] 12.1 Add regression coverage that Todo results show only Current and Tasks sections with visually styled status markers.
- [x] 12.2 Adjust Todo result rendering to remove progress/status rows and add stronger visual distinction for current and task states.
- [x] 12.3 Add regression coverage that Shell/CMD tool results render as a single command summary line without metadata or output body.
- [x] 12.4 Adjust Shell/CMD tool result rendering while preserving local `!CMD` output rendering.
- [x] 12.5 Add regression coverage that generic tool results such as WebFetch stay collapsed to their status summary without inline output.
- [x] 12.6 Adjust generic tool result rendering to hide inline output bodies except for explicitly supported surfaces.
- [x] 12.7 Re-run focused TUI tests and OpenSpec validation.

## 13. Shell Command Preservation Follow-up

- [x] 13.1 Add regression coverage that Shell/CMD results keep the command from matching `tool_call` arguments when result metadata omits it.
- [x] 13.2 Preserve the prior Shell/CMD command in the transcript summary when updating a running tool block from output.
- [x] 13.3 Re-run focused TUI tests and OpenSpec validation.
