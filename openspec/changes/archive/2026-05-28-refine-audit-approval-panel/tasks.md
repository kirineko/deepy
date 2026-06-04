## 1. Approval Rendering Model

- [x] 1.1 Inspect existing approval rendering, approval picker, and message diff preview helpers to identify reusable boundaries.
- [x] 1.2 Add an internal approval view model that separates title, target, metadata, preview content, auxiliary controls, and final decisions from raw SDK approval arguments.
- [x] 1.3 Add typed approval summarizers for shell command, MCP tool, file write, file update, and unknown fallback approvals.
- [x] 1.4 Add a target path formatter that uses project-relative paths only for files under the active project root and otherwise uses home-relative or absolute paths.

## 2. Diff Preview Behavior

- [x] 2.1 Implement highlighted diff preview generation for `Write` approvals as empty-file-to-new-content diffs.
- [x] 2.2 Implement highlighted diff preview generation for `Update` approvals when before-and-after content can be derived reliably.
- [x] 2.3 Implement the safe fallback summary for `Update` approvals that do not contain enough context for a reliable diff.
- [x] 2.4 Add compact diff truncation and an expandable preview state without placing the expand/collapse control in the final decision area.

## 3. Approval Picker Interaction

- [x] 3.1 Update the approval picker so visible controls are navigated with `Up` and `Down` only.
- [x] 3.2 Make `Enter` activate the selected control, resolving only `Approve` or `Reject` and toggling auxiliary expand/collapse controls without resolving approval.
- [x] 3.3 Make `Esc` reject the active approval.
- [x] 3.4 Remove `Y`, `A`, `N`, `R`, lowercase variants, number keys, and any visible hints that advertise those shortcuts from the approval picker.

## 4. Tests

- [x] 4.1 Add focused tests for shell approval panels showing concise command summaries without raw internal field labels.
- [x] 4.2 Add focused tests for MCP approval panels showing server/tool and bounded key arguments without full raw JSON dumps.
- [x] 4.3 Add focused tests for `Write` approval panels showing project-relative paths and highlighted new-file diff previews.
- [x] 4.4 Add focused tests for `Update` approval panels showing project-relative paths and highlighted removed/added diff lines.
- [x] 4.5 Add focused tests for outside-project target paths remaining home-relative or absolute.
- [x] 4.6 Add approval picker tests for `Up`/`Down`, `Enter`, `Esc`, auxiliary expand/collapse behavior, and ignored letter shortcuts.

## 5. Documentation And Validation

- [x] 5.1 Update English and Chinese UI documentation to describe the refined audit approval panel and keyboard interaction.
- [x] 5.2 Run focused terminal UI and approval picker tests.
- [x] 5.3 Run `openspec validate refine-audit-approval-panel --type change --strict`.
