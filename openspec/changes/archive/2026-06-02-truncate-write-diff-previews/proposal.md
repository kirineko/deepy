## Why

Classic UI now renders `Write` approval preflight diffs before the compact approval picker. Large whole-file writes can currently bypass the shared diff line limit and flood the terminal, while `Update` previews are already bounded.

## What Changes

- Apply the shared diff preview line limit to `Write` results the same way it is applied to `Update`.
- Keep the existing diff header, path, and added/removed counts behavior.
- Add regression coverage for rendered and text `Write` diff previews.

## Impact

- Affects stable terminal UI diff rendering for large `Write` previews.
- Reduces large approval/output scrollback without changing file mutation metadata or committed file contents.
