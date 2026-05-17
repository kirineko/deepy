from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from deepy.utils import json as json_utils


TODO_STATUSES = {"pending", "in_progress", "completed"}


@dataclass(frozen=True)
class TodoItem:
    id: str
    content: str
    status: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "content": self.content, "status": self.status}


def normalize_todo_items(value: object) -> tuple[list[TodoItem] | None, str | None]:
    if not isinstance(value, list):
        return None, "todos must be a list."
    items: list[TodoItem] = []
    seen_ids: set[str] = set()
    in_progress_count = 0
    for index, raw_item in enumerate(value):
        if not isinstance(raw_item, Mapping):
            return None, f"todo item {index + 1} must be an object."
        item = cast(Mapping[str, object], raw_item)
        todo_id = _clean_string(item.get("id"))
        content = _clean_string(item.get("content"))
        status = _clean_string(item.get("status"))
        if not todo_id:
            return None, f"todo item {index + 1} id must not be empty."
        if todo_id in seen_ids:
            return None, f"duplicate todo id: {todo_id}"
        if not content:
            return None, f"todo item {todo_id} content must not be empty."
        if status not in TODO_STATUSES:
            return None, f"todo item {todo_id} has unsupported status: {status or '(empty)'}"
        if status == "in_progress":
            in_progress_count += 1
        seen_ids.add(todo_id)
        items.append(TodoItem(id=todo_id, content=content, status=status))
    if in_progress_count > 1:
        return None, "only one todo item may be in_progress."
    return items, None


def todo_items_to_payload(items: list[TodoItem]) -> list[dict[str, str]]:
    return [item.to_dict() for item in items]


def todo_counts(items: list[TodoItem]) -> dict[str, int]:
    return {
        "total": len(items),
        "pending": sum(1 for item in items if item.status == "pending"),
        "in_progress": sum(1 for item in items if item.status == "in_progress"),
        "completed": sum(1 for item in items if item.status == "completed"),
    }


def todo_state_from_tool_output(output: object) -> list[dict[str, str]] | None:
    payload = _tool_output_payload(output)
    if not isinstance(payload, dict):
        return None
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("kind") != "todo_list":
        return None
    todos = metadata.get("todos")
    items, error = normalize_todo_items(todos)
    if error is not None or items is None:
        return None
    return todo_items_to_payload(items)


def normalize_persisted_todo_state(value: object) -> list[dict[str, str]] | None:
    items, error = normalize_todo_items(value)
    if error is not None or items is None:
        return None
    return todo_items_to_payload(items)


def todo_state_prompt_text(items: list[dict[str, str]]) -> str:
    normalized, error = normalize_todo_items(items)
    if error is not None or normalized is None or not normalized:
        return ""
    counts = todo_counts(normalized)
    lines = [
        "Active todo plan:",
        f"- Progress: {counts['completed']}/{counts['total']} completed",
    ]
    for item in normalized:
        lines.append(f"- [{item.status}] {item.id}: {item.content}")
    return "\n".join(lines)


def _tool_output_payload(output: object) -> Any:
    if isinstance(output, str):
        try:
            return json_utils.loads(output)
        except json_utils.JSONDecodeError:
            return None
    return output


def _clean_string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
