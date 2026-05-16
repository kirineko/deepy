from __future__ import annotations

import json
from typing import Any

orjson: Any | None
try:
    import orjson as _orjson
except Exception:  # pragma: no cover - exercised when optional wheel is unavailable.
    orjson = None
else:
    orjson = _orjson

JSONDecodeError = json.JSONDecodeError


def dumps(value: Any) -> str:
    if orjson is not None:
        return orjson.dumps(value).decode("utf-8")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def dumps_pretty(value: Any) -> str:
    if orjson is not None:
        return orjson.dumps(value, option=orjson.OPT_INDENT_2).decode("utf-8")
    return json.dumps(value, ensure_ascii=False, indent=2)


def loads(text: str | bytes | bytearray) -> Any:
    if orjson is not None:
        return orjson.loads(text)
    return json.loads(text)
