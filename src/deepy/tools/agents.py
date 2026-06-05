from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from deepy.audit import AuditPolicy

from .builtin import ToolRuntime
from .schema_compat import make_mimo_compatible_tool_schema
from .test_shell import TestShellDecision, TestShellPolicy, classify_test_shell_command
from .tool_args import (
    _bool_arg,
    _int_arg,
    _merge_tool_result_metadata,
    _optional_string_arg,
    _string_arg,
    _tool_args,
)

if TYPE_CHECKING:
    from agents import Tool

__all__ = ["build_function_tools", "make_mimo_compatible_tool_schema"]


def build_function_tools(
    runtime: ToolRuntime,
    *,
    mimo_schema_compatibility: bool = False,
    preferred_mcp_web_search_tools: list[str] | None = None,
    include_tools: set[str] | frozenset[str] | None = None,
    audit_policy: AuditPolicy | None = None,
) -> list[Tool]:
    from agents.tool import FunctionTool

    def make_function_tool(**kwargs: Any) -> FunctionTool:
        tool = FunctionTool(**kwargs)
        if mimo_schema_compatibility:
            tool.params_json_schema = make_mimo_compatible_tool_schema(tool.params_json_schema)
        return tool

    async def needs_text_write_approval(_context: object, _params: dict[str, Any], _call_id: str) -> bool:
        return bool(audit_policy and audit_policy.needs_approval("text_write"))

    async def needs_command_approval(_context: object, _params: dict[str, Any], _call_id: str) -> bool:
        return bool(audit_policy and audit_policy.needs_approval("command"))

    async def needs_background_task_control_approval(
        _context: object,
        _params: dict[str, Any],
        _call_id: str,
    ) -> bool:
        return bool(audit_policy and audit_policy.needs_approval("background_task_control"))

    async def needs_test_shell_approval(
        _context: object,
        params: dict[str, Any],
        _call_id: str,
    ) -> bool:
        if audit_policy is None or not audit_policy.needs_approval("command"):
            return False
        return _test_shell_decision(runtime, params).decision == "approval_required"

    async def invoke_shell(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "shell", SHELL_SCHEMA)
        if error is not None:
            return error
        result = await asyncio.to_thread(
            runtime.shell,
            _string_arg(args, "command"),
            timeout_ms=120_000,
            run_in_background=_bool_arg(args, "run_in_background", False),
        )
        return _merge_tool_result_metadata(result, repair_metadata)

    async def invoke_test_shell(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "test_shell", TEST_SHELL_SCHEMA)
        if error is not None:
            return error
        result = await asyncio.to_thread(
            runtime.test_shell,
            _string_arg(args, "command"),
            _int_arg(args, "timeout_ms", 120_000),
            approval_token=_optional_string_arg(args, "approval_token"),
            approved_by_audit=_test_shell_approved_by_audit(runtime, args, audit_policy),
        )
        return _merge_tool_result_metadata(result, repair_metadata)

    async def invoke_task_list(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "task_list", TASK_LIST_SCHEMA)
        if error is not None:
            return error
        return _merge_tool_result_metadata(
            runtime.task_list(
            active_only=_bool_arg(args, "active_only", False),
            limit=_int_arg(args, "limit", 20),
            ),
            repair_metadata,
        )

    async def invoke_task_output(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "task_output", TASK_OUTPUT_SCHEMA)
        if error is not None:
            return error
        result = await asyncio.to_thread(
            runtime.task_output,
            _string_arg(args, "task_id"),
            block=_bool_arg(args, "block", False),
            timeout=_int_arg(args, "timeout", 3),
        )
        return _merge_tool_result_metadata(result, repair_metadata)

    async def invoke_task_stop(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "task_stop", TASK_STOP_SCHEMA)
        if error is not None:
            return error
        return _merge_tool_result_metadata(
            runtime.task_stop(_string_arg(args, "task_id")),
            repair_metadata,
        )

    async def invoke_ask_user_question(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(
            raw_input,
            "AskUserQuestion",
            ASK_USER_QUESTION_SCHEMA,
        )
        if error is not None:
            return error
        questions = args.get("questions")
        return _merge_tool_result_metadata(
            runtime.ask_user_question(questions if isinstance(questions, list) else []),
            repair_metadata,
        )

    async def invoke_search(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "Search", SEARCH_SCHEMA)
        if error is not None:
            return error
        result = await asyncio.to_thread(
            runtime.search,
            _string_arg(args, "query"),
            path=_string_arg(args, "path") or ".",
            glob=_optional_string_arg(args, "glob"),
            mode=_string_arg(args, "mode") or "literal",
            output_mode=_string_arg(args, "output_mode") or "content",
            case_sensitive=_bool_arg(args, "case_sensitive", True),
            context=_int_arg(args, "context", 0),
            limit=_int_arg(args, "limit", 100),
            offset=_int_arg(args, "offset", 0),
            include_ignored=_bool_arg(args, "include_ignored", False),
        )
        return _merge_tool_result_metadata(result, repair_metadata)

    async def invoke_read(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "Read", READ_SCHEMA)
        if error is not None:
            return error
        result = await asyncio.to_thread(runtime.read, args)
        return _merge_tool_result_metadata(result, repair_metadata)

    async def invoke_write(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "Write", WRITE_SCHEMA)
        if error is not None:
            return error
        result = await asyncio.to_thread(
            runtime.write_v3,
            _string_arg(args, "path"),
            args.get("content"),
            overwrite=_bool_arg(args, "overwrite", False),
        )
        return _merge_tool_result_metadata(result, repair_metadata)

    async def invoke_update(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "Update", UPDATE_SCHEMA)
        if error is not None:
            return error
        result = await asyncio.to_thread(runtime.update, args)
        return _merge_tool_result_metadata(result, repair_metadata)

    async def invoke_web_search(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "WebSearch", WEB_SEARCH_SCHEMA)
        if error is not None:
            return error
        result = await asyncio.to_thread(runtime.web_search, _string_arg(args, "query"))
        return _merge_tool_result_metadata(result, repair_metadata)

    async def invoke_web_fetch(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "WebFetch", WEB_FETCH_SCHEMA)
        if error is not None:
            return error
        result = await asyncio.to_thread(runtime.web_fetch, _string_arg(args, "url"))
        return _merge_tool_result_metadata(result, repair_metadata)

    async def invoke_load_skill(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "load_skill", LOAD_SKILL_SCHEMA)
        if error is not None:
            return error
        result = await asyncio.to_thread(runtime.load_skill, _string_arg(args, "name"))
        return _merge_tool_result_metadata(result, repair_metadata)

    async def invoke_todo_write(_context: object, raw_input: str) -> str:
        args, error, repair_metadata = _tool_args(raw_input, "todo_write", TODO_WRITE_SCHEMA)
        if error is not None:
            return error
        return _merge_tool_result_metadata(
            runtime.todo_write(args.get("todos") if "todos" in args else None),
            repair_metadata,
        )

    web_search_description = (
        "Perform web searching using a natural language query. Use a small number of "
        "targeted searches, then stop and synthesize once enough sources are available; "
        "prefer WebFetch for exact URLs."
    )
    if preferred_mcp_web_search_tools:
        web_search_description = (
            "Built-in fallback web search. Preferred MCP web search tools are available: "
            + ", ".join(preferred_mcp_web_search_tools)
            + ". Prefer those MCP tools first for web/current-information searches; use "
            "this built-in WebSearch if MCP search is unavailable, fails, or the user "
            "explicitly requests Deepy's built-in search. Prefer WebFetch for exact URLs."
        )

    tools = [
        make_function_tool(
            name="shell",
            description=(
                "Execute commands in the current runtime shell. Match the runtime context's "
                "command dialect and path style. Set run_in_background only for long-running "
                "servers, watchers, or jobs that should continue while the assistant responds."
            ),
            params_json_schema=SHELL_SCHEMA,
            on_invoke_tool=invoke_shell,
            strict_json_schema=False,
            needs_approval=needs_command_approval,
        ),
        make_function_tool(
            name="test_shell",
            description=(
                "Run constrained development verification commands for tester subagents. "
                "The command is parsed without an unrestricted shell, classified by policy, "
                "and medium-risk commands are routed through Deepy's audit approval flow."
            ),
            params_json_schema=TEST_SHELL_SCHEMA,
            on_invoke_tool=invoke_test_shell,
            strict_json_schema=True,
            needs_approval=needs_test_shell_approval,
        ),
        make_function_tool(
            name="task_list",
            description=(
                "List background shell tasks started with shell run_in_background. Use this to "
                "find task ids and current status before inspecting or stopping a task."
            ),
            params_json_schema=TASK_LIST_SCHEMA,
            on_invoke_tool=invoke_task_list,
            strict_json_schema=False,
        ),
        make_function_tool(
            name="task_output",
            description=(
                "Read the captured output for a background shell task. Use block=true when you "
                "need to wait briefly for completion or new output."
            ),
            params_json_schema=TASK_OUTPUT_SCHEMA,
            on_invoke_tool=invoke_task_output,
            strict_json_schema=False,
        ),
        make_function_tool(
            name="task_stop",
            description="Request termination for a background shell task by task id.",
            params_json_schema=TASK_STOP_SCHEMA,
            on_invoke_tool=invoke_task_stop,
            strict_json_schema=False,
            needs_approval=needs_background_task_control_approval,
        ),
        make_function_tool(
            name="AskUserQuestion",
            description=(
                "当用户意图、范围、偏好、实现路线、高影响取舍或必要批准会明显影响结果时，"
                "use this tool to pause and ask a concise question. Match the user's language; "
                "for Chinese requests, ask in Chinese. If one option is recommended, list it first "
                "and mark it as recommended. Do not ask for low-impact details when a reasonable "
                "assumption can keep progress moving."
            ),
            params_json_schema=ASK_USER_QUESTION_SCHEMA,
            on_invoke_tool=invoke_ask_user_question,
            strict_json_schema=False,
        ),
        make_function_tool(
            name="Search",
            description=(
                "Search local project files without shell grep or rg. Prefer this for repository "
                "code/text search. Defaults to literal content search; use regex mode only when "
                "a regular expression is intentional."
            ),
            params_json_schema=SEARCH_SCHEMA,
            on_invoke_tool=invoke_search,
            strict_json_schema=True,
        ),
        make_function_tool(
            name="Read",
            description=(
                "Read one or more project files or directories. Use files=[...] to read "
                'multiple targets in one call; use quoted range strings like {"path": '
                '"src/app.py", "range": "80-120"} or {"files": [{"path": '
                '"src/app.py", "range": "80-120"}]}. Use head/tail/offset/limit '
                "for other slices."
            ),
            params_json_schema=READ_SCHEMA,
            on_invoke_tool=invoke_read,
            strict_json_schema=False,
        ),
        make_function_tool(
            name="Write",
            description=(
                "Create a new text file or replace a whole existing text file. For existing "
                "files, set overwrite=true after reading the target in this session."
            ),
            params_json_schema=WRITE_SCHEMA,
            on_invoke_tool=invoke_write,
            strict_json_schema=False,
            needs_approval=needs_text_write_approval,
        ),
        make_function_tool(
            name="Update",
            description=(
                "Apply exact text replacements. Use one old/new pair, path+edits for multiple "
                "edits in one file, or edits=[{path, old, new}] for multi-file updates."
            ),
            params_json_schema=UPDATE_SCHEMA,
            on_invoke_tool=invoke_update,
            strict_json_schema=False,
            needs_approval=needs_text_write_approval,
        ),
        make_function_tool(
            name="WebSearch",
            description=web_search_description,
            params_json_schema=WEB_SEARCH_SCHEMA,
            on_invoke_tool=invoke_web_search,
            strict_json_schema=False,
        ),
        make_function_tool(
            name="WebFetch",
            description="Fetch and extract readable content from a complete http or https URL.",
            params_json_schema=WEB_FETCH_SCHEMA,
            on_invoke_tool=invoke_web_fetch,
            strict_json_schema=False,
        ),
        make_function_tool(
            name="load_skill",
            description=(
                "Load the complete instructions for an available Agent Skill by name. Use this "
                "when the user's task matches a skill listed in Available skills before relying "
                "on that skill's workflow, scripts, references, or assets."
            ),
            params_json_schema=LOAD_SKILL_SCHEMA,
            on_invoke_tool=invoke_load_skill,
            strict_json_schema=False,
        ),
        make_function_tool(
            name="todo_write",
            description=(
                "Create, replace, read, or clear the session todo list for complex multi-step "
                "work. Use it for meaningful task tracking, not simple questions or one-step edits. "
                "Provide the complete todo list when updating; omit todos only to read current state."
            ),
            params_json_schema=TODO_WRITE_SCHEMA,
            on_invoke_tool=invoke_todo_write,
            strict_json_schema=False,
        ),
    ]
    if include_tools is not None:
        allowed = set(include_tools)
        return [tool for tool in tools if tool.name in allowed]
    return [tool for tool in tools if tool.name != "test_shell"]


def _test_shell_policy(runtime: ToolRuntime) -> TestShellPolicy:
    return TestShellPolicy(
        allow_patterns=runtime.settings.tools.test_shell.allow_patterns,
        approval_required_patterns=runtime.settings.tools.test_shell.approval_required_patterns,
    )


def _test_shell_decision(runtime: ToolRuntime, args: dict[str, Any]) -> TestShellDecision:
    return classify_test_shell_command(
        _string_arg(args, "command"),
        policy=_test_shell_policy(runtime),
        platform_name=runtime.platform_name,
    )


def _test_shell_approved_by_audit(
    runtime: ToolRuntime,
    args: dict[str, Any],
    audit_policy: AuditPolicy | None,
) -> bool:
    if audit_policy is None:
        return False
    return _test_shell_decision(runtime, args).decision == "approval_required"


SHELL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "The shell command to execute",
        },
        "description": {
            "type": "string",
            "description": (
                "Clear, concise description of what this command does in active voice. Never use "
                'words like "complex" or "risk" in the description - just describe what it does.'
            ),
        },
        "run_in_background": {
            "type": "boolean",
            "description": (
                "Run the command as a managed background task and return immediately. Use only "
                "for long-running commands such as servers, watchers, or jobs to inspect later."
            ),
        },
    },
    "required": ["command"],
    "additionalProperties": False,
}

