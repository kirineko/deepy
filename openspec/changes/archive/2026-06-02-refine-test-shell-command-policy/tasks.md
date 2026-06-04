## 1. Implementation

- [x] Update `test_shell` command classification for direct Python execution.
- [x] Refine common cross-language run commands into medium-risk approval.
- [x] Keep hard-deny behavior for destructive and publishing commands.

## 2. Verification

- [x] Add focused regression tests for Python direct execution and other language run commands.
- [x] Verify audit approval policy sees the refined `approval_required` decisions.
- [x] Run focused tests.
- [x] Run OpenSpec change validation.
