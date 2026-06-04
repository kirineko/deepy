## Context

Deepy is built on the OpenAI Agents SDK. The current main agent is constructed
with built-in tools and optional MCP servers, then executed through
`Runner.run_streamed()`. Tool calls and stream events are normalized into Deepy
events and rendered by the terminal UI.

OpenAI Agents SDK supports two multi-agent patterns relevant here:

- Handoffs: another agent takes over the conversation.
- Agent-as-tool: the main agent calls a specialist agent as a tool and continues
  the conversation after receiving the specialist result.

Deepy's desired product behavior is orchestration by the main agent: automatic
assignment when useful, visible subagent status, and final synthesis by Deepy.
That maps better to agent-as-tool than handoffs.

## Goals / Non-Goals

**Goals:**

- Let Deepy automatically use focused subagents for broad exploration, review,
  and test/reproduction work when the task naturally benefits from delegation.
- Keep the user informed when subagents are assigned, running, completed,
  failed, or blocked.
- Keep the main Deepy agent in control of final synthesis and user-facing
  answers.
- Keep built-in subagents useful without requiring user configuration.
- Let users define custom subagents under `.deepy/subagents` or
  `~/.deepy/subagents` with documented templates and examples.
- Support realistic test verification commands through a constrained
  `test_shell` tool rather than giving test subagents raw arbitrary shell.
- Allow `explore` to use search-class MCP tools automatically.

**Non-Goals:**

- Do not implement arbitrary user-provided Python tools for subagents in the
  first version.
- Do not place subagent definitions under `.agents`; that directory remains for
  Agent Skills.
- Do not build persistent team/task-board agents in the first version.
- Do not implement full OpenAI Agents SDK approval interruption persistence and
  resume in the first version.
- Do not make background/resumable subagents part of the MVP.
- Do not allow nested subagent spawning in the first version.

## Decisions

### Use `Agent.as_tool()` instead of handoffs

Each enabled subagent becomes a model-visible tool on the main Deepy agent. The
tool description contains when to use the subagent. The subagent receives a
focused task prompt, performs its work with its own tool set and instructions,
and returns a concise report. The main agent incorporates that report into the
next step or final response.

Alternatives considered:

- Handoffs. Rejected for MVP because they transfer control away from the main
  Deepy agent and make global task synthesis harder.
- A fully custom scheduler outside the SDK. Rejected because the SDK already
  provides nested agent execution, streaming callbacks, model selection, and
  tool approval hooks.

### Built-in subagents first

Deepy ships with:

- `explore`: read-only codebase, docs, and web/search-MCP exploration.
- `reviewer`: read-only code quality, correctness, security, and maintainability
  review.
- `tester`: verification-focused agent that can read/search and run
  constrained test/diagnostic commands through `test_shell`.

These are enough to cover the first valuable workflows without allowing
autonomous arbitrary implementation agents to mutate source code.

### Custom subagents live under `.deepy/subagents`

Project definitions live under `.deepy/subagents/*.md`; user definitions live
under `~/.deepy/subagents/*.md`; built-ins are the fallback. Project definitions
override user definitions with the same name, and user definitions override
built-ins. Definitions use Markdown with YAML frontmatter:

```md
---
name: tester
description: Reproduce bugs and run targeted verification commands.
model: inherit
tools:
  - read_file
  - Search
  - test_shell
mcp:
  inherit_search: false
max_turns: 30
---

You are a test engineer. Reproduce reported behavior and run targeted tests.
Do not modify source files. Report exact commands, outputs, and conclusions.
```

`.agents/skills` remains reserved for Agent Skills so users do not confuse
skills with subagents.

### Tool access is explicit and conservative

Subagents get tool allowlists rather than inheriting every main-agent tool.

Default built-in tool sets:

- `explore`: `Search`, `read_file`, `WebSearch`, `WebFetch`, search-class MCP
  tools, and optionally `load_skill` for relevant read-only skill instructions.
- `reviewer`: `Search`, `read_file`, and optionally `WebFetch` when reviewing
  referenced docs.
- `tester`: `Search`, `read_file`, `test_shell`, and task-output
  inspection only if the command was launched through `test_shell`.

No built-in subagent receives `edit_text`, `write_file`, or `apply_patch` in the
MVP.

### `test_shell` is a policy tool, not raw shell

`test_shell` accepts a command string but does not run it through an unrestricted
shell by default. It parses the command, rejects shell composition syntax, and
classifies the request:

- `allow`: execute immediately.
- `approval_required`: return a structured approval-needed result that the main
  Deepy agent escalates with `AskUserQuestion`.
- `deny`: refuse the command with a policy reason.

The allow/approval policy is broad enough for normal development verification:

- Python: `uv run pytest`, `python -m pytest`, `pytest`, `uv run ruff check`,
  `uv run ty check`, `uv run mypy`, `uv pip list`, `python -m pip list`,
  `pip list`.
- Node/frontend: `npm test`, `npm run test`, `npm run lint`,
  `npm run typecheck`, `npm run build`, and equivalent `pnpm`, `yarn`, and
  `bun` commands.
