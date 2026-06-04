## 1. Subagent Expandable Report

- [x] 1.1 Add a focused subagent detection/helper path for `subagent_*` tool blocks without changing non-subagent tool visibility.
- [x] 1.2 Render subagent expanded details with assigned task, bounded final report, and state-aware subagent styling.
- [x] 1.3 Keep collapsed subagent blocks compact and keep regular non-subagent tool output hidden on expand.
- [x] 1.4 Add Modern UI tests for completed subagent expansion, bounded report content, and non-subagent hidden output behavior.
- [x] 1.5 Show subagent parameters in the collapsed Modern UI subagent block while keeping non-subagent tools hidden.
- [x] 1.6 Add regression coverage for visible subagent parameters and hidden non-subagent parameter surfaces.

## 2. Modern UI Copy Bindings

- [x] 2.1 Replace the current no-copy-binding expectation with `Ctrl+C` and `super+c` app-level transcript copy bindings.
- [x] 2.2 Implement a transcript block text extraction path for focused blocks using Textual's clipboard API.
- [x] 2.3 Keep Kitty keyboard protocol disabled by default while preserving explicit environment overrides.
- [x] 2.4 Add tests for binding registration, focused block copy behavior, and unchanged Kitty default behavior.

## 3. Verification

- [x] 3.1 Run `openspec validate improve-modern-ui-subagent-copy --type change --strict`.
- [x] 3.2 Run focused TUI tests covering subagent rendering and copy bindings.
- [x] 3.3 Run `uv run ruff check src tests` and `uv run ty check src` if implementation touches Python code.