TEST_SHELL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "The verification command to classify and execute if allowed.",
        },
        "description": {
            "type": "string",
            "description": "Short description of the verification purpose.",
        },
        "timeout_ms": {
            "type": "integer",
            "description": "Maximum runtime in milliseconds, capped by Deepy.",
        },
        "approval_token": {
            "type": ["string", "null"],
            "description": (
                "Approval token returned by a prior approval_required result for the same command."
            ),
        },
    },
    "required": ["command"],
    "additionalProperties": False,
}

TASK_LIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "active_only": {
            "type": "boolean",
            "description": "When true, return only currently running background tasks.",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of background tasks to return.",
        },
    },
    "required": [],
    "additionalProperties": False,
}

TASK_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "Background task id returned by shell run_in_background or task_list.",
        },
        "block": {
            "type": "boolean",
            "description": "Wait briefly before reading output, useful for short jobs that may finish soon.",
        },
        "timeout": {
            "type": "integer",
            "description": "Maximum seconds to wait when block is true, capped by Deepy for responsiveness.",
        },
    },
    "required": ["task_id"],
    "additionalProperties": False,
}

TASK_STOP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "Background task id to stop.",
        },
    },
    "required": ["task_id"],
    "additionalProperties": False,
}
ASK_USER_QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "description": "Questions to present to the user. Usually only one question is needed at a time.",
            "items": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user.",
                    },
                    "multiSelect": {
                        "type": "boolean",
                        "description": "Whether the user may choose multiple options.",
                    },
                    "options": {
                        "type": "array",
                        "description": "A list of predefined options for the user to choose from.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {
                                    "type": "string",
                                    "description": "The display text for the option.",
                                },
                                "description": {
                                    "type": "string",
                                    "description": (
                                        "A detailed explanation or hint about this option to help the "
                                        "user understand what happens if they choose it."
                                    ),
                                },
                            },
                            "required": ["label"],
                        },
                    },
                },
                "required": ["question", "options"],
            },
        },
    },
    "required": ["questions"],
    "additionalProperties": False,
}

SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Literal string or regex pattern to search for in local project files.",
        },
        "path": {
            "type": "string",
            "description": "Project-relative file or directory path to search. Use '.' for the project.",
        },
        "glob": {
            "type": ["string", "null"],
            "description": "Optional glob filter against project-relative paths, such as '*.py'.",
        },
        "mode": {
            "type": "string",
            "enum": ["literal", "regex"],
            "description": "Search mode. Use literal by default; use regex only intentionally.",
        },
        "output_mode": {
            "type": "string",
            "enum": ["content", "files", "count"],
            "description": "Return matching lines, matching file paths, or per-file counts.",
        },
        "case_sensitive": {
            "type": "boolean",
            "description": "Whether matching is case-sensitive.",
        },
        "context": {
            "type": "integer",
            "description": "Number of context lines before and after content matches.",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of result entries to return. Use 0 for unlimited sparingly.",
        },
        "offset": {
            "type": "integer",
            "description": "Number of result entries to skip for pagination.",
        },
        "include_ignored": {
            "type": "boolean",
            "description": "Whether to include gitignored files. Sensitive files are still filtered.",
        },
    },
    "required": [
        "query",
        "path",
        "glob",
        "mode",
        "output_mode",
        "case_sensitive",
        "context",
        "limit",
        "offset",
        "include_ignored",
    ],
    "additionalProperties": False,
}

