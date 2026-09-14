## 1. Implementation
- [x] 1.1 Pass effective child model configuration to single and batch Read calls.
- [x] 1.2 Add bidirectional, inherited, and concurrent regression coverage.
- [x] 1.3 Update bilingual documentation.

## 2. Validation
- [x] 2.1 Run focused and full tests, Ruff, ty and strict OpenSpec checks.
- [x] 2.2 Review the full diff again.

## Results
- Focused tests: 137 passed.
- Full suite: 1029 passed with Path.home redirected to a temporary test directory for sandbox isolation.
- Ruff, ty, strict OpenSpec validation (27 items), and git diff --check passed.
- Re-reviewed the diff against 9d58ffb41289f73a5897cbe03c667335299068da; no additional actionable findings identified. No live provider API calls were made.
