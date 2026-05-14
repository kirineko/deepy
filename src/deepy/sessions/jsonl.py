from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deepy.llm.context import estimate_tokens_for_item
from deepy.llm.replay import sanitize_sdk_items_for_replay
from deepy.usage import TokenUsage, merge_usage, normalize_usage
from deepy.utils import json as json_utils

SESSION_INDEX_VERSION = 2
MAX_SESSION_INDEX_ENTRIES = 50


@dataclass(frozen=True)
class SessionEntry:
    id: str
    path: str
    active_tokens: int
    created_at: int
    updated_at: int
    processes: dict[str, dict[str, str]] | None = None
    usage: dict[str, Any] | None = None
    last_usage_tokens: int | None = None
    pending_tokens: int = 0
    last_usage_record_count: int | None = None


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
                fh.write(json_utils.dumps(record) + "\n")
        if self._loaded_items is not None:
            self._loaded_items = sanitize_sdk_items_for_replay(
                [*self._loaded_items, *(dict(item) for item in items)]
            )
        self._touch_index_after_append(items)

    async def pop_item(self) -> dict[str, Any] | None:
        records = self._load_records()
        if not records:
            return None
        popped = records.pop()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json_utils.dumps(record) + "\n")
        self._loaded_items = [item for item in (_sdk_item_from_record(record) for record in records) if item]
        state = self.context_token_state(records)
        self._touch_index(
            active_tokens=state.active_tokens,
            last_usage_tokens=state.last_usage_tokens,
            pending_tokens=state.pending_tokens,
            last_usage_record_count=state.last_usage_record_count,
        )
        return _sdk_item_from_record(popped)

    async def clear_session(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        self._loaded_items = []
        self._touch_index(
            active_tokens=0,
            last_usage_tokens=0,
            pending_tokens=0,
            last_usage_record_count=0,
        )

    def record_usage(self, usage: TokenUsage | dict[str, Any] | None) -> None:
        normalized = usage if isinstance(usage, TokenUsage) else normalize_usage(usage)
        if not normalized.known:
            return
        previous = _entry_for_session(self.path.parent / "sessions-index.json", self.session_id)
        accumulated = merge_usage(previous.get("usage") if previous else None, normalized)
        record_count = len(self._load_records())
        self._touch_index(
            active_tokens=normalized.prompt_tokens,
            usage=accumulated.to_dict(),
            last_usage_tokens=normalized.prompt_tokens,
            pending_tokens=0,
            last_usage_record_count=record_count,
        )

    def context_token_state(
        self,
        records: list[dict[str, Any]] | None = None,
    ) -> "ContextTokenState":
        source = records if records is not None else self._load_records()
        previous = _entry_for_session(self.path.parent / "sessions-index.json", self.session_id)
        if previous:
            last_usage_tokens = _optional_int(previous.get("lastUsageTokens"))
            last_usage_record_count = _optional_int(previous.get("lastUsageRecordCount"))
            if last_usage_tokens is not None and last_usage_record_count is not None:
                bounded_count = max(0, min(last_usage_record_count, len(source)))
                pending_tokens = sum(_estimate_record_tokens(record) for record in source[bounded_count:])
                return ContextTokenState(
                    active_tokens=last_usage_tokens + pending_tokens,
                    last_usage_tokens=last_usage_tokens,
                    pending_tokens=pending_tokens,
                    last_usage_record_count=bounded_count,
                    estimated=True,
                )
        active_tokens = self._estimate_active_tokens(source)
        return ContextTokenState(
            active_tokens=active_tokens,
            last_usage_tokens=None,
            pending_tokens=0,
            last_usage_record_count=None,
            estimated=True,
        )

    async def replace_items(
        self,
        items: list[dict[str, Any]],
        *,
        active_tokens: int | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        now = _now_ms()
        records = [
            {
                "id": uuid.uuid4().hex,
                "session_id": self.session_id,
                "role": _role_from_item(item),
                "content": _content_from_item(item),
                "created_at": now,
                "meta": {"sdk_item": item},
            }
            for item in items
        ]
        with self.path.open("w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json_utils.dumps(record) + "\n")
        self._loaded_items = sanitize_sdk_items_for_replay([dict(item) for item in items])
        estimated_tokens = (
            active_tokens if active_tokens is not None else self._estimate_active_tokens(records)
        )
        self._touch_index(
            active_tokens=estimated_tokens,
            last_usage_tokens=estimated_tokens,
            pending_tokens=0,
            last_usage_record_count=len(records),
        )

    def _record_from_sdk_item(self, item: dict[str, Any]) -> dict[str, Any]:
        now = _now_ms()
        return {
            "id": uuid.uuid4().hex,
            "session_id": self.session_id,
            "role": _role_from_item(item),
            "content": _content_from_item(item),
            "created_at": now,
            "meta": {"sdk_item": item},
        }

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
                    parsed = json_utils.loads(line)
                except Exception:
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
        return records

    def _load_items(self) -> list[dict[str, Any]]:
        if self._loaded_items is None:
            loaded_items = [
                item
                for item in (_sdk_item_from_record(record) for record in self._load_records())
                if item is not None
            ]
            self._loaded_items = sanitize_sdk_items_for_replay(loaded_items)
        return list(self._loaded_items)

    def _estimate_active_tokens(self, records: list[dict[str, Any]] | None = None) -> int:
        source = records if records is not None else self._load_records()
        return sum(_estimate_record_tokens(record) for record in source)

    def _touch_index(
        self,
        *,
        active_tokens: int | None = None,
        usage: dict[str, Any] | None = None,
        last_usage_tokens: int | None = None,
        pending_tokens: int | None = None,
        last_usage_record_count: int | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        index_path = self.path.parent / "sessions-index.json"
        now = _now_ms()
        raw = _read_index(index_path)
        sessions = _index_sessions(raw)
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
                **(
                    {"lastUsageTokens": last_usage_tokens}
                    if last_usage_tokens is not None
                    else (
                        {"lastUsageTokens": previous["lastUsageTokens"]}
                        if "lastUsageTokens" in previous
                        else {}
                    )
                ),
                **(
                    {"pendingTokens": pending_tokens}
                    if pending_tokens is not None
                    else (
                        {"pendingTokens": previous["pendingTokens"]}
                        if "pendingTokens" in previous
                        else {}
                    )
                ),
                **(
                    {"lastUsageRecordCount": last_usage_record_count}
                    if last_usage_record_count is not None
                    else (
                        {"lastUsageRecordCount": previous["lastUsageRecordCount"]}
                        if "lastUsageRecordCount" in previous
                        else {}
                    )
                ),
                "createdAt": _coerce_int(previous.get("createdAt"), now),
                "updatedAt": now,
                **({"usage": usage} if usage is not None else {}),
                **(
                    {"usage": previous["usage"]}
                    if usage is None and isinstance(previous.get("usage"), dict)
                    else {}
                ),
                **({"processes": previous["processes"]} if "processes" in previous else {}),
            },
        )
        payload = {
            "version": SESSION_INDEX_VERSION,
            "sessions": sessions[:MAX_SESSION_INDEX_ENTRIES],
        }
        index_path.write_text(json_utils.dumps_pretty(payload) + "\n", encoding="utf-8")

    def _touch_index_after_append(self, appended_items: list[dict[str, Any]]) -> None:
        previous = _entry_for_session(self.path.parent / "sessions-index.json", self.session_id)
        if previous and _optional_int(previous.get("lastUsageTokens")) is not None:
            last_usage_tokens = _optional_int(previous.get("lastUsageTokens")) or 0
            previous_pending = _coerce_int(previous.get("pendingTokens"), 0)
            pending_tokens = previous_pending + sum(estimate_tokens_for_item(item) for item in appended_items)
            self._touch_index(
                active_tokens=last_usage_tokens + pending_tokens,
                last_usage_tokens=last_usage_tokens,
                pending_tokens=pending_tokens,
                last_usage_record_count=_coerce_int(
                    previous.get("lastUsageRecordCount"),
                    max(0, len(self._load_records()) - len(appended_items)),
                ),
            )
            return
        self._touch_index(active_tokens=self._estimate_active_tokens())


@dataclass(frozen=True)
class ContextTokenState:
    active_tokens: int
    last_usage_tokens: int | None = None
    pending_tokens: int = 0
    last_usage_record_count: int | None = None
    estimated: bool = True


def list_session_entries(project_root: Path, deepy_home: Path | None = None) -> list[SessionEntry]:
    index_path = project_sessions_dir(project_root, deepy_home) / "sessions-index.json"
    if not index_path.is_file():
        return []
    sessions = _index_sessions(_read_index(index_path))
    entries: list[SessionEntry] = []
    for item in sessions:
        session_id = item.get("id")
        path = item.get("path")
        if not isinstance(session_id, str) or not session_id:
            continue
        if not isinstance(path, str) or not path:
            path = f"{session_id}.jsonl"
        usage = item.get("usage")
        entries.append(
            SessionEntry(
                id=session_id,
                path=path,
                active_tokens=_coerce_int(item.get("activeTokens"), 0),
                created_at=_coerce_int(item.get("createdAt"), 0),
                updated_at=_coerce_int(item.get("updatedAt"), 0),
                processes=_normalize_processes(item.get("processes")),
                usage=usage if isinstance(usage, dict) else None,
                last_usage_tokens=_optional_int(item.get("lastUsageTokens")),
                pending_tokens=_coerce_int(item.get("pendingTokens"), 0),
                last_usage_record_count=_optional_int(item.get("lastUsageRecordCount")),
            )
        )
    return entries


def _read_index(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        return {"version": SESSION_INDEX_VERSION, "sessions": []}
    try:
        raw = json_utils.loads(index_path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {"version": SESSION_INDEX_VERSION, "sessions": []}
    return raw if isinstance(raw, dict) else {"version": SESSION_INDEX_VERSION, "sessions": []}


def _index_sessions(raw: dict[str, Any]) -> list[dict[str, Any]]:
    sessions = raw.get("sessions")
    if not isinstance(sessions, list):
        return []
    return [item for item in sessions if isinstance(item, dict)]


def _entry_for_session(index_path: Path, session_id: str) -> dict[str, Any] | None:
    return next(
        (entry for entry in _index_sessions(_read_index(index_path)) if entry.get("id") == session_id),
        None,
    )


def _sdk_item_from_record(record: dict[str, Any]) -> dict[str, Any] | None:
    meta = record.get("meta")
    if not isinstance(meta, dict):
        return None
    item = meta.get("sdk_item")
    return dict(item) if isinstance(item, dict) else None


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    return value if isinstance(value, int) else default


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) and value >= 0 else None


def _normalize_processes(value: Any) -> dict[str, dict[str, str]] | None:
    if not isinstance(value, dict):
        return None
    processes: dict[str, dict[str, str]] = {}
    for pid, entry in value.items():
        if not isinstance(pid, str) or not pid:
            continue
        if isinstance(entry, dict):
            start_time = entry.get("startTime")
            command = entry.get("command")
            processes[pid] = {
                "startTime": start_time if isinstance(start_time, str) else "",
                "command": command if isinstance(command, str) else "Running process...",
            }
    return processes or None


def _estimate_record_tokens(record: dict[str, Any]) -> int:
    item = _sdk_item_from_record(record)
    if item is not None:
        return estimate_tokens_for_item(item)
    return estimate_tokens_for_item(record.get("content", ""))
