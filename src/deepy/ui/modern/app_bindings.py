"""Shared bindings monkeypatched through ``deepy.ui.modern.app`` in tests."""

from __future__ import annotations

from deepy.llm.context import estimate_tokens_for_text
from deepy.mcp import load_mcp_config
from deepy.sessions import list_session_entries
from deepy.sessions.manager import DeepySessionManager
from deepy.skill_market import (
    install_market_skill,
    list_installed_skills,
    search_market_skills,
    uninstall_market_skill,
    update_market_skill,
)
from deepy.skills import discover_skills
from deepy.status import fetch_deepseek_balance
from deepy.ui.shared.local_command import run_local_command, shell_tool_result_json

__all__ = [
    "DeepySessionManager",
    "discover_skills",
    "estimate_tokens_for_text",
    "fetch_deepseek_balance",
    "install_market_skill",
    "list_installed_skills",
    "list_session_entries",
    "load_mcp_config",
    "run_local_command",
    "search_market_skills",
    "shell_tool_result_json",
    "uninstall_market_skill",
    "update_market_skill",
]
