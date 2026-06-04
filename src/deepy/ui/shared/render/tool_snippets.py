from __future__ import annotations

import re
from typing import Any

from deepy.utils import json as json_utils
from deepy.ui.shared.render.tool_text import (
    _shorten_project_path,
    _string_key_dict,
    _string_or_none,
    _text_size_summary,
    _truncate,
)

FILE_MUTATION_TOOLS = {"Update", "Write"}


def build_tool_params_snippet(
    tool_function: object | None, *, project_root: str | None = None
) -> str:
    tool_params = _string_key_dict(tool_function)
    if tool_params is None:
        return ""
    args = tool_params.get("arguments")
    tool_name = tool_params.get("name")
    if not isinstance(args, str) or not args.strip():
        return ""
    try:
        parsed = json_utils.loads(args)
    except json_utils.JSONDecodeError:
        if isinstance(tool_name, str) and tool_name in FILE_MUTATION_TOOLS:
            return _format_malformed_file_tool_params_snippet(
                tool_name,
                args,
                project_root=project_root,
            )
        return args.strip()
    if tool_name == "Read":
        return _format_read_params_snippet(parsed, project_root=project_root) or args.strip()
    parsed_params = _string_key_dict(parsed)
    if parsed_params is None:
        return args.strip()
    return _format_tool_params_snippet(
        tool_name if isinstance(tool_name, str) else None,
        parsed_params,
        project_root=project_root,
    )


def _format_tool_params_snippet(
    tool_name: str | None,
    args: dict[str, Any],
    *,
    project_root: str | None,
) -> str:
    if tool_name == "AskUserQuestion":
        return ""

    if tool_name == "todo_write":
        todos = args.get("todos")
        if isinstance(todos, list):
            count = len(todos)
            label = "item" if count == 1 else "items"
            return f"{count} {label}"
        return "read current list"

    if tool_name == "Write" and "content" in args:
        return _format_write_params_snippet(args, project_root=project_root)
    if tool_name == "Update":
        return _format_update_params_snippet(args, project_root=project_root)
    if tool_name == "Search":
        return _format_search_params_snippet(args, project_root=project_root)
    if tool_name == "Read":
        return _format_read_params_snippet(args, project_root=project_root)

    if tool_name == "shell":
        command = args.get("command")
        description = args.get("description")
        command_text = command.strip() if isinstance(command, str) else ""
        description_text = description.strip() if isinstance(description, str) else ""
        if command_text and description_text:
            return f"{command_text}  # {description_text}"
        return command_text or description_text

    first_key = next(iter(args), "")
    if not first_key:
        return ""
    value = args[first_key]
    text = value if isinstance(value, str) else json_utils.dumps(value)
    if tool_name == "Read":
        return _shorten_project_path(text, project_root=project_root)
    return text


def _format_read_params_snippet(value: Any, *, project_root: str | None) -> str:
    paths = _read_paths_from_value(value)
    if not paths:
        return ""
    return ", ".join(_shorten_project_path(path, project_root=project_root) for path in paths)


def _read_paths_from_value(value: Any) -> list[str]:
    paths: list[str] = []
    _collect_read_paths(value, paths)
    return paths


def _collect_read_paths(value: Any, paths: list[str]) -> None:
    if isinstance(value, str):
        _append_unique_path(paths, value)
        return
    if isinstance(value, list):
        for item in value:
            _collect_read_paths(item, paths)
        return
    if not isinstance(value, dict):
        return
    for key in ("path", "file_path"):
        path = _string_or_none(value.get(key))
        if path:
            _append_unique_path(paths, path)
    for key in ("paths", "files"):
        items = value.get(key)
        if isinstance(items, list):
            for item in items:
                _collect_read_paths(item, paths)


def _append_unique_path(paths: list[str], path: str) -> None:
    if path not in paths:
        paths.append(path)


def _format_write_params_snippet(args: dict[str, Any], *, project_root: str | None) -> str:
    path = _string_or_none(args.get("file_path")) or _string_or_none(args.get("path"))
    content = args.get("content")
    path_text = _shorten_project_path(path, project_root=project_root) if path else "file"
    if not isinstance(content, str):
        return path_text
    return f"{path_text} ({_text_size_summary(content)})"


def _format_update_params_snippet(args: dict[str, Any], *, project_root: str | None) -> str:
    paths: list[str] = []
    edit_count = 0
    root_path = _string_or_none(args.get("path")) or _string_or_none(args.get("file_path"))
    edits = args.get("edits")
    if isinstance(edits, list):
        for item in edits:
            if not isinstance(item, dict):
                continue
            edit_count += 1
            path = _string_or_none(item.get("path")) or _string_or_none(item.get("file_path")) or root_path
            if path and path not in paths:
                paths.append(path)
    else:
        edit_count = 1 if ("old" in args or "new" in args) else 0
        if root_path:
            paths.append(root_path)
    if not paths:
        return f"{edit_count} edits" if edit_count else "edits"
    edit_label = "edit" if edit_count == 1 else "edits"
    file_label = "file" if len(paths) == 1 else "files"
    return f"{edit_count} {edit_label}, {len(paths)} {file_label}"


def _format_malformed_file_tool_params_snippet(
    tool_name: str,
    arguments: str,
    *,
    project_root: str | None,
) -> str:
    path = _extract_json_like_string_field(arguments, "file_path")
    if path is None:
        path = _extract_json_like_string_field(arguments, "path")
    path_text = _shorten_project_path(path, project_root=project_root) if path else "file"
    return f"{path_text} (malformed args)"


def _extract_json_like_string_field(arguments: str, field: str) -> str | None:
    match = _json_like_string_field_pattern(field).search(arguments)
    if match is None:
        return None
    return _unescape_json_like_string(match.group("value"))


def _json_like_string_field_pattern(field: str) -> re.Pattern[str]:
    escaped = re.escape(field)
    return re.compile(rf'"{escaped}"\s*:\s*"(?P<value>(?:\\.|[^"\\])*)"')


def _unescape_json_like_string(value: str) -> str:
    try:
        parsed = json_utils.loads(f'"{value}"')
    except json_utils.JSONDecodeError:
        return value
    return parsed if isinstance(parsed, str) else value


def _format_search_params_snippet(args: dict[str, Any], *, project_root: str | None) -> str:
    query = _string_or_none(args.get("query")) or "query"
    path = _string_or_none(args.get("path")) or "."
    glob = _string_or_none(args.get("glob"))
    output_mode = _string_or_none(args.get("output_mode"))
    mode = _string_or_none(args.get("mode"))
    shortened_path = _shorten_project_path(path, project_root=project_root)
    parts = [repr(_truncate(query, 60)), "in", shortened_path]
    if glob:
        parts.append(f"glob {glob}")
    if output_mode and output_mode != "content":
        parts.append(output_mode)
    if mode and mode != "literal":
        parts.append(mode)
    return " ".join(parts)
