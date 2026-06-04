## 1. Runtime Environment Classification

- [x] 1.1 Add runtime environment data structures/helpers for OS family, shell kind, command dialect, and path style.
- [x] 1.2 Detect Windows PowerShell, PowerShell Core, cmd, bash, zsh, Linux, macOS, and ambiguous shells from platform and environment inputs.
- [x] 1.3 Render classified environment fields in `build_runtime_context` while preserving existing project, Python, Node, tool availability, and git context.
- [x] 1.4 Add unit tests for Windows PowerShell, POSIX bash/zsh, and unknown-shell runtime context classification.

## 2. Prompt And Tool Guidance

- [x] 2.1 Update system prompt rules to tell the model to choose commands for the detected OS, shell kind, command dialect, and path style.
- [x] 2.2 Update shell tool documentation so the model understands that `shell` executes the current environment shell, including PowerShell on Windows.
- [x] 2.3 Update function tool registration and descriptions to expose the model-facing `shell` tool.
- [x] 2.4 Add prompt/tool documentation tests that verify PowerShell guidance appears for Windows PowerShell context and POSIX defaults remain clear.

## 3. Shell Execution Internals

- [x] 3.1 Refactor shell command construction into shell-specific builders with a shared result metadata shape.
- [x] 3.2 Preserve the existing POSIX wrapper behavior for bash/zsh, including cwd persistence, exit-code capture, timeout handling, output truncation, and `nul` compatibility.
- [x] 3.3 Add a PowerShell wrapper that executes user commands, captures normalized exit codes, emits cwd markers with `Get-Location`, and exits with the captured code.
- [x] 3.4 Resolve shell executable selection for PowerShell Core, Windows PowerShell, cmd, and POSIX shells with conservative fallback behavior.
- [x] 3.5 Include shell kind, command dialect, and path style in shell tool success, failure, and timeout metadata.

## 4. Windows Path And Cwd Behavior

- [x] 4.1 Ensure PowerShell execution uses native Windows path style rather than Git Bash `/c/...` paths.
- [x] 4.2 Keep existing Git Bash path normalization helpers and tests intact.
- [x] 4.3 Add tests for PowerShell cwd marker extraction and cwd persistence semantics using deterministic wrapper output.

## 5. Verification

- [x] 5.1 Add focused tests for runtime context, shell utilities, shell wrapper construction, function tool descriptions, and shell tool metadata.
- [x] 5.2 Run `uv run pytest tests/test_prompts.py tests/test_shell_utils.py tests/test_tools.py`.
- [x] 5.3 Run `uv run ruff check`.
- [x] 5.4 Run `uv run pyright`.
- [x] 5.5 Run `openspec status --change improve-windows-powershell-support` and resolve any artifact or spec validation issues.
