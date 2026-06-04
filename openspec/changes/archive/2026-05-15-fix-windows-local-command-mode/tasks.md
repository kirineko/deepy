## 1. Windows Execution Path

- [x] 1.1 Remove `pywinpty` from `pyproject.toml` and refresh `uv.lock`.
- [x] 1.2 Replace the Windows `pywinpty` runner in `src/deepy/ui/local_command.py` with a non-interactive subprocess pipe runner.
- [x] 1.3 Ensure the Windows runner redirects stdin away from the user prompt, captures stdout/stderr, applies the existing timeout, and terminates child processes on timeout or interruption.
- [x] 1.4 Preserve shell dialect argument handling for PowerShell and cmd without using `shell=True`.
- [x] 1.5 Update local command metadata so Windows results report a non-interactive pipe-based TTY mode.

## 2. Output Normalization And Rendering

- [x] 2.1 Add shared output normalization for command output: CRLF and bare CR become LF.
- [x] 2.2 Strip ANSI/VT terminal control sequences and non-printable terminal control characters from Windows local command output.
- [x] 2.3 Preserve printable Unicode text, including Chinese command output.
- [x] 2.4 Ensure sanitized output is used for terminal display and context persistence.
- [x] 2.5 Confirm shell output blocks remain aligned when rendered with sanitized Windows command output.
- [x] 2.6 Reuse shell tool output decoding for Windows local command output so legacy Windows encodings render correctly.

## 3. Session Context Compatibility

- [x] 3.1 Keep the synthetic shell transcript item shape unchanged for local command mode.
- [x] 3.2 Ensure Windows local command results still persist command metadata, exit status, timeout/interruption state, and truncation flags.
- [x] 3.3 Ensure local command-mode turns continue to bypass model requests while updating pending context estimates.

## 4. Tests

- [x] 4.1 Add unit tests for Windows subprocess command success, non-zero exit, timeout, and interruption metadata.
- [x] 4.2 Add tests proving `pywinpty` is no longer required for Windows local command execution.
- [x] 4.3 Add tests for CRLF normalization, ANSI/VT stripping, and Unicode preservation.
- [x] 4.4 Add terminal UI tests showing local command output renders without raw control sequences.
- [x] 4.5 Add session replay tests showing sanitized Windows local command output round-trips through JSONL history.
- [x] 4.6 Add regression tests showing GB18030 and UTF-16LE Windows local command output is decoded before terminal display and context persistence.

## 5. Verification

- [x] 5.1 Run `openspec validate fix-windows-local-command-mode --strict`.
- [x] 5.2 Run `uv run ruff check`.
- [x] 5.3 Run `uv run pyright`.
- [x] 5.4 Run `uv run pytest`.
- [x] 5.5 Manually verify on Windows that `!wsl --version` renders readable output and the next prompt accepts normal text instead of ANSI/VT sequences.
