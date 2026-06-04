## Why

Deepy currently runs a single main coding agent for every task. That keeps the
interaction simple, but it also means broad codebase exploration, independent
verification, and specialist review all compete for the main agent's context
window. Users need Deepy to automatically delegate suitable work to focused
subagents, show what was delegated, and fold the results back into the main
answer without requiring manual orchestration.

This change adds first-class subagent support while preserving Deepy's existing
terminal-centered workflow and Agent Skills directory boundaries.

## What Changes

- Add built-in subagents for common coding-agent workflows:
  - `explore`: read/search focused codebase and web/search-MCP exploration.
  - `reviewer`: read-only implementation, quality, correctness, and risk review.
  - `tester`: targeted reproduction, test execution, and verification.
- Expose subagents to the main Deepy agent through OpenAI Agents SDK
  `Agent.as_tool()` so the main agent remains the orchestrator and synthesizer.
- Add user-visible subagent lifecycle output for assignment, progress, completion,
  failure, and summarized results.
- Add `.deepy/subagents/*.md` and `~/.deepy/subagents/*.md` custom subagent
  definitions with Markdown plus YAML frontmatter.
- Add documentation templates and examples for custom subagents without using
  `.agents`, which remains reserved for Agent Skills.
- Add a constrained `test_shell` capability for test-oriented subagents. It
  supports common development verification commands across Python, Node.js,
  Java/Spring, Rust, Go, frontend tooling, Docker Compose, curl, ping, mysql,
  head, and tail while classifying commands as allow, approval-required, or deny.
- Allow `explore` to automatically inherit search-class MCP tools while avoiding
  broad side-effecting MCP inheritance.
- Defer full global approval mode and SDK interruption-resume support. The first
  version uses command policy plus `AskUserQuestion` escalation for subagent
  commands that need user approval.

## Capabilities

### New Capabilities

- `subagents`: Built-in and user-defined subagent discovery, selection,
  execution, lifecycle visibility, and result synthesis.

### Modified Capabilities

- `tools`: Add constrained test-shell execution and subagent-facing tool
  allowlists.
- `mcp-support`: Identify search-class MCP tools that `explore` may inherit.
- `configuration`: Add `.deepy/subagents` custom subagent configuration and
  project/user precedence.
- `terminal-ui`: Render subagent lifecycle and result status in the stable
  terminal UI.
- `session-context`: Persist enough subagent event/result data for readable
  session replay without storing independent subagent transcripts as main-thread
  conversation history.

## Impact

- Affects agent construction in `src/deepy/llm/agent.py` and streaming/event
  handling in `src/deepy/llm/runner.py` and `src/deepy/llm/events.py`.
- Adds subagent definition loading, built-in subagent prompts, and custom
  `.deepy/subagents` documentation.
- Adds a `test_shell` policy engine and tool wiring for test-oriented subagents.
- Affects tool registration in `src/deepy/tools/agents.py`, tool runtime policy
  in `src/deepy/tools/builtin.py`, and tool docs.
- Affects Rich/prompt-toolkit and Textual renderers that display tool and stream
  events.
- Adds tests for subagent discovery, tool exposure, lifecycle events, custom
  definition validation, MCP search inheritance, test-shell policy decisions,
  approval escalation, and result rendering.
