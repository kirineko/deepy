from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SESSION_INDEX_VERSION = 1
MAX_SESSION_INDEX_ENTRIES = 50


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

    async def get_items(self, limit: int | None = None) -> list[dict[str, Any]]:
        items = self._load_items()
        if limit is not None:
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
        self._touch_index()

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
        self._touch_index()
        return self._sdk_item_from_record(popped)

    async def clear_session(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        self._loaded_items = []
        self._touch_index()

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
        if role in {"user", "assistant", "system", "developer"}:
            return {"role": role, "content": content}
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
                records.append(json.loads(line))
        return records

    def _load_items(self) -> list[dict[str, Any]]:
        if self._loaded_items is None:
            self._loaded_items = [
                self._sdk_item_from_record(record) for record in self._load_records()
            ]
        return list(self._loaded_items)

    def _touch_index(self) -> None:
        index_path = self.path.parent / "sessions-index.json"
        now = _now_ms()
        if index_path.exists():
            raw = json.loads(index_path.read_text(encoding="utf-8") or "{}")
        else:
            raw = {"version": SESSION_INDEX_VERSION, "sessions": []}
        sessions = raw.get("sessions")
        if not isinstance(sessions, list):
            sessions = []
        sessions = [entry for entry in sessions if entry.get("id") != self.session_id]
        sessions.insert(
            0,
            {
                "id": self.session_id,
                "path": self.path.name,
                "activeTokens": 0,
                "createdAt": now,
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
