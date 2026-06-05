"""Shared bindings monkeypatched through ``deepy.ui.classic.terminal`` in tests."""

from __future__ import annotations

from deepy.background_tasks import BackgroundTaskManager
from deepy.llm.context import estimate_tokens_for_text
from deepy.mcp import DeepyMcpRuntime
from deepy.sessions import list_session_entries
from deepy.status import fetch_deepseek_balance
from deepy.ui.classic.markdown import render_markdown
from deepy.ui.classic.pickers.audit_approval_picker import pick_audit_approval
from deepy.config import ui_theme_from_selection, ui_theme_number
from deepy.ui.classic.commands.config_choices import _print_theme_choices
from deepy.ui.classic.prompt.prompt_input import create_prompt_session, prompt_for_input
from deepy.ui.classic.terminal_types import msvcrt
from rich.console import Console
from rich.prompt import Prompt
from deepy.ui.shared.local_command import run_local_command
from deepy.ui.shared.render.message_view import render_tool_diff_preview

def _prompt_theme_choice(default: str = "dark") -> str:
    _print_theme_choices(Console())
    value = Prompt.ask("UI theme number", default=ui_theme_number(default))
    return ui_theme_from_selection(value, default=default)


__all__ = [
    "_prompt_theme_choice",
    "BackgroundTaskManager",
    "DeepyMcpRuntime",
    "create_prompt_session",
    "estimate_tokens_for_text",
    "fetch_deepseek_balance",
    "list_session_entries",
    "msvcrt",
    "pick_audit_approval",
    "prompt_for_input",
    "render_markdown",
    "render_tool_diff_preview",
    "run_local_command",
]
