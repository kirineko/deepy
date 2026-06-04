## Why

The stable terminal UI already exposes audit mode and resolves SDK approval interruptions through an explicit approval UI, but the experimental Textual TUI does not yet provide an equivalent UI layer. As a result, approval-gated actions in the TUI can be rejected by the runner fallback instead of being presented to the user for a decision.

## What Changes

- Add Textual TUI audit mode state initialized from persisted audit settings.
- Show the active audit mode in the TUI status surfaces, including the status bar and `/status`.
- Add a Textual-native audit mode cycle interaction aligned with the stable UI order: `normal`, `auto`, `yolo`, `normal`.
- Add a Textual-native SDK approval prompt that lets users approve or reject built-in tool and MCP tool interruptions.
- Reuse stable UI approval summary and diff-review rules so shell, MCP, `Write`, and `Update` approvals stay consistent across UIs.
- Preserve existing TUI prompt completion, input-suggestion, interrupt, and transcript behavior.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `experimental-textual-tui`: Add Textual audit mode visibility, mode cycling, and approval prompt behavior aligned with the stable terminal UI contract.

## Impact

- Affects Textual TUI state, status rendering, key bindings, model-turn runner arguments, and modal screens under `src/deepy/tui/`.
- Reuses shared audit data structures from `src/deepy/audit.py` and approval summary/diff logic from `src/deepy/ui/audit_approval_panel.py`.
- Adds focused Textual TUI tests in `tests/test_tui_app.py`.
- No provider, storage, or stable prompt-toolkit UI behavior changes.