READ_TARGET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Path to read."},
        "range": {"type": "string", "description": "Optional 1-indexed inclusive line range like '20-80'."},
        "head": {"type": "integer", "description": "Optional number of leading lines to read."},
        "tail": {"type": "integer", "description": "Optional number of trailing lines to read."},
        "offset": {"type": "integer", "description": "Optional 1-indexed start line."},
        "limit": {"type": "integer", "description": "Optional number of lines to read."},
        "pages": {"type": "string", "description": "Optional PDF page range."},
    },
    "required": ["path"],
    "additionalProperties": False,
}

READ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Path to read when reading one target."},
        "files": {
            "type": "array",
            "description": "Targets to read in one call.",
            "items": READ_TARGET_SCHEMA,
        },
        "range": {"type": "string", "description": "Optional 1-indexed inclusive line range like '20-80'."},
        "head": {"type": "integer", "description": "Optional number of leading lines to read."},
        "tail": {"type": "integer", "description": "Optional number of trailing lines to read."},
        "offset": {"type": "integer", "description": "Optional 1-indexed start line."},
        "limit": {"type": "integer", "description": "Optional number of lines to read."},
        "pages": {"type": "string", "description": "Optional PDF page range."},
    },
    "required": [],
    "additionalProperties": False,
}

WRITE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Path to create or replace."},
        "content": {"type": "string", "description": "Complete file content."},
        "overwrite": {"type": "boolean", "description": "Set true to replace an existing file."},
    },
    "required": ["path", "content"],
    "additionalProperties": False,
}

