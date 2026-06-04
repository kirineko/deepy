## 1. Shell Encoding Compatibility

- [x] 1.1 Add a Windows-scoped shell environment helper that preserves parent environment values and defaults `PYTHONUTF8=1` plus `PYTHONIOENCODING=utf-8` only for Windows shell invocations.
- [x] 1.2 Update shell process launch to pass the helper environment without changing cwd, timeout, process tracking, stdout/stderr capture, or shell metadata behavior.
- [x] 1.3 Add PowerShell wrapper output encoding setup for Windows PowerShell/PowerShell 7 command scripts.
- [x] 1.4 Add tests that PowerShell invocations receive UTF-8 Python defaults and output encoding setup.
- [x] 1.5 Add tests that POSIX shell command construction and environment behavior do not receive Windows-specific PowerShell encoding setup.

## 2. GBK-Compatible File Tools

- [x] 2.1 Extend text encoding detection to try UTF-16LE BOM, strict UTF-8/UTF-8-SIG, then strict GB18030 for GBK-compatible files.
- [x] 2.2 Preserve detected GBK-compatible encoding when writing or modifying existing files.
- [x] 2.3 Ensure failed or unknown text decoding remains structured and does not bypass read-before-write or stale-write checks.
- [x] 2.4 Add a read test for a GBK-compatible file containing Unicode text and assert readable output plus encoding metadata.
- [x] 2.5 Add a modify test for a GBK-compatible file and assert replacement succeeds and bytes remain GBK-compatible.
- [x] 2.6 Add regression tests that valid UTF-8 and UTF-16LE files keep their existing encoding behavior.

## 3. Windows Terminal Prompt Input

- [x] 3.1 Add an idempotent Windows-only prompt-toolkit Win32 input patch that maps Shift+Enter console records to the existing newline binding path.
- [x] 3.2 Keep the existing vt100 Shift+Enter sequence override for terminals that emit ANSI sequences.
- [x] 3.3 Add tests for the Win32 Shift+Enter mapping using simulated prompt-toolkit input records or an isolated helper.
- [x] 3.4 Add regression tests that ordinary Enter still submits and existing vt100 Shift+Enter parsing still inserts a newline.

## 4. Runtime Context And Documentation

- [x] 4.1 Update runtime context or shell metadata only if needed to expose Windows encoding compatibility clearly to the model or tests.
- [x] 4.2 Update model-facing shell or modify tool guidance only if implementation introduces new observable behavior the model should know.
- [x] 4.3 Avoid documenting any requirement for users to run `chcp`, change PowerShell profiles, or convert files manually.

## 5. Verification

- [x] 5.1 Run focused tests for shell utilities, built-in tools, and prompt input.
- [x] 5.2 Run the broader relevant test suite to catch macOS/Linux regressions in shared helpers.
- [x] 5.3 Manually verify or provide a clear manual verification script for Windows Terminal + PowerShell 7 covering Unicode Python execution, GBK-compatible file modify, and Shift+Enter newline insertion.
- [x] 5.4 Run `openspec validate improve-windows-gbk-powershell-compatibility --type change` and resolve any proposal/spec/task issues.
