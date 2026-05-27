from __future__ import annotations

import sqlite3
from typing import Any

from deepy.todos import todo_state_from_tool_output
from deepy.utils import json as json_utils

CONTEXT_UNDERCOUNT_REPAIR_RATIO = 2
CONTEXT_UNDERCOUNT_REPAIR_MIN_DELTA = 128


def role_from_item(item: dict[str, Any]) -> str:
    role = item.get("role")
    if isinstance(role, str) and role:
        return role
    item_type = item.get("type")
    return item_type if isinstance(item_type, str) and item_type else "unknown"


def item_type_from_item(item: dict[str, Any]) -> str:
    item_type = item.get("type")
    return item_type if isinstance(item_type, str) else ""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        pragma journal_mode = wal;
        create table if not exists store_meta(
            key text primary key,
            value text not null
        );
        insert or ignore into store_meta(key, value) values ('version', '1');
        create table if not exists sessions(
            id text primary key,
            created_at integer not null,
            updated_at integer not null,
            item_count integer not null default 0,
            active_tokens integer not null default 0,
            latest_context_window_tokens integer,
            last_usage_tokens integer,
            pending_tokens integer not null default 0,
            last_usage_record_count integer,
            usage_json text,
            input_suggestion_usage_json text,
            todo_state_json text,
            session_cost_json text,
            processes_json text,
            title text,
            status text
        );
        create table if not exists session_items(
            session_id text not null,
            seq integer not null,
            created_at integer not null,
            role text not null,
            item_type text,
            payload_json text not null,
            primary key(session_id, seq),
            foreign key(session_id) references sessions(id) on delete cascade
        );
        create table if not exists session_archives(
            id text primary key,
            session_id text not null,
            created_at integer not null,
            reason text not null,
            before_tokens integer not null,
            after_tokens integer,
            item_snapshot_json text not null
        );
        create index if not exists idx_sessions_updated_at on sessions(updated_at desc);
        create index if not exists idx_session_items_session_seq
            on session_items(session_id, seq);
        """
    )
    _ensure_column(conn, "sessions", "cache_prefix_fingerprint", "text")
    _ensure_column(conn, "sessions", "cache_prefix_snapshot_json", "text")
    _ensure_column(conn, "sessions", "cache_prefix_generation", "integer not null default 0")
    _ensure_column(conn, "sessions", "cache_break_reason", "text")
    _ensure_column(conn, "sessions", "cache_usage_json", "text")


def _ensure_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    rows = conn.execute(f"pragma table_info({table})").fetchall()
    if any(row[1] == column for row in rows):
        return
    conn.execute(f"alter table {table} add column {column} {declaration}")


def next_seq(conn: sqlite3.Connection, session_id: str) -> int:
    value = conn.execute(
        "select coalesce(max(seq), 0) + 1 from session_items where session_id = ?",
        (session_id,),
    ).fetchone()[0]
    return int(value)


def item_count(conn: sqlite3.Connection, session_id: str) -> int:
    value = conn.execute(
        "select count(*) from session_items where session_id = ?",
        (session_id,),
    ).fetchone()[0]
    return int(value)


def json_dumps(value: Any) -> str:
    return json_utils.dumps(value)


def json_loads(value: str) -> dict[str, Any]:
    parsed = json_utils.loads(value)
    return dict(parsed) if isinstance(parsed, dict) else {}


def json_loads_or_none(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return None
    try:
        return json_utils.loads(value)
    except Exception:
        return None


def json_object(value: Any) -> dict[str, Any] | None:
    parsed = json_loads_or_none(value)
    return parsed if isinstance(parsed, dict) else None


def latest_todo_state_from_items(items: list[dict[str, Any]]) -> list[dict[str, str]] | None:
    latest: list[dict[str, str]] | None = None
    for item in items:
        output = item.get("output")
        if output is None and item.get("role") == "tool":
            output = item.get("content")
        todo_state = todo_state_from_tool_output(output)
        if todo_state is not None:
            latest = todo_state
    return latest


def preview_from_items(items: list[dict[str, Any]]) -> tuple[str, str]:
    return session_title(items), session_status(items)


def session_title(items: list[dict[str, Any]]) -> str:
    for item in items:
        if role_from_item(item) == "user":
            text = item_text(item)
            if text.strip():
                return " ".join(text.split())[:200]
    for item in items:
        text = item_text(item)
        if text.strip():
            return " ".join(text.split())[:200]
    return "Untitled"


def session_status(items: list[dict[str, Any]]) -> str:
    if not items:
        return "empty"
    last = items[-1]
    if item_type_from_item(last) == "function_call":
        return "interrupted"
    return "completed"


def item_text(item: dict[str, Any]) -> str:
    for key in ("content", "text", "output"):
        value = item.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for part in value:
                if isinstance(part, dict):
                    text = part.get("text") or part.get("input_text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
    return ""


def coerce_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    return value if isinstance(value, int) else default


def optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) and value >= 0 else None


def normalize_processes(value: Any) -> dict[str, dict[str, str]] | None:
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


def repair_undercounted_context_tokens(checkpoint_tokens: int, estimated_tokens: int) -> int:
    if estimated_tokens <= checkpoint_tokens:
        return checkpoint_tokens
    if (
        estimated_tokens - checkpoint_tokens >= CONTEXT_UNDERCOUNT_REPAIR_MIN_DELTA
        and estimated_tokens >= checkpoint_tokens * CONTEXT_UNDERCOUNT_REPAIR_RATIO
    ):
        return estimated_tokens
    return checkpoint_tokens
