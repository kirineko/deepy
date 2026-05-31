## test_shell

Run constrained verification commands for tester subagents.

Args: `command`, optional `description`, optional `timeout_ms`, optional
`approval_token`.

`test_shell` parses the command into argv and does not run it through an
unrestricted raw shell. It rejects shell composition such as pipes, separators,
redirection, command substitution, heredocs, and background operators.

Low-risk verification commands run immediately and return command, cwd,
exit-code, elapsed time, stdout, stderr, and truncation metadata. Medium-risk
commands are routed through Deepy's outer audit approval flow when an audit
policy is active; after approval they still execute through this constrained
tool. Without an active audit policy, medium-risk commands return
`approval_required` with an `approvalToken` for same-command retry. Destructive,
publishing, mutating, or unsupported commands are denied.
