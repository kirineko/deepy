## 1. Implementation

- [x] 1.1 Reject oversized Read image results with a recoverable tool error using the shared limit.
- [x] 1.2 Add boundary, mixed-target, and SDK recovery regression tests.
- [x] 1.3 Document the Read image batch limit in tool instructions and both READMEs.

## 2. Verification

- [x] 2.1 Run focused tests, quality gates, full tests, and strict OpenSpec validation.
- [x] 2.2 Review the changes again against the requested base.

## Results

- Focused image/Read tests: 132 passed.
- Full suite: 1025 passed, with Path.home redirected to an isolated temporary directory to avoid sandbox writes to the real user home.
- Ruff, ty, strict change validation, and git diff --check passed.
- Second review found a separate subagent model override issue: Read still validates images against the parent runtime settings. Reported for follow-up; outside this batch-limit fix.
