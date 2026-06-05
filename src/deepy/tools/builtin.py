from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from deepy.background_tasks import BackgroundTaskManager
from deepy.config import Settings
from deepy.todos import TodoItem, normalize_todo_items

from .constants import (
    DEFAULT_LINE_LIMIT,
    MAX_BASH_CAPTURE_CHARS,
    MAX_BASH_OUTPUT_CHARS,
    MAX_LINE_LENGTH,
    MAX_WEB_SEARCH_CALLS_PER_TURN,
)
from .file_state import FileState
from .result import ToolResult
from .runtime.interaction import InteractionToolsMixin
from .runtime.mutation_apply import MutationApplyMixin
from .runtime.read import ReadToolsMixin
from .runtime.shell import ShellToolsMixin
from .runtime.tasks import TaskToolsMixin
from .runtime.web import WebToolsMixin
from .shell_command import _build_shell_command, _extract_bash_sentinel
from .web.query import _web_search_chat

__all__ = [
    "DEFAULT_LINE_LIMIT",
    "MAX_BASH_CAPTURE_CHARS",
    "MAX_BASH_OUTPUT_CHARS",
    "MAX_LINE_LENGTH",
    "MAX_WEB_SEARCH_CALLS_PER_TURN",
    "ToolResult",
    "ToolRuntime",
    "_build_shell_command",
    "_extract_bash_sentinel",
    "_web_search_chat",
]


@dataclass
class ToolRuntime(
    ReadToolsMixin,
    MutationApplyMixin,
    ShellToolsMixin,
    TaskToolsMixin,
    WebToolsMixin,
    InteractionToolsMixin,
):
    cwd: Path
    settings: Settings
    platform_name: str = field(default_factory=lambda: sys.platform)
    file_state: FileState = field(default_factory=FileState)
    running_processes: dict[str, dict[str, str]] = field(default_factory=dict)
    background_tasks: BackgroundTaskManager = field(default_factory=BackgroundTaskManager)
    should_interrupt: Callable[[], bool] | None = None
    web_search_calls: int = 0
    todo_items: list[TodoItem] = field(default_factory=list)
    test_shell_approvals: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        raw_items = [
            item.to_dict() if isinstance(item, TodoItem) else item for item in self.todo_items
        ]
        normalized, error = normalize_todo_items(raw_items)
        if error is None and normalized is not None:
            self.todo_items = normalized
