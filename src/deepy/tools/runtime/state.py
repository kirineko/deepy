from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from deepy.background_tasks import BackgroundTaskManager
from deepy.config import Settings
from deepy.todos import TodoItem

from ..file_state import FileState


class ToolRuntimeState:
    cwd: Path
    settings: Settings
    platform_name: str
    file_state: FileState
    running_processes: dict[str, dict[str, str]]
    background_tasks: BackgroundTaskManager
    should_interrupt: Callable[[], bool] | None
    web_search_calls: int
    todo_items: list[TodoItem]
    test_shell_approvals: dict[str, str]
