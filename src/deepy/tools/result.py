from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from deepy.utils import json as json_utils


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    name: str
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    awaitUserResponse: bool = False
    followUpMessages: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "name": self.name,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
            "awaitUserResponse": self.awaitUserResponse,
        }
        if self.followUpMessages is not None:
            payload["followUpMessages"] = self.followUpMessages
        return payload

    def to_json(self) -> str:
        return json_utils.dumps(self.to_dict())

    @classmethod
    def ok_result(
        cls,
        name: str,
        output: str = "",
        *,
        metadata: dict[str, Any] | None = None,
    ) -> "ToolResult":
        return cls(ok=True, name=name, output=output, metadata=metadata or {})

    @classmethod
    def error_result(
        cls,
        name: str,
        error: str,
        *,
        output: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "ToolResult":
        return cls(ok=False, name=name, output=output, error=error, metadata=metadata or {})
