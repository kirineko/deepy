from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deepy.utils import json as json_utils

from .builtin import ToolRuntime

if TYPE_CHECKING:
    from agents import Tool


def build_function_tools(
    runtime: ToolRuntime,
    *,
    preferred_mcp_web_search_tools: list[str] | None = None,
) -> list[Tool]:
    from agents.tool import FunctionTool

    async def invoke_shell(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.shell(_string_arg(args, "command"), timeout_ms=120_000)

    async def invoke_ask_user_question(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        questions = args.get("questions")
        return runtime.ask_user_question(questions if isinstance(questions, list) else [])

    async def invoke_read_file(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.read_file(
            _string_arg(args, "file_path"),
            start_line=_int_arg(args, "offset", 1),
            limit=_optional_int_arg(args, "limit"),
            pages=_optional_string_arg(args, "pages"),
        )

    async def invoke_edit_text(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.edit_text(
            _optional_string_arg(args, "file_path"),
            _string_arg(args, "old_string"),
            _string_arg(args, "new_string"),
            replace_all=_bool_arg(args, "replace_all", False),
            snippet_id=_optional_string_arg(args, "snippet_id"),
            expected_occurrences=_optional_int_arg(args, "expected_occurrences"),
        )

    async def invoke_write_file(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.write_file(
            _string_arg(args, "file_path"),
            args.get("content"),
            overwrite=_bool_arg(args, "overwrite", False),
            snapshot_id=_optional_string_arg(args, "snapshot_id"),
            expected_hash=_optional_string_arg(args, "expected_hash"),
        )

    async def invoke_apply_patch(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.apply_patch(args.get("operations"))

    async def invoke_web_search(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.web_search(_string_arg(args, "query"))

    async def invoke_web_fetch(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.web_fetch(_string_arg(args, "url"))

    async def invoke_load_skill(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.load_skill(_string_arg(args, "name"))

    async def invoke_todo_write(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.todo_write(args.get("todos") if "todos" in args else None)

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

    return [
        FunctionTool(
            name="shell",
            description=(
                "Execute commands in the current runtime shell. Match the runtime context's "
                "command dialect and path style."
            ),
            params_json_schema=SHELL_SCHEMA,
            on_invoke_tool=invoke_shell,
            strict_json_schema=False,
        ),
        FunctionTool(
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
        FunctionTool(
            name="read_file",
            description=(
                "Read a file or directory and record managed text snapshots for later edits. "
                "Use this before whole-file replacement or when you need context."
            ),
            params_json_schema=READ_FILE_SCHEMA,
            on_invoke_tool=invoke_read_file,
            strict_json_schema=True,
        ),
        FunctionTool(
            name="edit_text",
            description=(
                "Preferred tool for small single-file exact/string edits. Use file_path "
                "with old_string/new_string and expected_occurrences when possible; use "
                "snippet_id only to intentionally scope a partial-read range."
            ),
            params_json_schema=EDIT_TEXT_SCHEMA,
            on_invoke_tool=invoke_edit_text,
            strict_json_schema=True,
        ),
        FunctionTool(
            name="write_file",
            description=(
                "Create a new text file or explicitly replace a whole file. Existing-file "
                "replacement requires overwrite intent plus snapshot_id or expected_hash."
            ),
            params_json_schema=WRITE_FILE_SCHEMA,
            on_invoke_tool=invoke_write_file,
            strict_json_schema=True,
        ),
        FunctionTool(
            name="apply_patch",
            description=(
                "Batch structured file operations. Best for multiple edits in one file, "
                "multi-file edits, create/delete/move, or larger block replacements. "
                "Provide an operations array using create_file, replace_file, delete_file, "
                "move_file, replace_block, insert_before, insert_after, or replace_all."
            ),
            params_json_schema=APPLY_PATCH_SCHEMA,
            on_invoke_tool=invoke_apply_patch,
            strict_json_schema=True,
        ),
        FunctionTool(
            name="WebSearch",
            description=web_search_description,
            params_json_schema=WEB_SEARCH_SCHEMA,
            on_invoke_tool=invoke_web_search,
            strict_json_schema=False,
        ),
        FunctionTool(
            name="WebFetch",
            description="Fetch and extract readable content from a complete http or https URL.",
            params_json_schema=WEB_FETCH_SCHEMA,
            on_invoke_tool=invoke_web_fetch,
            strict_json_schema=False,
        ),
        FunctionTool(
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
        FunctionTool(
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


def _tool_args(raw_input: str) -> dict[str, Any]:
    try:
        parsed = json_utils.loads(raw_input or "{}")
    except json_utils.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


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
    },
    "required": ["command"],
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

READ_FILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Path to file or directory under the current project",
        },
        "offset": {
            "type": ["number", "null"],
            "description": "Line number to start reading from; null means start at line 1",
        },
        "limit": {
            "type": ["number", "null"],
            "description": "Number of lines to read; null means the default limit",
        },
        "pages": {
            "type": ["string", "null"],
            "description": "Page range for PDF files; null for non-PDF reads",
        },
    },
    "required": ["file_path", "offset", "limit", "pages"],
    "additionalProperties": False,
}

EDIT_TEXT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": ["string", "null"],
            "description": "Path to file. Use null when snippet_id scopes the edit.",
        },
        "snippet_id": {
            "type": ["string", "null"],
            "description": "Snippet id returned by read_file to scope the edit.",
        },
        "old_string": {
            "type": "string",
            "description": "Exact existing text to replace.",
        },
        "new_string": {
            "type": "string",
            "description": "Replacement text. Must change file content.",
        },
        "replace_all": {
            "type": "boolean",
            "description": "Replace all occurrences of old_string.",
        },
        "expected_occurrences": {
            "type": ["number", "null"],
            "description": "Expected number of matches; null skips this safety check.",
        },
    },
    "required": [
        "file_path",
        "snippet_id",
        "old_string",
        "new_string",
        "replace_all",
        "expected_occurrences",
    ],
    "additionalProperties": False,
}

WRITE_FILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Path to the file under the current project.",
        },
        "content": {
            "type": "string",
            "description": "Complete file content.",
        },
        "overwrite": {
            "type": "boolean",
            "description": "Explicit intent to replace an existing file.",
        },
        "snapshot_id": {
            "type": ["string", "null"],
            "description": "Snapshot id returned by read_file for existing-file replacement.",
        },
        "expected_hash": {
            "type": ["string", "null"],
            "description": "Content hash returned by read_file for existing-file replacement.",
        },
    },
    "required": ["file_path", "content", "overwrite", "snapshot_id", "expected_hash"],
    "additionalProperties": False,
}

APPLY_PATCH_OPERATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "create_file",
                "replace_file",
                "delete_file",
                "move_file",
                "replace_block",
                "insert_before",
                "insert_after",
                "replace_all",
            ],
            "description": "Structured file operation type.",
        },
        "file_path": {
            "type": "string",
            "description": "Path to the source or target file under the current project.",
        },
        "destination_path": {
            "type": ["string", "null"],
            "description": "Destination path for move_file; null for other operations.",
        },
        "content": {
            "type": ["string", "null"],
            "description": "File content for create_file/replace_file or inserted content for insert operations.",
        },
        "old_text": {
            "type": ["string", "null"],
            "description": "Exact text to replace for replace_block or replace_all.",
        },
        "new_text": {
            "type": ["string", "null"],
            "description": "Replacement text for replace_block or replace_all.",
        },
        "anchor": {
            "type": ["string", "null"],
            "description": "Exact anchor text for insert_before or insert_after.",
        },
        "expected_occurrences": {
            "type": ["integer", "null"],
            "description": "Expected match count for exact text or anchor operations.",
        },
        "replace_all": {
            "type": ["boolean", "null"],
            "description": "Whether to apply a block or insertion operation to every matching occurrence.",
        },
        "overwrite": {
            "type": ["boolean", "null"],
            "description": "Explicit overwrite intent for replace_file.",
        },
        "snapshot_id": {
            "type": ["string", "null"],
            "description": "Snapshot id returned by read_file for replace_file.",
        },
        "expected_hash": {
            "type": ["string", "null"],
            "description": "Content hash returned by read_file for replace_file.",
        },
    },
    "required": [
        "type",
        "file_path",
        "destination_path",
        "content",
        "old_text",
        "new_text",
        "anchor",
        "expected_occurrences",
        "replace_all",
        "overwrite",
        "snapshot_id",
        "expected_hash",
    ],
    "additionalProperties": False,
}

APPLY_PATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "operations": {
            "type": "array",
            "description": "Structured file operations to preflight and commit as one logical patch.",
            "items": APPLY_PATCH_OPERATION_SCHEMA,
        },
    },
    "required": ["operations"],
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
