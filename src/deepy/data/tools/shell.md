## shell

Run commands in the detected runtime shell for inspection, tests, builds, and
project operations.

Args: `command`, optional `timeout_ms`.

Use the runtime context's command dialect and path style: PowerShell uses
PowerShell commands and Windows paths, `cmd` uses cmd syntax, and `posix` uses
POSIX shell syntax.

On Windows PowerShell, Python child processes run with UTF-8 I/O defaults for
the command invocation; do not ask users to run `chcp` or change their
PowerShell profile for Unicode output.

Runs in the session cwd, preserves cwd between calls when supported, and returns
stdout/stderr JSON with cwd, exit-code, and shell metadata.
