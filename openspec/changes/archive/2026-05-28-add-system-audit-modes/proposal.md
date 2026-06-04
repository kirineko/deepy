## Why

Deepy currently lets the model execute side-effecting built-in tools and MCP tools without a unified user approval boundary, which makes safe everyday use and high-autonomy use hard to distinguish. Adding system audit modes gives users an explicit runtime contract for file writes, command execution, background-task termination, and MCP tool calls while aligning the implementation with OpenAI Agents SDK approval interruptions.

## What Changes

- Add three system audit modes:
  - `normal`: require user approval for managed text writes, command execution, background task termination, and MCP tool calls.
  - `auto`: automatically approve managed text writes, but require approval for command execution, background task termination, and MCP tool calls unless the MCP tool is explicitly configured as safe/read-only.
  - `yolo`: automatically approve Deepy built-in side-effect tools and MCP tool calls, preserving the current high-autonomy behavior.
- Route approval-gated actions through OpenAI Agents SDK HITL interruptions and resume with `RunState.approve()` or `RunState.reject()`.
- Include MCP servers in the same audit boundary using the SDK MCP `require_approval` mechanism.
- Add terminal UI affordances for the active audit mode, pending approval panels, and `Shift+Tab` mode cycling.
- Add persistent configuration for default audit mode and MCP approval overrides.
- Preserve hard safety guardrails for workspace boundaries, symlink escapes, unsupported mutation targets, and SDK/runtime failures even when `yolo` is active.

## Capabilities

### New Capabilities

- `system-audit`: user-selectable audit modes, approval lifecycle, and shared approval semantics across built-in tools, subagents, and MCP tools.

### Modified Capabilities

- `tools`: built-in `Write`, `Update`, `shell`, and background task termination SHALL participate in system audit approval decisions.
- `mcp-support`: MCP tool calls SHALL participate in system audit approval decisions through OpenAI Agents SDK MCP approval support.
- `terminal-ui`: stable terminal UI SHALL expose audit mode status, approval prompts, and `Shift+Tab` mode switching.
- `configuration`: TOML configuration SHALL support default audit mode and MCP approval overrides.
- `subagents`: approval interruptions raised inside subagent tool execution SHALL surface to the outer Deepy session for user decision.

## Impact

- Affected code:
  - `src/deepy/tools/agents.py` for built-in tool `needs_approval` registration.
  - `src/deepy/llm/runner.py` for SDK interruption drain, approval state handling, and resumed streaming runs.
  - `src/deepy/mcp.py` for MCP `require_approval` configuration.
  - `src/deepy/config/settings.py` and related config commands for audit-mode settings.
  - `src/deepy/ui/prompt_input.py`, `src/deepy/ui/terminal.py`, and message/panel rendering helpers for mode switching and approval UI.
  - Subagent construction in `src/deepy/llm/agent.py` and related subagent docs/specs.
- Affected tests:
  - Focused tool approval policy tests.
  - Runner interruption/resume tests using mocked SDK results.
  - MCP approval policy configuration tests.
  - Terminal prompt key-binding and approval-panel rendering tests.
- Dependencies:
  - Uses OpenAI Agents SDK approval APIs already present in the project dependency surface.
