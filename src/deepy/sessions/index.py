from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepy.todos import normalize_persisted_todo_state

from .session import SESSION_DB_NAME, DeepySession, project_sessions_db
from .store_helpers import (
    coerce_int,
    ensure_schema,
    json_loads_or_none,
    json_object,
    normalize_processes,
    optional_int,
)

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
    input_suggestion_usage: dict[str, Any] | None = None
    latest_context_window_tokens: int | None = None
    last_usage_tokens: int | None = None
    pending_tokens: int = 0
    last_usage_record_count: int | None = None
    todo_state: list[dict[str, str]] | None = None
    session_cost: dict[str, Any] | None = None


def list_session_entries(project_root: Path, deepy_home: Path | None = None) -> list[SessionEntry]:
    db_path = project_sessions_db(project_root, deepy_home)
    if not db_path.is_file():
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_schema(conn)
        rows = conn.execute(
            """
            select * from sessions
            order by updated_at desc, rowid desc
            limit ?
            """,
            (MAX_SESSION_INDEX_ENTRIES,),
        ).fetchall()
    entries: list[SessionEntry] = []
    for row in rows:
        entries.append(
            SessionEntry(
                id=row["id"],
                path=f"{row['id']}@{SESSION_DB_NAME}",
                active_tokens=coerce_int(row["active_tokens"], 0),
                created_at=coerce_int(row["created_at"], 0),
                updated_at=coerce_int(row["updated_at"], 0),
                processes=normalize_processes(json_loads_or_none(row["processes_json"])),
                usage=json_object(row["usage_json"]),
                input_suggestion_usage=json_object(row["input_suggestion_usage_json"]),
                latest_context_window_tokens=optional_int(row["latest_context_window_tokens"]),
                last_usage_tokens=optional_int(row["last_usage_tokens"]),
                pending_tokens=coerce_int(row["pending_tokens"], 0),
                last_usage_record_count=optional_int(row["last_usage_record_count"]),
                todo_state=normalize_persisted_todo_state(
                    json_loads_or_none(row["todo_state_json"])
                ),
                session_cost=json_object(row["session_cost_json"]),
            )
        )
    return entries


def clear_session_processes(
    project_root: Path,
    session_id: str,
    deepy_home: Path | None = None,
) -> None:
    session = DeepySession.open(project_root, session_id, deepy_home=deepy_home)
    with session._transaction() as conn:
        session._ensure_session_row(conn)
        session._update_session_metadata(conn, processes=None)
