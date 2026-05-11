from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

SESSION_INDEX_VERSION = 1
MAX_SESSION_INDEX_ENTRIES = 50


@dataclass(frozen=True)
class SessionEntry:
    id: str
    path: str
    active_tokens: int
    created_at: int
    updated_at: int
    processes: dict[str, dict[str, str]] | None = None


def project_code(project_root: Path) -> str:
    text = str(project_root.resolve())
    return text.replace("/", "-").replace("\\", "-").replace(":", "")


def project_sessions_dir(project_root: Path, deepy_home: Path | None = None) -> Path:
    home = deepy_home or Path.home() / ".deepy"
    return home / "projects" / project_code(project_root)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _role_from_item(item: dict[str, Any]) -> str:
    role = item.get("role")
    if isinstance(role, str) and role:
        return role
    item_type = item.get("type")
    return item_type if isinstance(item_type, str) and item_type else "unknown"


def _content_from_item(item: dict[str, Any]) -> Any:
    if "content" in item:
        return item["content"]
    if "output" in item:
        return item["output"]
    return ""


def _content_with_params(content: Any, content_params: Any, role: Any) -> Any:
    if role not in {"user", "system"} or not content_params:
        return content
    params = content_params if isinstance(content_params, list) else [content_params]
    parts: list[Any] = []
    if content:
        parts.append({"type": "text", "text": content})
    parts.extend(param for param in params if isinstance(param, dict))
    return parts or content


