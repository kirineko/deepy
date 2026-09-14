"""Non-mutating Responses replay and indivisible tool groups."""
from __future__ import annotations

import hashlib
from deepy.utils import json as json_utils
from copy import deepcopy
from typing import Any

from agents.exceptions import ModelBehaviorError

ADAPTER_VERSION = 1


def fingerprint(value: Any) -> str:
    def canonical(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: canonical(item[key]) for key in sorted(item)}
        if isinstance(item, (tuple, list)):
            return [canonical(part) for part in item]
        return item
    return hashlib.sha256(json_utils.dumps(canonical(value)).encode()).hexdigest()


def model_identity(provider: str, model: str, endpoint: str) -> dict[str, str]:
    return {"provider": provider, "model": model, "api": "responses",
            "endpoint": endpoint.rstrip("/")}


def project_history(items: list[Any], target: dict[str, str]) -> list[Any]:
    result = []
    for original in items:
        item = deepcopy(original)
        if isinstance(item, dict):
            provenance = item.pop("deepy_origin", None)
            item.pop("deepy_provider", None)
            if provenance != target:
                # Server item IDs are provider-local; call_id is the portable tool pairing key.
                item.pop("id", None)
            if item.get("type") == "reasoning" and provenance != target:
                # Opaque reasoning cannot be ported, including between two models
                # served by the same provider. Final answers remain in history.
                continue
        result.append(item)
    return result


def history_groups(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    pending: set[str] = set()
    seen: set[str] = set()
    group: list[dict[str, Any]] = []
    for item in items:
        kind = item.get("type")
        call_id = item.get("call_id") or item.get("id")
        if kind == "function_call":
            if not isinstance(call_id, str) or not call_id or call_id in seen:
                raise ModelBehaviorError("Invalid or duplicate tool call in history; restore a complete session.")
            pending.add(call_id)
            seen.add(call_id)
        elif kind == "function_call_output":
            if call_id not in pending:
                raise ModelBehaviorError("Unpaired tool result in history; restore a complete session.")
            pending.remove(call_id)
        group.append(item)
        if not pending:
            groups.append(group)
            group = []
    if pending:
        raise ModelBehaviorError("Unfinished tool calls; finish or cancel active work before switching models.")
    return groups
