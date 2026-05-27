from __future__ import annotations

import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deepy.llm.context import estimate_tokens_for_item
from deepy.llm.replay import sanitize_sdk_items_for_replay
from deepy.todos import normalize_persisted_todo_state
from deepy.usage import (
    ContextWindowUsage,
    TokenUsage,
    context_window_usage,
    merge_usage,
    normalize_usage,
)

from .store_helpers import (
    coerce_int,
    ensure_schema,
    item_count,
    item_type_from_item,
    json_dumps,
    json_loads,
    json_loads_or_none,
    json_object,
    latest_todo_state_from_items,
    next_seq,
    optional_int,
    preview_from_items,
    repair_undercounted_context_tokens,
    role_from_item,
)

SESSION_STORE_VERSION = 1
SESSION_DB_NAME = "sessions.db"
_UNSET = object()


@dataclass(frozen=True)
class ContextTokenState:
    # active_tokens is an internal local history estimate. User-facing Context
    # Window values should use latest_context_window_usage() when provider usage is known.
    active_tokens: int
    last_usage_tokens: int | None = None
    pending_tokens: int = 0
    last_usage_record_count: int | None = None
    estimated: bool = True


def project_code(project_root: Path) -> str:
    text = str(project_root.resolve())
    return text.replace("/", "-").replace("\\", "-").replace(":", "")


def project_sessions_dir(project_root: Path, deepy_home: Path | None = None) -> Path:
    home = deepy_home or Path.home() / ".deepy"
    return home / "projects" / project_code(project_root)


