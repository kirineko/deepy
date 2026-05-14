## bash

Run shell commands for inspection, tests, builds, and project operations.

Args: `command`, optional `timeout_ms`.

Despite the legacy tool name, commands run in the detected runtime shell for the
current environment. Match the runtime context's command dialect and path style:
use PowerShell-compatible commands and Windows paths when the dialect is
`powershell`, cmd syntax when the dialect is `cmd`, and POSIX shell syntax when
the dialect is `posix`.

Runs in the session cwd, preserves cwd between calls when the shell supports it,
and returns stdout/stderr JSON with cwd, exit-code, and shell metadata.
