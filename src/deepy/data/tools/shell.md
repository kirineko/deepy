## shell

Run commands in the detected runtime shell for inspection, tests, builds, and
project operations.

Args: `command`, optional `timeout_ms`, optional `run_in_background`.

Use the runtime context's command dialect and path style: PowerShell uses
PowerShell commands and Windows paths, `cmd` uses cmd syntax, and `posix` uses
POSIX shell syntax.

On Windows PowerShell, Python child processes run with UTF-8 I/O defaults for
the command invocation. Deepy also decodes captured output from Windows-native
commands with UTF-8, UTF-16, and GBK-compatible fallbacks. Do not ask users to
run `chcp` or change their PowerShell profile for Unicode output.

Runs in the session cwd, preserves cwd between calls when supported, and returns
stdout/stderr JSON with cwd, exit-code, and shell metadata.

Set `run_in_background` to `true` only for long-running servers, watchers, or
jobs that should continue while you respond. Background commands return a task
id immediately and write stdout/stderr to a Deepy-managed log; use `task_list`,
`task_output`, and `task_stop` to manage them. Do not use background mode for
ordinary short commands where the result is needed before responding.