@dataclass
class DeepyJsonlSession:
    session_id: str
    path: Path
    session_settings: object | None = None
    _loaded_items: list[dict[str, Any]] | None = field(default=None, init=False, repr=False)

    @classmethod
    def create(
        cls,
        project_root: Path,
        *,
        deepy_home: Path | None = None,
        session_id: str | None = None,
    ) -> "DeepyJsonlSession":
        sid = session_id or uuid.uuid4().hex
        sessions_dir = project_sessions_dir(project_root, deepy_home)
        return cls(session_id=sid, path=sessions_dir / f"{sid}.jsonl")

    @classmethod
    def open(
        cls,
        project_root: Path,
        session_id: str,
        *,
        deepy_home: Path | None = None,
    ) -> "DeepyJsonlSession":
        sessions_dir = project_sessions_dir(project_root, deepy_home)
        return cls(session_id=session_id, path=sessions_dir / f"{session_id}.jsonl")

    async def get_items(self, limit: int | None = None) -> list[dict[str, Any]]:
        items = self._load_items()
        if limit is not None:
            if limit <= 0:
                return []
            return items[-limit:]
        return list(items)

    async def add_items(self, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            for item in items:
                record = self._record_from_sdk_item(item)
                fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        if self._loaded_items is not None:
            self._loaded_items.extend(dict(item) for item in items)
        self._touch_index(active_tokens=self._estimate_active_tokens())

    async def pop_item(self) -> dict[str, Any] | None:
        records = self._load_records()
        if not records:
            return None
        popped = records.pop()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._loaded_items = [self._sdk_item_from_record(record) for record in records]
        self._touch_index(active_tokens=self._estimate_active_tokens(records))
        return self._sdk_item_from_record(popped)

    async def clear_session(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        self._loaded_items = []
        self._touch_index(active_tokens=0)

    def _record_from_sdk_item(self, item: dict[str, Any]) -> dict[str, Any]:
        now = _now_ms()
        return {
            "id": uuid.uuid4().hex,
            "sessionId": self.session_id,
            "role": _role_from_item(item),
            "content": _content_from_item(item),
            "contentParams": None,
            "messageParams": None,
            "compacted": False,
            "visible": True,
            "createTime": now,
            "updateTime": now,
            "meta": {"sdk_item": item},
        }

    def _sdk_item_from_record(self, record: dict[str, Any]) -> dict[str, Any]:
        meta = record.get("meta")
        if isinstance(meta, dict) and isinstance(meta.get("sdk_item"), dict):
            return dict(meta["sdk_item"])
        role = record.get("role")
        content = record.get("content", "")
        message_params = record.get("messageParams")
        content_params = record.get("contentParams")
        if role in {"user", "assistant", "system", "developer"}:
            item = {"role": role, "content": _content_with_params(content, content_params, role)}
            if isinstance(message_params, dict):
                tool_calls = message_params.get("tool_calls")
                if isinstance(tool_calls, list):
                    item["tool_calls"] = tool_calls
                    item["reasoning_content"] = str(message_params.get("reasoning_content", ""))
                elif isinstance(message_params.get("reasoning_content"), str):
                    item["reasoning_content"] = message_params["reasoning_content"]
            return item
        if role == "tool":
            item = {"role": "tool", "content": content}
            if isinstance(message_params, dict) and isinstance(message_params.get("tool_call_id"), str):
                item["tool_call_id"] = message_params["tool_call_id"]
            return item
        return {"type": str(role or "unknown"), "content": content}

    def _load_records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def _load_items(self) -> list[dict[str, Any]]:
        if self._loaded_items is None:
            self._loaded_items = [
                self._sdk_item_from_record(record)
                for record in self._load_records()
                if not record.get("compacted", False)
            ]
        return list(self._loaded_items)

    def _estimate_active_tokens(self, records: list[dict[str, Any]] | None = None) -> int:
        source = records if records is not None else self._load_records()
        return sum(_estimate_record_tokens(record) for record in source if record.get("visible", True))

    def _touch_index(self, *, active_tokens: int | None = None) -> None:
        index_path = self.path.parent / "sessions-index.json"
        now = _now_ms()
        if index_path.exists():
            try:
                raw = json.loads(index_path.read_text(encoding="utf-8") or "{}")
            except json.JSONDecodeError:
                raw = {"version": SESSION_INDEX_VERSION, "sessions": []}
        else:
            raw = {"version": SESSION_INDEX_VERSION, "sessions": []}
        sessions = raw.get("sessions")
        if not isinstance(sessions, list):
            sessions = []
        previous = next((entry for entry in sessions if entry.get("id") == self.session_id), {})
        sessions = [entry for entry in sessions if entry.get("id") != self.session_id]
        sessions.insert(
            0,
            {
                "id": self.session_id,
                "path": self.path.name,
                "activeTokens": active_tokens
                if active_tokens is not None
                else _coerce_int(previous.get("activeTokens"), 0),
                "createdAt": _coerce_int(previous.get("createdAt"), now),
                "updatedAt": now,
            },
        )
        payload = {
            "version": SESSION_INDEX_VERSION,
            "sessions": sessions[:MAX_SESSION_INDEX_ENTRIES],
        }
        index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def list_session_entries(project_root: Path, deepy_home: Path | None = None) -> list[SessionEntry]:
    index_path = project_sessions_dir(project_root, deepy_home) / "sessions-index.json"
    if not index_path.is_file():
        return []
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return []
    sessions = raw.get("sessions")
    if sessions is None:
        sessions = raw.get("entries")
    if not isinstance(sessions, list):
        return []

    entries: list[SessionEntry] = []
    for item in sessions:
        if not isinstance(item, dict):
            continue
        session_id = item.get("id")
        if not isinstance(session_id, str):
            continue
        path = item.get("path")
        if not isinstance(path, str):
            path = f"{session_id}.jsonl"
        entries.append(
            SessionEntry(
                id=session_id,
                path=path,
                active_tokens=_coerce_int(item.get("activeTokens"), 0),
                created_at=_coerce_time_ms(item.get("createdAt", item.get("createTime"))),
                updated_at=_coerce_time_ms(item.get("updatedAt", item.get("updateTime"))),
                processes=_normalize_processes(item.get("processes")),
            )
        )
    return entries


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    return value if isinstance(value, int) else default


def _coerce_time_ms(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            return 0
    return 0


def _normalize_processes(value: Any) -> dict[str, dict[str, str]] | None:
    if not isinstance(value, dict):
        return None
    processes: dict[str, dict[str, str]] = {}
    for pid, entry in value.items():
        if not isinstance(pid, str) or not pid:
            continue
        if isinstance(entry, str):
            processes[pid] = {"startTime": entry, "command": "Running process..."}
        elif isinstance(entry, dict):
            start_time = entry.get("startTime")
            command = entry.get("command")
            processes[pid] = {
                "startTime": start_time if isinstance(start_time, str) else "",
                "command": command if isinstance(command, str) else "Running process...",
            }
    return processes or None


def _estimate_record_tokens(record: dict[str, Any]) -> int:
    content = record.get("content", "")
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
    return max(1, (len(content) + 3) // 4)
