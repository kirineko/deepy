## test_shell

Run constrained verification commands for tester subagents.

Args: `command`, optional `description`, optional `timeout_ms`, optional
`approval_token`.

`test_shell` parses the command into argv and does not run it through an
unrestricted raw shell. It rejects shell composition such as pipes, separators,
redirection, command substitution, heredocs, and background operators.

Low-risk verification commands run immediately and return command, cwd,
exit-code, elapsed time, stdout, stderr, and truncation metadata. Medium-risk
commands return `approval_required` with an `approvalToken`; the main Deepy
agent must ask the user before retrying the same command with that token.
Destructive, publishing, mutating, or unsupported commands are denied.
