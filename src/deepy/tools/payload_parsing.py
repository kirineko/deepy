from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from deepy.utils import json as json_utils

from .shell_command import _string_key_dict
from .text_io import _read_text_preserving_newlines
from .tool_dataclasses import UpdateEdit

def _normalize_optional_tool_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped.casefold() in {"null", "none", "undefined"}:
        return None
    return value


def _optional_string_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return _normalize_optional_tool_identifier(value)


def _parse_v3_read_targets(value: object) -> tuple[list[dict[str, object]], str | None]:
    if not isinstance(value, dict):
        return [], "Read arguments must be a JSON object."
    request = cast(dict[str, object], value)
    raw_files = request.get("files")
    if raw_files is None:
        raw_targets: list[object] = [request]
    elif isinstance(raw_files, list):
        raw_targets = raw_files
    else:
        return [], "Read files must be an array when provided."
    targets: list[dict[str, object]] = []
    for index, item in enumerate(raw_targets):
        if not isinstance(item, dict):
            return [], f"Read target #{index + 1} must be an object."
        target = cast(dict[str, object], item)
        path = target.get("path")
        if path is None:
            path = target.get("file_path")
        if not isinstance(path, str) or not path.strip():
            return [], f"Read target #{index + 1} requires path."
        start_line, limit = _parse_v3_read_range(target)
        pages = target.get("pages")
        targets.append(
            {
                "path": path,
                "start_line": start_line,
                "limit": limit,
                "pages": pages if isinstance(pages, str) and pages.strip() else None,
            }
        )
    return targets, None


def _parse_v3_read_range(item: dict[str, object]) -> tuple[int, int | None]:
    range_value = item.get("range")
    if isinstance(range_value, str):
        match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", range_value)
        if match:
            start = max(1, int(match.group(1)))
            end = max(start, int(match.group(2)))
            return start, end - start + 1
    head = _coerce_optional_int(item.get("head"))
    if head is not None and head > 0:
        return 1, head
    tail = _coerce_optional_int(item.get("tail"))
    if tail is not None and tail > 0:
        return -tail, tail
    offset = _coerce_optional_int(item.get("offset"))
    limit = _coerce_optional_int(item.get("limit"))
    return (offset if offset and offset > 0 else 1), limit


def _parse_v3_update_edits(
    value: object,
) -> tuple[list[UpdateEdit], str | None, dict[str, object]]:
    if not isinstance(value, dict):
        return [], "Update arguments must be a JSON object.", {}
    request = cast(dict[str, object], value)
    raw_edits = request.get("edits")
    if raw_edits is None:
        raw_items: list[object] = [request]
    elif isinstance(raw_edits, list):
        raw_items = raw_edits
    else:
        return [], "Update edits must be an array when provided.", {}
    base_path = _optional_string_value(request.get("path") or request.get("file_path"))
    raw_base_replace_all = request.get("replace_all")
    base_replace_all = raw_base_replace_all if isinstance(raw_base_replace_all, bool) else False
    base_expected = _coerce_optional_int(request.get("expected_occurrences"))
    edits: list[UpdateEdit] = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            return [], f"Update edit #{index + 1} must be an object.", {"editIndex": index}
        edit = cast(dict[str, object], item)
        path = _optional_string_value(edit.get("path") or edit.get("file_path")) or base_path
        if not path:
            return [], f"Update edit #{index + 1} requires path.", {"editIndex": index}
        old = edit.get("old")
        new = edit.get("new")
        if not isinstance(old, str) or old == "":
            return [], f"Update edit #{index + 1} requires non-empty old.", {"editIndex": index, "path": path}
        if not isinstance(new, str):
            return [], f"Update edit #{index + 1} requires string new.", {"editIndex": index, "path": path}
        raw_replace_all = edit.get("replace_all")
        replace_all = raw_replace_all if isinstance(raw_replace_all, bool) else base_replace_all
        expected = _coerce_optional_int(edit.get("expected_occurrences"))
        if expected is None:
            expected = base_expected
        edits.append(
            UpdateEdit(
                index=index,
                path=path,
                old=old,
                new=new,
                replace_all=bool(replace_all),
                expected_occurrences=expected,
            )
        )
    return edits, None, {}


def _coerce_optional_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None



def _format_notebook(path: Path) -> tuple[str, str | None]:
    raw = _read_text_preserving_newlines(path)
    if not raw:
        return "WARNING: File is empty.", None
    try:
        parsed = json_utils.loads(raw)
    except json_utils.JSONDecodeError as exc:
        return "", f"Failed to parse notebook JSON: {exc}"
    if not isinstance(parsed, dict):
        return "WARNING: Notebook has no cells.", None

    cells = parsed.get("cells")
    lines: list[str] = []
    if isinstance(cells, list):
        for index, raw_cell in enumerate(cells):
            cell = _string_key_dict(raw_cell)
            if cell is None:
                continue
            raw_cell_type = cell.get("cell_type")
            cell_type = raw_cell_type if isinstance(raw_cell_type, str) else "unknown"
            lines.append(f"# Cell {index + 1} ({cell_type})")
            lines.extend(_normalize_notebook_field(cell.get("source")))

            outputs = cell.get("outputs")
            if not isinstance(outputs, list):
                continue
            for output_index, raw_output in enumerate(outputs):
                output = _string_key_dict(raw_output)
                if output is None:
                    continue
                raw_output_type = output.get("output_type")
                output_type = raw_output_type if isinstance(raw_output_type, str) else "output"
                lines.append(f"# Output {output_index + 1} ({output_type})")
                lines.extend(_format_notebook_output(output))

    if not lines:
        return "WARNING: Notebook has no cells.", None
    return "\n".join(f"{idx + 1}: {line}" for idx, line in enumerate(lines)), None


def _normalize_notebook_field(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).removesuffix("\n").removesuffix("\r") for item in value]
    if isinstance(value, str):
        return value.splitlines()
    return []


def _format_notebook_output(output: dict[str, object]) -> list[str]:
    lines = _normalize_notebook_field(output.get("text"))
    data = output.get("data")
    data_dict = _string_key_dict(data)
    if data_dict is not None:
        lines.extend(_normalize_notebook_field(data_dict.get("text/plain")))
        image_png = data_dict.get("image/png")
        if isinstance(image_png, str):
            lines.append(f"[image/png {len(image_png)} chars]")
        image_jpeg = data_dict.get("image/jpeg")
        if isinstance(image_jpeg, str):
            lines.append(f"[image/jpeg {len(image_jpeg)} chars]")
    traceback = output.get("traceback")
    if isinstance(traceback, list):
        lines.extend(str(item).removesuffix("\n").removesuffix("\r") for item in traceback)
    return lines or ["[output omitted]"]

