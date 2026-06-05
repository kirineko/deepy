from __future__ import annotations

from typing import Any

from deepy.utils import json as json_utils

from .arg_repair import _repair_tool_arguments
from .result import ToolResult
from .schema_compat import _validate_args_against_schema


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
