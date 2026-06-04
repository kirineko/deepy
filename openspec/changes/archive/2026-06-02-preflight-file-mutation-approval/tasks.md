## 1. Preflight Planning

- [x] 1.1 Add shared `Write` and `Update` preflight planning APIs that do not commit file side effects.
- [x] 1.2 Reuse existing mutation policy, stale snapshot, content normalization, and update planning logic.
- [x] 1.3 Return structured preflight success/error data with unified diff metadata.
- [x] 1.4 Add unit tests proving preflight does not write files and matches actual mutation diffs.

## 2. Approval Integration

- [x] 2.1 Extend approval resolver inputs or helpers so file mutation approvals can request preflight data.
- [x] 2.2 Render preflight diffs before decision controls in Classic UI.
- [x] 2.3 Render preflight diffs as transcript proposed-change blocks before decision controls in Modern UI.
- [x] 2.4 Mark rejected proposed changes as rejected without mutating files.
- [x] 2.5 Suppress duplicate post-execution diff rendering when it matches an approved proposed diff.

## 3. Approval UI Simplification

- [x] 3.1 Remove large Write/Update diff previews from Classic approval picker controls.
- [x] 3.2 Remove large Write/Update diff previews from Modern audit decision controls.
- [x] 3.3 Keep non-file approvals compact and unchanged in behavior.

## 4. Validation

- [x] 4.1 Validate this OpenSpec change in strict mode.
- [x] 4.2 Run focused audit, file-tool, Classic UI, and Modern UI tests.
- [x] 4.3 Run `uv run ruff check src tests`, `uv run ty check src`, and broader relevant tests.