def project_sessions_db(project_root: Path, deepy_home: Path | None = None) -> Path:
    return project_sessions_dir(project_root, deepy_home) / SESSION_DB_NAME


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class DeepySession:
    session_id: str
    db_path: Path
    session_settings: object | None = None
    _loaded_items: list[dict[str, Any]] | None = field(default=None, init=False, repr=False)

    @classmethod
    def create(
        cls,
        project_root: Path,
        *,
        deepy_home: Path | None = None,
        session_id: str | None = None,
    ) -> "DeepySession":
        sid = session_id or uuid.uuid4().hex
        return cls(session_id=sid, db_path=project_sessions_db(project_root, deepy_home))

    @classmethod
    def open(
        cls,
        project_root: Path,
        session_id: str,
        *,
        deepy_home: Path | None = None,
    ) -> "DeepySession":
        return cls(session_id=session_id, db_path=project_sessions_db(project_root, deepy_home))

    async def get_items(self, limit: int | None = None) -> list[dict[str, Any]]:
        return self.get_items_sync(limit=limit)

    def get_items_sync(self, limit: int | None = None) -> list[dict[str, Any]]:
        if limit is not None and limit <= 0:
            return []
        if limit is None:
            if self._loaded_items is None:
                self._loaded_items = sanitize_sdk_items_for_replay(self._load_items())
            return list(self._loaded_items)
        return sanitize_sdk_items_for_replay(self._load_items(limit=limit))

    async def add_items(self, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        with self._transaction() as conn:
            row = self._ensure_session_row(conn)
            next_seq_value = next_seq(conn, self.session_id)
            now = _now_ms()
            for offset, item in enumerate(items):
                conn.execute(
                    """
                    insert into session_items(session_id, seq, created_at, role, item_type, payload_json)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.session_id,
                        next_seq_value + offset,
                        now,
                        role_from_item(item),
                        item_type_from_item(item),
                        json_dumps(item),
                    ),
                )
            previous_last_usage = optional_int(row["last_usage_tokens"])
            todo_state = latest_todo_state_from_items(items)
            if previous_last_usage is not None:
                previous_pending = coerce_int(row["pending_tokens"], 0)
                pending_tokens = previous_pending + sum(
                    estimate_tokens_for_item(item) for item in items
                )
                active_tokens = previous_last_usage + pending_tokens
                last_usage_record_count = coerce_int(
                    row["last_usage_record_count"],
                    max(0, item_count(conn, self.session_id) - len(items)),
                )
            else:
                active_tokens = self._estimate_active_tokens_conn(conn)
                pending_tokens = coerce_int(row["pending_tokens"], 0)
                last_usage_record_count = optional_int(row["last_usage_record_count"])
            self._update_session_metadata(
                conn,
                active_tokens=active_tokens,
                pending_tokens=pending_tokens,
                last_usage_record_count=last_usage_record_count,
                todo_state=todo_state if todo_state is not None else _UNSET,
            )
        self._append_loaded_cache(items)

    async def pop_item(self) -> dict[str, Any] | None:
        with self._transaction() as conn:
            self._ensure_session_row(conn)
            row = conn.execute(
                """
                select seq, payload_json from session_items
                where session_id = ?
                order by seq desc
                limit 1
                """,
                (self.session_id,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "delete from session_items where session_id = ? and seq = ?",
                (self.session_id, row["seq"]),
            )
            items = self._load_items_conn(conn)
            session_row = conn.execute(
                "select * from sessions where id = ?",
                (self.session_id,),
            ).fetchone()
            state = self._context_token_state_from_row(session_row, items)
            self._update_session_metadata(
                conn,
                active_tokens=state.active_tokens,
                last_usage_tokens=state.last_usage_tokens,
                pending_tokens=state.pending_tokens,
                last_usage_record_count=state.last_usage_record_count,
            )
            self._loaded_items = sanitize_sdk_items_for_replay(items)
            return json_loads(row["payload_json"])

    async def clear_session(self) -> None:
        with self._transaction() as conn:
            self._ensure_session_row(conn)
            conn.execute("delete from session_items where session_id = ?", (self.session_id,))
            self._update_session_metadata(
                conn,
                active_tokens=0,
                latest_context_window_tokens=0,
                last_usage_tokens=0,
                pending_tokens=0,
                last_usage_record_count=0,
                todo_state=[],
                session_cost=None,
            )
        self._loaded_items = []

    async def replace_items(
        self,
        items: list[dict[str, Any]],
        *,
        active_tokens: int | None = None,
    ) -> None:
        with self._transaction() as conn:
            self._ensure_session_row(conn)
            self._replace_items_conn(conn, items, active_tokens=active_tokens)
        self._loaded_items = sanitize_sdk_items_for_replay([dict(item) for item in items])

    async def archive_and_replace_items(
        self,
        items: list[dict[str, Any]],
        *,
        active_tokens: int,
        reason: str,
        before_tokens: int,
        after_tokens: int,
    ) -> str:
        archive_id = uuid.uuid4().hex
        with self._transaction() as conn:
            self._ensure_session_row(conn)
            snapshot = self._load_items_conn(conn)
            conn.execute(
                """
                insert into session_archives(
                    id, session_id, created_at, reason, before_tokens, after_tokens, item_snapshot_json
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    archive_id,
                    self.session_id,
                    _now_ms(),
                    reason,
                    before_tokens,
                    after_tokens,
                    json_dumps(snapshot),
                ),
            )
            self._replace_items_conn(conn, items, active_tokens=active_tokens)
        self._loaded_items = sanitize_sdk_items_for_replay([dict(item) for item in items])
        return archive_id

    def record_usage(self, usage: TokenUsage | dict[str, Any] | None) -> None:
        normalized = usage if isinstance(usage, TokenUsage) else normalize_usage(usage)
        if not normalized.known:
            return
        with self._transaction() as conn:
            row = self._ensure_session_row(conn)
            accumulated = merge_usage(json_object(row["usage_json"]), normalized)
            current_state = self._context_token_state_from_row(row, self._load_items_conn(conn))
            checkpoint_tokens = max(normalized.prompt_tokens, current_state.active_tokens)
            latest_context_usage = context_window_usage(normalized)
            self._update_session_metadata(
                conn,
                active_tokens=checkpoint_tokens,
                usage=accumulated.to_dict(),
                latest_context_window_tokens=latest_context_usage.used_tokens
                if latest_context_usage is not None
                else None,
                last_usage_tokens=checkpoint_tokens,
                pending_tokens=0,
                last_usage_record_count=item_count(conn, self.session_id),
            )

    def record_input_suggestion_usage(
        self,
        usage: TokenUsage | dict[str, Any] | None,
        *,
        model: str,
        elapsed_ms: int | None = None,
    ) -> None:
        normalized = usage if isinstance(usage, TokenUsage) else normalize_usage(usage)
        if not normalized.known:
            return
        with self._transaction() as conn:
            row = self._ensure_session_row(conn)
            previous_usage = json_object(row["input_suggestion_usage_json"])
            accumulated = merge_usage(previous_usage, normalized).to_dict()
            accumulated["model"] = model
            if elapsed_ms is not None:
                accumulated["elapsed_ms"] = coerce_int(
                    previous_usage.get("elapsed_ms") if previous_usage else None,
                    0,
                ) + max(elapsed_ms, 0)
            self._update_session_metadata(conn, input_suggestion_usage=accumulated)

    def record_session_cost_start(self, snapshot: dict[str, Any]) -> None:
        from deepy.session_cost import start_session_cost

        with self._transaction() as conn:
            row = self._ensure_session_row(conn)
            previous_cost = json_object(row["session_cost_json"])
            if isinstance(previous_cost, dict) and isinstance(previous_cost.get("start"), dict):
                return
            self._update_session_metadata(conn, session_cost=start_session_cost(snapshot))

    def record_session_cost_end(self, snapshot: dict[str, Any]) -> None:
        from deepy.session_cost import complete_session_cost

        with self._transaction() as conn:
            row = self._ensure_session_row(conn)
            previous_cost = json_object(row["session_cost_json"])
            self._update_session_metadata(
                conn,
                session_cost=complete_session_cost(previous_cost, snapshot),
            )

    def session_cost(self) -> dict[str, Any] | None:
        row = self._session_row()
        return json_object(row["session_cost_json"]) if row is not None else None

    def context_token_state(self, items: list[dict[str, Any]] | None = None) -> ContextTokenState:
        source = items if items is not None else self._load_items()
        row = self._session_row()
        return self._context_token_state_from_row(row, source)

    def latest_context_window_usage(self) -> ContextWindowUsage | None:
        row = self._session_row()
        if row is None:
            return None
        latest_tokens = optional_int(row["latest_context_window_tokens"])
        if latest_tokens is not None:
            return ContextWindowUsage(
                used_tokens=latest_tokens,
                input_tokens=latest_tokens,
                output_tokens=0,
            )
        usage = json_object(row["usage_json"])
        if usage and usage.get("request_usage_entries"):
            return context_window_usage(usage)
        return None

    def todo_state(self) -> list[dict[str, str]]:
        row = self._session_row()
        if row is None:
            return []
        return normalize_persisted_todo_state(json_loads_or_none(row["todo_state_json"])) or []

    def _touch_index(
        self,
        *,
        active_tokens: int | None = None,
        usage: dict[str, Any] | None = None,
        latest_context_window_tokens: int | None = None,
        last_usage_tokens: int | None = None,
        pending_tokens: int | None = None,
        last_usage_record_count: int | None = None,
        todo_state: object = _UNSET,
        input_suggestion_usage: dict[str, Any] | None = None,
        session_cost: object = _UNSET,
        processes: object = _UNSET,
    ) -> None:
        with self._transaction() as conn:
            self._update_session_metadata(
                conn,
                active_tokens=active_tokens,
                usage=usage,
                latest_context_window_tokens=latest_context_window_tokens,
                last_usage_tokens=last_usage_tokens,
                pending_tokens=pending_tokens,
                last_usage_record_count=last_usage_record_count,
                todo_state=todo_state,
                input_suggestion_usage=input_suggestion_usage,
                session_cost=session_cost,
                processes=processes,
            )

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            ensure_schema(conn)
            conn.execute("begin")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        ensure_schema(conn)
        return conn

    def _session_row(self) -> sqlite3.Row | None:
        if not self.db_path.exists():
            return None
        with self._connection() as conn:
            return conn.execute(
                "select * from sessions where id = ?",
                (self.session_id,),
            ).fetchone()

    def _ensure_session_row(self, conn: sqlite3.Connection) -> sqlite3.Row:
        row = conn.execute("select * from sessions where id = ?", (self.session_id,)).fetchone()
        if row is not None:
            return row
        now = _now_ms()
        conn.execute(
            """
            insert into sessions(id, created_at, updated_at, item_count, active_tokens, pending_tokens)
            values (?, ?, ?, 0, 0, 0)
            """,
            (self.session_id, now, now),
        )
        return conn.execute("select * from sessions where id = ?", (self.session_id,)).fetchone()

    def _replace_items_conn(
        self,
        conn: sqlite3.Connection,
        items: list[dict[str, Any]],
        *,
        active_tokens: int | None,
    ) -> None:
        conn.execute("delete from session_items where session_id = ?", (self.session_id,))
        now = _now_ms()
        for index, item in enumerate(items, 1):
            conn.execute(
                """
                insert into session_items(session_id, seq, created_at, role, item_type, payload_json)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    self.session_id,
                    index,
                    now,
                    role_from_item(item),
                    item_type_from_item(item),
                    json_dumps(item),
                ),
            )
        estimated_tokens = (
            active_tokens if active_tokens is not None else self._estimate_active_tokens(items)
        )
        self._update_session_metadata(
            conn,
            active_tokens=estimated_tokens,
            latest_context_window_tokens=estimated_tokens,
            last_usage_tokens=estimated_tokens,
            pending_tokens=0,
            last_usage_record_count=len(items),
        )

    def _update_session_metadata(
        self,
        conn: sqlite3.Connection,
        *,
        active_tokens: int | None = None,
        usage: dict[str, Any] | None = None,
        latest_context_window_tokens: int | None = None,
        last_usage_tokens: int | None = None,
        pending_tokens: int | None = None,
        last_usage_record_count: int | None = None,
        todo_state: object = _UNSET,
        input_suggestion_usage: dict[str, Any] | None = None,
        session_cost: object = _UNSET,
        processes: object = _UNSET,
    ) -> None:
        self._ensure_session_row(conn)
        assignments: dict[str, Any] = {
            "updated_at": _now_ms(),
            "item_count": item_count(conn, self.session_id),
        }
        if active_tokens is not None:
            assignments["active_tokens"] = active_tokens
        if usage is not None:
            assignments["usage_json"] = json_dumps(usage)
        if latest_context_window_tokens is not None:
            assignments["latest_context_window_tokens"] = latest_context_window_tokens
        if last_usage_tokens is not None:
            assignments["last_usage_tokens"] = last_usage_tokens
        if pending_tokens is not None:
            assignments["pending_tokens"] = pending_tokens
        if last_usage_record_count is not None:
            assignments["last_usage_record_count"] = last_usage_record_count
        if input_suggestion_usage is not None:
            assignments["input_suggestion_usage_json"] = json_dumps(input_suggestion_usage)
        if todo_state is not _UNSET:
            assignments["todo_state_json"] = json_dumps(todo_state) if todo_state is not None else None
        if session_cost is not _UNSET:
            assignments["session_cost_json"] = (
                json_dumps(session_cost) if isinstance(session_cost, dict) else None
            )
        if processes is not _UNSET:
            assignments["processes_json"] = (
                json_dumps(processes) if isinstance(processes, dict) else None
            )
        title, status = preview_from_items(self._load_items_conn(conn, limit=80))
        assignments["title"] = title
        assignments["status"] = status
        sql = ", ".join(f"{key} = ?" for key in assignments)
        conn.execute(
            f"update sessions set {sql} where id = ?",
            (*assignments.values(), self.session_id),
        )

    def _load_items(self, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        with self._connection() as conn:
            return self._load_items_conn(conn, limit=limit)

    def _load_items_conn(
        self,
        conn: sqlite3.Connection,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if limit is not None:
            rows = conn.execute(
                """
                select payload_json from session_items
                where session_id = ?
                order by seq desc
                limit ?
                """,
                (self.session_id, limit),
            ).fetchall()
            rows = list(reversed(rows))
        else:
            rows = conn.execute(
                """
                select payload_json from session_items
                where session_id = ?
                order by seq
                """,
                (self.session_id,),
            ).fetchall()
        return [json_loads(row["payload_json"]) for row in rows]

    def _estimate_active_tokens(self, items: list[dict[str, Any]] | None = None) -> int:
        source = items if items is not None else self._load_items()
        return sum(estimate_tokens_for_item(item) for item in source)

    def _estimate_active_tokens_conn(self, conn: sqlite3.Connection) -> int:
        return sum(estimate_tokens_for_item(item) for item in self._load_items_conn(conn))

    def _append_loaded_cache(self, items: list[dict[str, Any]]) -> None:
        if self._loaded_items is not None:
            self._loaded_items = sanitize_sdk_items_for_replay(
                [*self._loaded_items, *(dict(item) for item in items)]
            )

    def _context_token_state_from_row(
        self,
        row: sqlite3.Row | None,
        items: list[dict[str, Any]],
    ) -> ContextTokenState:
        if row is not None:
            last_usage_tokens = optional_int(row["last_usage_tokens"])
            last_usage_record_count = optional_int(row["last_usage_record_count"])
            if last_usage_tokens is not None and last_usage_record_count is not None:
                if last_usage_record_count > len(items):
                    return ContextTokenState(active_tokens=self._estimate_active_tokens(items))
                pending_tokens = sum(
                    estimate_tokens_for_item(item) for item in items[last_usage_record_count:]
                )
                checkpoint_tokens = last_usage_tokens + pending_tokens
                estimated_tokens = self._estimate_active_tokens(items)
                active_tokens = repair_undercounted_context_tokens(
                    checkpoint_tokens,
                    estimated_tokens,
                )
                return ContextTokenState(
                    active_tokens=active_tokens,
                    last_usage_tokens=last_usage_tokens,
                    pending_tokens=max(active_tokens - last_usage_tokens, pending_tokens),
                    last_usage_record_count=last_usage_record_count,
                )
        return ContextTokenState(active_tokens=self._estimate_active_tokens(items))
