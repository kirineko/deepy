"""Classic prompt_toolkit terminal UI."""

from __future__ import annotations

from deepy.ui.classic.terminal import run_interactive
from deepy.ui.shared.input.commands import SlashCommand, parse_slash_command

__all__ = ["SlashCommand", "parse_slash_command", "run_interactive"]
