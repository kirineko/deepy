"""Incremental checkpoint metadata using the existing session transaction."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deepy.llm.history_projection import fingerprint, model_identity
from deepy.usage import TokenUsage, merge_usage
from .store_helpers import json_dumps, json_object

if TYPE_CHECKING:
    from deepy.config import Settings
    from .session import DeepySession


def read_history_state(session: DeepySession) -> dict[str, Any]:
    with session._transaction() as conn:
        row = session._ensure_session_row(conn)
        return json_object(row["history_state_json"]) or {}


def record_checkpoint(session: DeepySession, settings: Settings, prefix: str) -> None:
    with session._transaction() as conn:
        row = session._ensure_session_row(conn)
        items = session._load_items_conn(conn)
        state = json_object(row["history_state_json"]) or {}
        target = model_identity(settings.model.provider, settings.model.name, settings.model.base_url)
        state["checkpoint"] = {"target": target, "prefix": prefix,
                               "revision": fingerprint(items), "count": len(items)}
        state["last_successful_model"] = target
        conn.execute("update sessions set history_state_json = ? where id = ?",
                     (json_dumps(state), session.session_id))


def record_summary_usage(session: DeepySession, usage: TokenUsage, model: dict[str, str] | None = None) -> None:
    if not usage.known:
        return
    with session._transaction() as conn:
        row = session._ensure_session_row(conn)
        state = json_object(row["history_state_json"]) or {}
        state["summary_usage"] = merge_usage(state.get("summary_usage"), usage).to_dict()
        if model:
            key = f"{model['provider']}/{model['model']}"
            by_model = state.setdefault("summary_usage_by_model", {})
            by_model[key] = merge_usage(by_model.get(key), usage).to_dict()
            state["summary_requests"] = [*state.get("summary_requests", []),
                                         {"model": model, "usage": usage.to_dict()}][-32:]
        session._update_session_metadata(conn, usage=merge_usage(json_object(row["usage_json"]), usage).to_dict())
        conn.execute("update sessions set history_state_json = ? where id = ?",
                     (json_dumps(state), session.session_id))
