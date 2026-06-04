## 1. Subagent Definition Core

- [x] 1.1 Add built-in subagent definitions for `explore`, `reviewer`, and `tester` with focused prompts, descriptions, tool allowlists, and max-turn defaults.
- [x] 1.2 Add Markdown-plus-YAML-frontmatter parsing for custom subagents under `.deepy/subagents/*.md` and `~/.deepy/subagents/*.md`.
- [x] 1.3 Implement discovery precedence: project custom definitions, user custom definitions, then built-ins.
- [x] 1.4 Validate custom definitions for required `name`, `description`, prompt body, supported `model`, supported tools, MCP inheritance options, and bounded max turns.
- [x] 1.5 Add tests for built-in discovery, custom parsing, precedence, invalid definitions, and `.agents/skills` non-interference.

## 2. Test Shell Policy

- [x] 2.1 Add a constrained `test_shell` policy classifier with `allow`, `approval_required`, and `deny` decisions.
- [x] 2.2 Support common verification command families for Python/uv/pip, Node/package managers, Java/Maven/Gradle/Spring Boot, Rust, Go, frontend builds, curl, ping, mysql, Docker Compose, head, and tail.
- [x] 2.3 Reject shell composition and destructive/publishing commands by default.
- [x] 2.4 Execute allowed commands with bounded timeout, fixed cwd, captured stdout/stderr, exit code metadata, and output truncation.
- [x] 2.5 Add project-level policy extension points for additional allow and approval-required command patterns.
- [x] 2.6 Add tests for allowed, approval-required, denied, malformed, timeout, output truncation, and cross-platform command parsing cases.

## 3. Agent-As-Tool Integration

- [x] 3.1 Build subagent `Agent` instances with independent instructions, bounded tools, model inheritance or configured model override, and no nested subagent access.
- [x] 3.2 Expose enabled subagents to the main Deepy agent through OpenAI Agents SDK `Agent.as_tool()`.
- [x] 3.3 Route `explore` search-class MCP inheritance through Deepy's preferred MCP web/search tool metadata while avoiding broad MCP inheritance.
- [x] 3.4 Ensure `tester` receives `test_shell` but not source mutation tools by default.
- [x] 3.5 Add fake-runner tests for automatic subagent tool exposure, bounded inputs, tool allowlists, max turns, and nested spawning prevention.

## 4. Lifecycle Events And UI

- [x] 4.1 Add Deepy stream event kinds or metadata for subagent start, progress, completion, failure, and approval-required states.
- [x] 4.2 Normalize nested `Agent.as_tool(on_stream=...)` events into concise Deepy subagent lifecycle events.
- [x] 4.3 Render subagent lifecycle events in the stable terminal UI with compact `[Subagent]` labels and readable summaries.
- [x] 4.4 Keep nested subagent thinking and raw tool chatter from overwhelming the main transcript.
- [x] 4.5 Add session replay-safe storage for subagent summary events and final results.
- [x] 4.6 Add UI and session tests for started/completed/failed/approval-required rendering and replay behavior.

## 5. Approval Escalation

- [x] 5.1 Return structured `approval_required` results from `test_shell` for medium-risk commands.
- [x] 5.2 Teach the main agent prompt/tool guidance to escalate `test_shell` approval-required results through `AskUserQuestion`.
- [x] 5.3 Add a same-session approval token or approved-command retry path so approved commands can be executed without broadening raw shell access.
- [x] 5.4 Add tests covering approval prompt generation, approval retry, rejection, and no implicit execution after rejection.
- [x] 5.5 Document that full OpenAI Agents SDK interruption-resume approval mode is deferred.

## 6. Documentation And Validation

- [x] 6.1 Add user docs for built-in subagents, automatic delegation behavior, visible lifecycle output, and limits.
- [x] 6.2 Add custom subagent templates and examples under `.deepy/subagents` documentation.
- [x] 6.3 Document `test_shell` supported command families, approval-required examples, denied examples, and project policy extension.
- [x] 6.4 Update MCP docs to describe search-class MCP inheritance for `explore`.
- [x] 6.5 Run targeted tests for subagent discovery, tools, runner events, UI rendering, MCP search inheritance, and test-shell policy.
- [x] 6.6 Run `openspec validate add-subagent-support --strict`.