- Java/Spring: `mvn test`, `mvn verify`, `mvn package`, `./mvnw test`,
  `./mvnw verify`, `mvn spring-boot:run`, `./mvnw spring-boot:run`, `gradle
  test`, `./gradlew test`.
- Rust: `cargo test`, `cargo check`, `cargo clippy`.
- Go: `go test`, `go vet`.
- Diagnostics: safe `curl` GET/HEAD requests, `ping`, `head`, `tail`.
- Docker: `docker ps`, `docker logs`, `docker compose ps`,
  `docker compose logs`, `docker compose config`, and approval-gated
  `docker compose up`.
- Databases: read-only mysql statements such as `SELECT`, `SHOW`, `DESCRIBE`,
  and `EXPLAIN`.

Destructive or publishing commands are denied by default, including `rm`, source
mutating `mv`/`cp`, `chmod`, `chown`, `git reset`, `git clean`, `git checkout`,
`git add`, `git commit`, `git push`, `docker system prune`,
`docker compose down -v`, mysql `DROP`/`DELETE`/`UPDATE`/`INSERT`/`ALTER`/
`TRUNCATE`, mutating `curl` methods, and package publish/deploy commands.

### First version uses policy escalation, not full SDK approval mode

The SDK supports `needs_approval`, interruptions, `RunResult.to_state()`,
`RunState.approve()`, and `RunState.reject()`, including nested agent-as-tool
approval. Deepy does not currently persist or resume SDK approval interruptions.
Implementing full approval mode would require session schema, UI, resume, and
nested approval plumbing.

For this change, `test_shell` returns `approval_required` for medium-risk
commands. The main agent must ask the user through `AskUserQuestion`. If the
user approves, the main agent retries the same command with an approval token or
same-turn approved flag managed by Deepy.

Full SDK approval mode is explicitly deferred until Deepy needs global approvals
for all tools.

### Search-class MCP inheritance for `explore`

Deepy already identifies preferred MCP web search tools for the main agent.
`explore` may automatically inherit those search-class MCP tools and direct
fetch/search built-ins. It must not inherit all MCP tools by default.

Search-class MCP inheritance should be based on Deepy-controlled metadata or
tool naming heuristics that are visible in configuration/status output. Users
can disable it per custom subagent with `mcp.inherit_search = false`.

### User-visible lifecycle events

Subagent execution should be visible but compact:

```text
[Subagent] explore started - Trace auth routing and data access
[Subagent] explore completed - 7 files, 2 key findings
```

The UI should show assignment, status, final summary, and failure/approval
state. Nested subagent thinking should not flood the main transcript. Tool calls
inside a subagent may be summarized or shown under the subagent event group when
useful.

### Concurrency and recursion limits

MVP constraints:

- Maximum one level of subagents: subagents cannot spawn subagents.
- Default maximum concurrent subagent executions is small, such as 3.
- Subagent max turns are bounded per definition.
- The first implementation can execute subagents foreground as agent-as-tool
  calls. Background/resumable subagents are deferred.

## Risks / Trade-offs

- Broad command support can become arbitrary shell in disguise -> Use parsing,
  deny shell composition by default, classify command families, and add tests
  for risky examples.
- `test_shell` policy may reject legitimate project-specific verification ->
  Provide `.deepy/config.toml` extension points for allow/approval patterns.
- Search-class MCP detection may misclassify tools -> Default to known preferred
  MCP web search tools and let users opt out.
- Subagent output can clutter the transcript -> Render lifecycle summaries and
  only expose detailed nested events when useful.
- Automatic delegation can overuse tokens -> Use precise descriptions, max
  turns, concurrency limits, and prompt guidance that subagents are for broad,
  independent, or specialist tasks.

## Migration Plan

1. Add subagent definition models, built-in definitions, discovery precedence,
   and validation without wiring them into the main agent.
2. Add `test_shell` policy classification and tests for allow, approval, and
   deny cases.
3. Add subagent tool construction through `Agent.as_tool()` with tool allowlists,
   no recursion, bounded max turns, and search-class MCP inheritance for
   `explore`.
4. Add stream-event normalization and terminal rendering for subagent lifecycle
   and result summaries.
5. Add `AskUserQuestion` escalation for `test_shell` approval-required results.
6. Add documentation for built-ins, `.deepy/subagents` templates, custom examples,
   and test-shell policy extension.
7. Validate with focused unit tests, runner tests using fake SDK runners, UI
   render tests, and `openspec validate add-subagent-support --strict`.

Rollback is straightforward before release: keep the new definition loader and
docs inert, remove subagent tools from the main agent construction, and leave
existing built-in tools unchanged.

## Open Questions

- Should approved `test_shell` command patterns persist for only the current
  Deepy process, the current session, or the project config?
- Should custom subagents support `background = true` after the foreground MVP,
  or should background subagents wait for a broader task-browser UI?
- Should `reviewer` have optional `test_shell` access for running static checks,
  or should all command execution remain with `tester`?
