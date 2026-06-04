## 1. Shell Output Decoding

- [x] 1.1 Change shell stdout/stderr capture in `ToolRuntime.shell` from text-mode temporary files to binary temporary files while preserving process tracking, timeout handling, and cleanup.
- [x] 1.2 Add a shell-output decode helper that prefers UTF-8/UTF-8-SIG, detects likely UTF-16-style output, falls back to GB18030, and finally decodes with replacement.
- [x] 1.3 Apply decoded stdout/stderr before sentinel extraction, output truncation, result construction, and timeout result construction.
- [x] 1.4 Preserve cwd tracking, normalized exit-code tracking, output truncation metadata, and existing shell metadata.
- [x] 1.5 Add regression tests for readable UTF-16-style Windows native command output.
- [x] 1.6 Add regression tests for readable GBK-compatible shell output.
- [x] 1.7 Add regression tests proving ordinary UTF-8 shell output and truncation behavior remain unchanged.

## 2. Ctrl+J Prompt Input

- [x] 2.1 Add Ctrl+J newline support on all platforms.
- [x] 2.2 Remove Shift+Enter and Ctrl+Enter escape-sequence newline behavior.
- [x] 2.3 Keep plain Enter mapped to prompt submission.
- [x] 2.4 Remove Windows-only prompt newline fallback logic and any platform-specific toolbar branching for newline shortcuts.
- [x] 2.5 Update prompt toolbar/help text to advertise Ctrl+J as the only newline shortcut on all platforms.
- [x] 2.6 Update prompt input tests to cover Ctrl+J newline, Enter submission, and absence of Shift+Enter/Ctrl+Enter guidance.

## 3. Documentation And Guidance

- [x] 3.1 Update shell tool documentation to state that Deepy decodes captured Windows-native command output internally and users should not be asked to run `chcp` or change PowerShell profiles.
- [x] 3.2 Remove or revise any prompt UI tests, constants, or docs that advertise Shift+Enter or Ctrl+Enter as newline shortcuts.
- [x] 3.3 Keep the model-facing shell command dialect guidance unchanged except where output decoding behavior is relevant.

## 4. Verification

- [x] 4.1 Run `uv run pytest tests/test_tools.py tests/test_prompt_input.py`.
- [x] 4.2 Run any additional focused tests touched by shell docs or prompt toolbar changes.
- [x] 4.3 Run `openspec validate fix-windows-shell-encoding-and-ctrl-enter --type change --strict`.
- [x] 4.4 Add or update manual Windows verification notes for `wsl.exe --status 2>&1`, Ctrl+J newline insertion, and Enter submission.
