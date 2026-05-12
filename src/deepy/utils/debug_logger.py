from __future__ import annotations

import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import json as json_utils


def debug_log_path(deepy_home: Path | None = None) -> Path:
    home = deepy_home or Path.home() / ".deepy"
    return home / "logs" / "debug.log"


def normalize_error(error: BaseException | object) -> dict[str, str]:
    if isinstance(error, BaseException):
        payload = {
            "name": error.__class__.__name__,
            "message": str(error),
        }
        stack = "".join(traceback.format_exception(type(error), error, error.__traceback__)).strip()
        if stack:
            payload["stack"] = stack
        return payload
    return {"name": "UnknownError", "message": str(error)}


def log_debug_event(entry: Mapping[str, Any], *, deepy_home: Path | None = None) -> None:
    try:
        path = debug_log_path(deepy_home)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json_utils.dumps(_to_serializable(entry)))
            fh.write("\n")
    except Exception:
        return


def _to_serializable(value: Any, seen: set[int] | None = None) -> Any:
    seen = seen or set()
    if isinstance(value, BaseException):
        return normalize_error(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        marker = id(value)
        if marker in seen:
            return "[Circular]"
        seen.add(marker)
        return {str(key): _to_serializable(item, seen) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        marker = id(value)
        if marker in seen:
            return "[Circular]"
        seen.add(marker)
        return [_to_serializable(item, seen) for item in value]
    try:
        json_utils.dumps(value)
    except TypeError:
        return str(value)
    return value
