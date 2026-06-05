from __future__ import annotations

import re
from typing import Any


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
