## 1. Audit Policy And Configuration

- [x] 1.1 Add an `AuditMode` model with `normal`, `auto`, and `yolo` values plus validation helpers.
- [x] 1.2 Add TOML settings for the default audit mode and exact MCP safe-tool overrides.
- [x] 1.3 Add runtime state plumbing so interactive mode changes can override the persisted default for the active process.
- [x] 1.4 Add config/status diagnostics for invalid audit-mode values and stale MCP override entries.

## 2. Built-In Tool Approval Registration

- [x] 2.1 Add an audit policy helper that maps `Write`, `Update`, `shell`, and `task_stop` to SDK approval decisions.
- [x] 2.2 Register `needs_approval` callbacks on side-effecting `FunctionTool` definitions in `build_function_tools`.
- [x] 2.3 Preserve ungated behavior for `Search`, `Read`, `WebSearch`, `WebFetch`, `task_list`, `task_output`, `load_skill`, and `todo_write`.
- [x] 2.4 Preserve hard mutation guardrails after approval decisions, including workspace boundary, symlink escape, unsupported target, and stale-write checks.

## 3. SDK Interruption And Resume Flow

- [x] 3.1 Extend the runner to drain streamed events, detect SDK approval interruptions, and return or handle a pending-approval state.
- [x] 3.2 Implement approval resolution that converts results to `RunState`, applies approve/reject decisions, and resumes the original top-level run.
- [x] 3.3 Add model-visible rejection text that is distinct from ordinary tool failures and `AskUserQuestion` prompts.
- [x] 3.4 Ensure usage accounting, session reconciliation, MCP cleanup, and interrupt handling remain correct across paused and resumed runs.

## 4. MCP Audit Integration

- [x] 4.1 Pass SDK MCP `require_approval` settings when constructing stdio and Streamable HTTP MCP servers.
- [x] 4.2 Apply `normal`, `auto`, and `yolo` MCP approval behavior, including exact safe-tool overrides for `auto`.
- [x] 4.3 Include server name, model-visible tool name, original tool name, and arguments summary in MCP approval metadata for UI rendering.
- [x] 4.4 Preserve existing MCP lifecycle, duplicate-name handling, preferred web-search discovery, and subagent MCP inheritance.

## 5. Terminal UI

- [x] 5.1 Show the active audit mode in the stable prompt footer and status surfaces.
- [x] 5.2 Add `Shift+Tab` cycling for `normal -> auto -> yolo -> normal` without changing plain `Tab` completion behavior.
- [x] 5.3 Render built-in tool approval prompts with action kind, tool name, command/path/task id, and diff preview when available.
- [x] 5.4 Render MCP approval prompts with server, tool, and arguments summary.
- [x] 5.5 Route approve/reject choices back to the paused runner without submitting them as normal user messages.

## 6. Subagents

- [x] 6.1 Verify built-in tool approvals raised inside `Agent.as_tool()` subagents surface on the outer run.
- [x] 6.2 Verify MCP approvals raised inside subagents surface on the outer run.
- [x] 6.3 Add subagent-context labels to approval prompts when the SDK interruption exposes that context.

## 7. Tests

- [x] 7.1 Add focused tests for audit mode parsing, defaults, and runtime override behavior.
- [x] 7.2 Add focused tests for built-in tool `needs_approval` decisions in `normal`, `auto`, and `yolo`.
- [x] 7.3 Add runner tests for approve, reject, multiple pending approvals, and resumed streaming output.
- [x] 7.4 Add MCP construction tests for `require_approval` settings and safe-tool override matching.
- [x] 7.5 Add terminal UI tests for footer display, `Shift+Tab` cycling, and approval prompt rendering.
- [x] 7.6 Add subagent approval propagation tests using mocked SDK interruptions.

## 8. Documentation And Validation

- [x] 8.1 Update user-facing docs for audit modes, MCP safe-tool overrides, and approval UI behavior.
- [x] 8.2 Update subagent docs to remove the statement that full SDK approval interruption/resume is deferred.
- [x] 8.3 Run focused tests for affected modules.
- [x] 8.4 Run `openspec validate add-system-audit-modes --type change --strict`.
- [x] 8.5 Run project quality gates before implementation is considered complete.
