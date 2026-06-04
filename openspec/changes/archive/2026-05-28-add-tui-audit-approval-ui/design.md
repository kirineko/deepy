## Context

The stable Rich/prompt-toolkit UI owns a runtime `AuditModeState`, shows the active mode in status surfaces, lets users cycle the mode with `Shift+Tab`, and injects an SDK `approval_resolver` that renders an explicit approval picker. The experimental Textual TUI currently calls `run_prompt_once()` without an audit mode state or approval resolver, so approval-gated SDK interruptions fall back to runner-level rejection instead of a Textual decision UI.

The stable UI already has reusable approval summarization and diff-review logic in `deepy.ui.audit_approval_panel`. The TUI should reuse those rules while presenting the interaction through Textual-native screens.

## Goals / Non-Goals

**Goals:**

- Make the active audit mode visible in the Textual TUI.
- Allow runtime audit mode cycling in the TUI using the same mode order as the stable UI.
- Resolve SDK approval interruptions through a Textual approval modal.
- Keep shell, MCP, `Write`, and `Update` approval summaries aligned with stable UI conventions.
- Preserve existing TUI prompt suggestions, transcript rendering, interrupt behavior, and Textual testability.

**Non-Goals:**

- Persist runtime audit mode cycles back to config.
- Replace or refactor the stable prompt-toolkit approval picker.
- Change audit policy semantics in `run_prompt_once()` or tool definitions.
- Add new audit modes or alter `normal`, `auto`, or `yolo` behavior.

## Decisions

- **Textual owns a runtime `AuditModeState`.** Initialize it from `settings.audit.mode` when `DeepyTuiApp` is created, pass it to `run_prompt_once(audit_mode=...)`, and use it for status display. This mirrors the stable UI while keeping config unchanged during runtime cycling.

- **Use `Shift+Tab` for mode cycling.** Stable UI already uses this binding and explicitly preserves plain `Tab` for completion and suggestions. The TUI should add an app-level or prompt-level `Shift+Tab` binding that cycles `normal -> auto -> yolo -> normal` and refreshes status without submitting the prompt.

- **Implement a Textual-native approval screen.** Add an `AuditApprovalScreen` under `src/deepy/tui/screens.py` that returns an approval outcome. It should use Textual navigation and selection rather than prompt-toolkit. `Esc` rejects, and `Enter` activates the selected `Approve` or `Reject` decision.

- **Reuse stable approval view construction.** Build approval content from `deepy.ui.audit_approval_panel.build_approval_view()` or an equivalent shared helper so shell command, MCP, file path, and diff preview rules stay consistent. Textual may render the view with Textual widgets, but summary and diff construction should come from the shared approval layer.

- **Use scrolling instead of expand/collapse preview controls.** The Textual TUI already owns a full-screen scrollable surface, so file mutation approvals should render the available diff preview in a scrollable region and keep the decision controls limited to `Approve` and `Reject`. This avoids duplicating the stable prompt-toolkit picker's compact/expanded interaction in a UI where scrolling is natural.

- **Use an async resolver inside the TUI model-turn worker.** `run_prompt_once()` accepts an awaitable approval resolver, and existing TUI worker code already awaits Textual screens in other command paths. The resolver can iterate pending approvals, await `push_screen_wait(AuditApprovalScreen(...))`, and return `ApprovalDecision` values to the paused run.

## Risks / Trade-offs

- **Approval screen blocks model progress while open** -> This is intended; the SDK run is paused until the user decides. Keep the app responsive to modal navigation and rejection.
- **Textual rendering cannot directly mirror Rich panel output pixel-for-pixel** -> Reuse the shared approval view data and diff rules, but let Textual own layout.
- **`Shift+Tab` support can vary by terminal** -> Keep the binding aligned with stable UI and cover the Textual event path in tests; avoid changing plain `Tab` behavior.
- **Large file diffs can overwhelm a modal** -> Keep the preview inside a bounded scrollable Textual region and leave only approval decisions in the control list.
