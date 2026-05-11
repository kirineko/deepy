from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .debug_logger import normalize_error

MAX_ERROR_LOG_ENTRIES = 20
CONTENT_PREVIEW_CHARS = 100

_SENSITIVE_PATTERNS = (
    re.compile(r"(Authorization:\s*Bearer\s+)[^\s\r\n]+", re.IGNORECASE),
    re.compile(r"((?:api[Kk]ey|api_key|secret)\s*[:=]\s*\"?)[^\",}\s]+", re.IGNORECASE),
)


def error_log_path(deepy_home: Path | None = None) -> Path:
    home = deepy_home or Path.home() / ".deepy"
    return home / "logs" / "error.log"


def mask_sensitive(text: str) -> str:
    masked = text
    for pattern in _SENSITIVE_PATTERNS:
        masked = pattern.sub(r"\1***MASKED***", masked)
    return masked


def log_api_error(entry: Mapping[str, Any], *, deepy_home: Path | None = None) -> None:
    try:
        path = error_log_path(deepy_home)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = _sanitize_error_entry(entry)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
            fh.write("\n")
        _trim_error_log(path)
    except Exception:
        return


def _sanitize_error_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    error = entry.get("error")
    normalized_error = (
        normalize_error(error)
        if isinstance(error, BaseException)
        else dict(error)
        if isinstance(error, Mapping)
        else normalize_error(error or "")
    )
    sanitized = {
        "timestamp": entry.get("timestamp"),
        "location": entry.get("location"),
        "requestId": entry.get("requestId"),
        "sessionId": entry.get("sessionId"),
        "model": entry.get("model"),
        "baseURL": entry.get("baseURL"),
        "error": {
            "name": normalized_error.get("name", "UnknownError"),
            "message": mask_sensitive(str(normalized_error.get("message", ""))),
        },
        "request": _sanitize_request(entry.get("request", {})),
    }
    stack = normalized_error.get("stack")
    if stack:
        sanitized["error"]["stack"] = mask_sensitive(str(stack))
    if "response" in entry:
        response = entry["response"]
        sanitized["response"] = mask_sensitive(response) if isinstance(response, str) else response
    return {key: value for key, value in sanitized.items() if value is not None}


def _sanitize_request(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) <= CONTENT_PREVIEW_CHARS:
            return value
        return value[:CONTENT_PREVIEW_CHARS] + f"...(total {len(value)} chars)"
    if isinstance(value, list):
        return [_sanitize_request(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == "content" and isinstance(item, str):
                result[key] = _sanitize_request(item)
            else:
                result[key] = _sanitize_request(item)
        return result
    return value


def _trim_error_log(path: Path) -> None:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) <= MAX_ERROR_LOG_ENTRIES:
        return
    path.write_text("\n".join(lines[-MAX_ERROR_LOG_ENTRIES:]) + "\n", encoding="utf-8")
