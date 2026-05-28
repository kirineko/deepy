from __future__ import annotations

import asyncio
import re
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from deepy.audit import AuditPolicy
from deepy.utils import json as json_utils

from .builtin import ToolRuntime
from .result import ToolResult

if TYPE_CHECKING:
    from agents import Tool


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
                "and may return approval_required instead of executing."
            ),
            params_json_schema=TEST_SHELL_SCHEMA,
            on_invoke_tool=invoke_test_shell,
            strict_json_schema=True,
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


def make_mimo_compatible_tool_schema(schema: dict[str, Any]) -> dict[str, Any]:
    compatible = deepcopy(schema)
    _remove_nullable_required_fields(compatible)
    return compatible


def _remove_nullable_required_fields(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _remove_nullable_required_fields(item)
        return
    if not isinstance(value, dict):
        return

    properties = value.get("properties")
    required = value.get("required")
    if isinstance(properties, dict) and isinstance(required, list):
        value["required"] = [
            field
            for field in required
            if not (
                isinstance(field, str)
                and isinstance(properties.get(field), dict)
                and _schema_type_allows_null(properties[field])
            )
        ]

    if _schema_type_allows_null(value):
        schema_type = value["type"]
        non_null_types = [item for item in schema_type if item != "null"]
        if len(non_null_types) == 1:
            value["type"] = non_null_types[0]
        elif non_null_types:
            value["type"] = non_null_types

    for item in value.values():
        _remove_nullable_required_fields(item)


def _schema_type_allows_null(schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    return isinstance(schema_type, list) and "null" in schema_type


def _tool_args(
    raw_input: str,
    tool_name: str,
    schema: dict[str, Any],
) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    try:
        parsed = json_utils.loads(raw_input or "{}")
    except json_utils.JSONDecodeError as exc:
        repaired, repair_metadata = _repair_tool_arguments(raw_input or "", tool_name=tool_name)
        if repaired is not None:
            try:
                parsed = json_utils.loads(repaired)
            except json_utils.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                validation_error = _validate_args_against_schema(parsed, schema)
                if validation_error is None:
                    return parsed, None, repair_metadata
        return {}, _invalid_tool_arguments_result(tool_name, exc, repair_metadata), {}
    if not isinstance(parsed, dict):
        return {}, ToolResult.error_result(
            tool_name,
            "Invalid tool arguments JSON: expected a JSON object matching the tool schema.",
            metadata={
                "error_code": "invalid_arguments",
                "retryable": True,
                "recoverable": True,
                "repairAttempted": False,
                "repairApplied": False,
                "recovery": "Pass exactly one JSON object as the tool arguments.",
            },
        ).to_json(), {}
    return parsed, None, {}


def _invalid_tool_arguments_result(
    tool_name: str,
    exc: json_utils.JSONDecodeError,
    repair_metadata: dict[str, Any] | None = None,
) -> str:
    return ToolResult.error_result(
        tool_name,
        "Invalid tool arguments JSON: "
        f"{exc.msg} at line {exc.lineno} column {exc.colno}.",
        metadata={
            "error_code": "invalid_arguments",
            "retryable": True,
            "recoverable": True,
            "parse_error": str(exc),
            "line": exc.lineno,
            "column": exc.colno,
            "position": exc.pos,
            "repairAttempted": bool(repair_metadata),
            "repairApplied": False,
            **(repair_metadata or {}),
            "recovery": (
                "Pass a valid JSON object matching the tool schema."
            ),
        },
    ).to_json()


def _repair_tool_arguments(raw_input: str, *, tool_name: str) -> tuple[str | None, dict[str, Any]]:
    repaired = raw_input.strip()
    if not repaired:
        return None, {}
    operations: list[str] = []
    if tool_name == "Read":
        repaired, changed = _quote_unquoted_read_ranges(repaired)
        if changed:
            operations.append("read_range_string")
    repaired, changed = _replace_unquoted_python_literals(repaired)
    if changed:
        operations.append("json_literals")
    repaired, changed = _remove_trailing_commas(repaired)
    if changed:
        operations.append("trailing_commas")
    if not operations:
        return None, {}
    return repaired, {
        "argumentRepair": True,
        "repairAttempted": True,
        "repairApplied": True,
        "repairOperations": operations,
    }


def _quote_unquoted_read_ranges(value: str) -> tuple[str, bool]:
    pattern = re.compile(
        r'(?P<lead>(?:^|[,{]\s*))(?P<key>"range"|range)\s*:\s*'
        r'(?P<start>[1-9]\d*)\s*-\s*(?P<end>[1-9]\d*)'
        r'(?P<trail>\s*(?=[,}\]]))'
    )

    def replace(match: re.Match[str]) -> str:
        return (
            f'{match.group("lead")}"range": '
            f'"{match.group("start")}-{match.group("end")}"'
            f'{match.group("trail")}'
        )

    repaired, count = pattern.subn(replace, value)
    return repaired, count > 0


def _replace_unquoted_python_literals(value: str) -> tuple[str, bool]:
    replacements = {"None": "null", "True": "true", "False": "false"}
    output: list[str] = []
    changed = False
    index = 0
    in_string = False
    escape = False
    while index < len(value):
        char = value[index]
        if in_string:
            output.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        replaced = False
        for source, target in replacements.items():
            end = index + len(source)
            if (
                value.startswith(source, index)
                and (index == 0 or not _is_identifier_char(value[index - 1]))
                and (end >= len(value) or not _is_identifier_char(value[end]))
            ):
                output.append(target)
                index = end
                changed = True
                replaced = True
                break
        if not replaced:
            output.append(char)
            index += 1
    return "".join(output), changed


def _remove_trailing_commas(value: str) -> tuple[str, bool]:
    output: list[str] = []
    changed = False
    index = 0
    in_string = False
    escape = False
    while index < len(value):
        char = value[index]
        if in_string:
            output.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == ",":
            next_index = index + 1
            while next_index < len(value) and value[next_index].isspace():
                next_index += 1
            if next_index < len(value) and value[next_index] in "}]":
                changed = True
                index += 1
                continue
        output.append(char)
        index += 1
    return "".join(output), changed


def _is_identifier_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def _validate_args_against_schema(args: dict[str, Any], schema: dict[str, Any]) -> str | None:
    required = schema.get("required")
    if isinstance(required, list):
        for field in required:
            if isinstance(field, str) and field not in args:
                return f"Missing required field: {field}"
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None
    if schema.get("additionalProperties") is False:
        extra = sorted(set(args) - set(properties))
        if extra:
            return f"Unsupported fields: {', '.join(extra)}"
    for key, value in args.items():
        field_schema = properties.get(key)
        if isinstance(field_schema, dict) and not _schema_value_matches(value, field_schema):
            return f"Invalid type for field: {key}"
    return None


def _schema_value_matches(value: Any, schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    allowed = schema_type if isinstance(schema_type, list) else [schema_type]
    if value is None:
        return "null" in allowed
    if "string" in allowed and isinstance(value, str):
        return _schema_enum_matches(value, schema)
    if "boolean" in allowed and isinstance(value, bool):
        return _schema_enum_matches(value, schema)
    if "integer" in allowed and isinstance(value, int) and not isinstance(value, bool):
        return _schema_enum_matches(value, schema)
    if "number" in allowed and isinstance(value, int | float) and not isinstance(value, bool):
        return _schema_enum_matches(value, schema)
    if "array" in allowed and isinstance(value, list):
        item_schema = schema.get("items")
        return not isinstance(item_schema, dict) or all(_schema_value_matches(item, item_schema) for item in value)
    if "object" in allowed and isinstance(value, dict):
        nested_error = _validate_args_against_schema(value, schema)
        return nested_error is None
    return False


def _schema_enum_matches(value: Any, schema: dict[str, Any]) -> bool:
    enum = schema.get("enum")
    return not isinstance(enum, list) or value in enum


def _merge_tool_result_metadata(result: str, metadata: dict[str, Any]) -> str:
    if not metadata:
        return result
    try:
        payload = json_utils.loads(result)
    except json_utils.JSONDecodeError:
        return result
    if not isinstance(payload, dict):
        return result
    result_metadata = payload.get("metadata")
    merged = result_metadata if isinstance(result_metadata, dict) else {}
    payload["metadata"] = {**merged, **metadata}
    return json_utils.dumps(payload)


def _string_arg(args: dict[str, Any], name: str) -> str:
    value = args.get(name)
    return value if isinstance(value, str) else ""


def _optional_string_arg(args: dict[str, Any], name: str) -> str | None:
    value = args.get(name)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped.casefold() in {"null", "none", "undefined"}:
        return None
    return value


def _int_arg(args: dict[str, Any], name: str, default: int) -> int:
    value = args.get(name)
    if isinstance(value, bool):
        return default
    return value if isinstance(value, int) else default


def _optional_int_arg(args: dict[str, Any], name: str) -> int | None:
    value = args.get(name)
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _bool_arg(args: dict[str, Any], name: str, default: bool) -> bool:
    value = args.get(name)
    return value if isinstance(value, bool) else default


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
