# Subagents

Deepy can delegate independent specialist work to subagents while the main Deepy
agent keeps control of the final answer.

Built-ins:

- `explore`: read-only codebase, documentation, and web/search investigation.
- `reviewer`: read-only correctness, security, maintainability, design, and
  test-risk review.
- `tester`: bug reproduction and verification through constrained `test_shell`.

Deepy exposes subagents as tools named `subagent_explore`, `subagent_reviewer`,
and `subagent_tester`. Use is automatic when the main agent decides the task is
large enough or specialized enough to delegate. The terminal shows compact
`[Subagent] <name>` lifecycle lines and the final subagent report.

Limits:

- Subagents do not spawn other subagents.
- Built-in subagents do not receive source mutation tools.
- `tester` receives `test_shell`, not raw unrestricted `shell`.
- Background or resumable subagents are not part of this version.
- Full OpenAI Agents SDK approval interruption/resume is deferred; `test_shell`
  uses Deepy's policy result plus `AskUserQuestion` flow.

## Custom Subagents

Project custom subagents live in `.deepy/subagents/*.md`. User custom subagents
live in `~/.deepy/subagents/*.md`. Project definitions override user definitions,
and user definitions override built-ins with the same normalized name.

Deepy does not load `.agents/skills` as subagents. That directory remains for
Agent Skills.

Template:

```md
---
name: triage
description: Read logs and source paths to identify likely root causes.
model: inherit
tools:
  - Search
  - read_file
  - WebFetch
mcp:
  inherit_search: false
max_turns: 20
---

You are a read-only triage subagent. Inspect only the assigned scope.
Return likely causes, evidence, relevant paths, and unresolved questions.
Do not modify files or run commands.
```

Supported tools for custom subagents:

- `Search`
- `read_file`
- `WebSearch`
- `WebFetch`
- `load_skill`
- `task_output`
- `test_shell`

Mutation tools such as `edit_text`, `write_file`, `apply_patch`, and raw
`shell` are not supported for subagents in this version.

## `test_shell`

`test_shell` parses commands into argv and does not run them through an
unrestricted shell. It classifies commands as:

- `allow`: execute immediately with bounded timeout, fixed project cwd, stdout,
  stderr, exit code, elapsed time, and truncation metadata.
- `approval_required`: do not execute; return a command, reason, and approval
  token for Deepy to ask the user.
- `deny`: refuse destructive, publishing, source-mutating, or unsupported
  commands.

Supported low-risk families include Python/uv/pip test and inspection commands,
Node package-manager test/lint/typecheck/build commands, Maven/Gradle
test/verify/package/build, Rust `cargo test/check/clippy`, Go `go test/vet`,
read-only `curl`, `ping`, read-only `mysql`, read-only Docker/Docker Compose
diagnostics, `head`, and `tail`.

Approval-required examples include dependency installation, Spring Boot service
startup, Docker Compose startup/build, and project-defined medium-risk patterns.

Denied examples include `rm`, source-mutating `mv`/`cp`, `chmod`, `chown`,
mutating git commands, package publish/deploy, `docker system prune`,
`docker compose down -v`, mutating `curl`, mutating `mysql`, and shell
composition such as pipes, separators, redirection, command substitution, and
background operators.

Project policy extensions can be configured in `~/.deepy/config.toml` or the
selected Deepy config file:

```toml
[tools.test_shell]
allow_patterns = ["make test-*", "just verify *"]
approval_required_patterns = ["make seed-db", "docker compose up *"]
```

Global deny rules still override project allow patterns.
