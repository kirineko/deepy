"""Process-local generation/summary leases for model selection boundaries."""
from __future__ import annotations

from collections import Counter
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from typing import Any

_active: Counter[str] = Counter()
interrupt_check: ContextVar[Any] = ContextVar("deepy_history_interrupt", default=None)


def active_work(project_root: Path) -> bool:
    return _active[str(project_root.resolve())] > 0


def generation_boundary(function: Any) -> Any:
    @wraps(function)
    async def guarded(*args: Any, **kwargs: Any) -> Any:
        owner_root = getattr(args[0], "project_root", None) if args else None
        root = str((kwargs.get("project_root") or owner_root or Path.cwd()).resolve())
        token = interrupt_check.set(kwargs.get("should_interrupt"))
        _active[root] += 1
        try:
            return await function(*args, **kwargs)
        finally:
            _active[root] -= 1
            interrupt_check.reset(token)
    return guarded


def switch_error(project_root: Path, *, busy: bool = False, pending: bool = False, session_id: str | None = None) -> str | None:
    if active_work(project_root) or busy or pending:
        return "Model unchanged: finish or cancel generation, tools, approval or subagent work before switching."
    if session_id:
        from deepy.sessions import DeepySession
        from .history_projection import history_groups
        from agents.exceptions import ModelBehaviorError
        session = DeepySession.open(project_root, session_id)
        if session.db_path.exists():
            try:
                history_groups(session.get_items_sync())
            except ModelBehaviorError as exc:
                return f"Model unchanged: {exc}"
    return None
