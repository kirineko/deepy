## 1. Audit State And Status

- [x] 1.1 Add runtime `AuditModeState` ownership to the Textual TUI app, initialized from `settings.audit.mode`.
- [x] 1.2 Pass the TUI audit state into `run_prompt_once()` through `audit_mode`.
- [x] 1.3 Add active audit mode to the TUI status bar context without hiding existing provider, model, cwd, MCP, background-task, context, or cache segments.
- [x] 1.4 Add active audit mode and runtime-vs-config distinction to the TUI `/status` screen.

## 2. Audit Mode Cycling

- [x] 2.1 Add `Shift+Tab` handling in the Textual TUI to cycle `normal -> auto -> yolo -> normal`.
- [x] 2.2 Ensure plain `Tab` still accepts slash-command completions, file mentions, and input suggestions.
- [x] 2.3 Add TUI tests for runtime mode cycling and preserved Tab behavior.

## 3. Textual Approval UI

- [x] 3.1 Add a Textual approval modal that can render approval title, primary target, metadata, optional preview, and decision controls.
- [x] 3.2 Reuse shared approval summary and diff-review rules from the stable UI approval panel layer.
- [x] 3.3 Render long `Write` and `Update` diffs in a scrollable preview region while keeping only Approve and Reject decision controls.
- [x] 3.4 Implement keyboard behavior: Up/Down moves selection between decisions, Enter activates selected decision, Esc rejects, and letter shortcuts do not approve or reject.

## 4. Runner Integration

- [x] 4.1 Add an async TUI approval resolver that opens the Textual modal for each pending approval and returns `ApprovalDecision` values.
- [x] 4.2 Pass the resolver into TUI model turns while preserving existing stream-event, interrupt, question, and transcript behavior.
- [x] 4.3 Add tests that an approval request is surfaced through the TUI resolver and resumes the original model turn after approve or reject.
- [x] 4.4 Add tests that approval prompts are not appended as normal transcript messages or submitted as normal user messages.

## 5. Validation

- [x] 5.1 Run focused TUI tests covering audit status, mode cycling, approval modal behavior, and resolver integration.
- [x] 5.2 Run scoped quality checks for touched TUI files.
- [x] 5.3 Run `openspec validate add-tui-audit-approval-ui --type change --strict`.
