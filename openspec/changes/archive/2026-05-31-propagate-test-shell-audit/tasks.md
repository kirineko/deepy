## 1. Test Shell Policy

- [x] 1.1 Classify `cargo run` as a medium-risk `test_shell` command requiring approval.
- [x] 1.2 Add an audit-approved execution path for `test_shell` approval-required commands while preserving the legacy token retry path.

## 2. Audit Integration

- [x] 2.1 Add SDK `needs_approval` handling for `test_shell` commands classified as `approval_required`.
- [x] 2.2 Ensure audit-approved `test_shell` execution still uses the constrained runner and never exposes raw `shell` to tester subagents.

## 3. Documentation And Verification

- [x] 3.1 Update prompt/tool/docs text to describe SDK audit-backed `test_shell` approvals.
- [x] 3.2 Add focused regression tests for cargo classification, test_shell audit gating, and audit-approved execution.
- [x] 3.3 Run OpenSpec validation and focused tests for the changed areas.