UPDATE_EDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Target path; optional when parent path is provided."},
        "old": {"type": "string", "description": "Exact text to replace."},
        "new": {"type": "string", "description": "Replacement text."},
        "replace_all": {"type": "boolean", "description": "Replace every exact old match."},
        "expected_occurrences": {"type": "integer", "description": "Expected match count."},
    },
    "required": ["old", "new"],
    "additionalProperties": False,
}

UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Target path for one file."},
        "old": {"type": "string", "description": "Exact text to replace for a single edit."},
        "new": {"type": "string", "description": "Replacement text for a single edit."},
        "edits": {
            "type": "array",
            "description": "Ordered exact replacements; each edit can include its own path.",
            "items": UPDATE_EDIT_SCHEMA,
        },
        "replace_all": {"type": "boolean", "description": "Default replace_all for edits."},
        "expected_occurrences": {"type": "integer", "description": "Default expected match count for edits."},
    },
    "required": [],
    "additionalProperties": False,
}

WEB_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "A search query phrased as a clear, specific natural language question or statement "
                "that includes key context."
            ),
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}

WEB_FETCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "A complete http or https URL to fetch.",
        },
    },
    "required": ["url"],
    "additionalProperties": False,
}

LOAD_SKILL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "The exact skill name from the Available skills list.",
        },
    },
    "required": ["name"],
    "additionalProperties": False,
}
TODO_WRITE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "todos": {
            "type": "array",
            "description": (
                "Complete replacement todo list. Omit this property to read the current todo list; "
                "pass an empty list to clear it."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Stable id for this todo item.",
                    },
                    "content": {
                        "type": "string",
                        "description": "User-facing task text.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                    },
                },
                "required": ["id", "content", "status"],
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}
