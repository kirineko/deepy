## 1. Encoding Policy

- [x] 1.1 Update the new-file encoding selection so managed text files default to plain UTF-8 on all platforms.
- [x] 1.2 Preserve existing-file detected encoding behavior for UTF-8 with signature, UTF-16, GBK-compatible, and plain UTF-8 files.
- [x] 1.3 Keep explicit byte-based writes and existing newline normalization behavior unchanged.

## 2. Regression Tests

- [x] 2.1 Replace the Windows new non-ASCII file test expectation from `utf8-sig` to plain `utf8` without `EF BB BF`.
- [x] 2.2 Add or update a Windows new Python source file regression that includes non-ASCII content and parses successfully when read as `utf-8`.
- [x] 2.3 Keep coverage proving existing UTF-8 signature files preserve their signature when edited.
- [x] 2.4 Run the focused tool tests that cover modify/write encoding behavior.

## 3. Spec And Verification

- [x] 3.1 Verify `openspec validate fix-windows-new-file-bom-policy --type change --strict` passes.
- [x] 3.2 Confirm the resulting tool metadata reports `encoding="utf8"` for Windows new non-ASCII text files.
- [x] 3.3 Document any remaining CSV or legacy Windows consumer behavior as out of scope for this change.
