from __future__ import annotations

from typing import Any

from deepy.utils import json as json_utils

from .builtin import ToolRuntime


def build_function_tools(runtime: ToolRuntime) -> list[object]:
    from agents.tool import FunctionTool

    async def invoke_shell(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.shell(_string_arg(args, "command"), timeout_ms=120_000)

    async def invoke_ask_user_question(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        questions = args.get("questions")
        return runtime.ask_user_question(questions if isinstance(questions, list) else [])

    async def invoke_read(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.read(
            _string_arg(args, "file_path"),
            start_line=_int_arg(args, "offset", 1),
            limit=_optional_int_arg(args, "limit"),
            pages=_optional_string_arg(args, "pages"),
        )

    async def invoke_modify(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.modify(
            _optional_string_arg(args, "file_path"),
            content=args.get("content"),
            old=_nullable_string_arg(args, "old_string"),
            new=_nullable_string_arg(args, "new_string"),
            replace_all=_bool_arg(args, "replace_all", False),
            snippet_id=_optional_string_arg(args, "snippet_id"),
        )

    async def invoke_web_search(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.web_search(_string_arg(args, "query"))

    async def invoke_web_fetch(_context: object, raw_input: str) -> str:
        args = _tool_args(raw_input)
        return runtime.web_fetch(_string_arg(args, "url"))

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
            name="read",
            description="Read files from the filesystem (text, images, PDFs, notebooks).",
            params_json_schema=READ_SCHEMA,
            on_invoke_tool=invoke_read,
            strict_json_schema=False,
        ),
        FunctionTool(
            name="modify",
            description=(
                "Create new files or edit existing files. Use content only for files that do not "
                "exist. For existing files, read first and use old_string/new_string."
            ),
            params_json_schema=MODIFY_SCHEMA,
            on_invoke_tool=invoke_modify,
            strict_json_schema=False,
        ),
        FunctionTool(
            name="WebSearch",
            description=(
                "Perform web searching using a natural language query. Use a small number of "
                "targeted searches, then stop and synthesize once enough sources are available; "
                "prefer WebFetch for exact URLs."
            ),
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
    return value if isinstance(value, str) and value else None


def _nullable_string_arg(args: dict[str, Any], name: str) -> str | None:
    value = args.get(name)
    return value if isinstance(value, str) else None


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

READ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "UNIX-style path to file",
        },
        "offset": {
            "type": "number",
            "description": "Line number to start reading from",
        },
        "limit": {
            "type": "number",
            "description": "Number of lines to read",
        },
        "pages": {
            "type": "string",
            "description": (
                'Page range for PDF files (e.g., "1-5", "3", "10-20"). Only applicable to PDF files.'
            ),
        },
    },
    "required": ["file_path"],
    "additionalProperties": False,
}

MODIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Absolute path to file. Optional when snippet_id scopes an existing edit.",
        },
        "snippet_id": {
            "type": "string",
            "description": (
                "Snippet id returned by the Read or Modify tool to scope the search range after "
                "a partial read."
            ),
        },
        "content": {
            "type": "string",
            "description": (
                "Complete content for a new file only. Do not use for existing files; read the file "
                "and use old_string/new_string instead."
            ),
        },
        "old_string": {
            "type": "string",
            "description": "Exact existing text to replace inside the file or snippet scope",
        },
        "new_string": {
            "type": "string",
            "description": "Replacement text for old_string",
        },
        "replace_all": {
            "type": "boolean",
            "description": "Replace all occurrences of old_string (default false)",
            "default": False,
        },
        "expected_occurrences": {
            "type": "number",
            "description": (
                "Expected number of matches, especially useful as a safety check with replace_all"
            ),
        },
    },
    "required": [],
    "additionalProperties": False,
}

EDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Absolute path to file. Optional when snippet_id is provided.",
        },
        "snippet_id": {
            "type": "string",
            "description": (
                "Snippet id returned by the Read or Edit tool to scope the search range after a partial read."
            ),
        },
        "old_string": {
            "type": "string",
            "description": "Exact text to replace inside the file or snippet scope",
        },
        "new_string": {
            "type": "string",
            "description": "Replacement text (must differ from old_string)",
        },
        "replace_all": {
            "type": "boolean",
            "description": "Replace all occurences of old_string (default false)",
            "default": False,
        },
        "expected_occurrences": {
            "type": "number",
            "description": (
                "Expected number of matches, especially useful as a safety check with replace_all"
            ),
        },
    },
    "required": ["old_string", "new_string"],
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
