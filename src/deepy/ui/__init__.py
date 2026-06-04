from __future__ import annotations

from deepy.ui.classic import run_interactive
from deepy.ui.modern import run_tui
from deepy.ui.shared.input.commands import SlashCommand, parse_slash_command

__all__ = ["SlashCommand", "parse_slash_command", "run_interactive", "run_tui"]
