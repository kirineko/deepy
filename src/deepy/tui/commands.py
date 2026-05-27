from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from textual.command import DiscoveryHit, Hit, Hits, Provider

from deepy.ui.slash_commands import slash_command_priority

if TYPE_CHECKING:
    from deepy.tui.app import DeepyTuiApp


@dataclass(frozen=True)
class TuiCommand:
    name: str
    label: str
    description: str
    group: str


TUI_COMMANDS: tuple[TuiCommand, ...] = (
    TuiCommand("help", "/help", "Show commands, keybindings, and TUI state", "Help"),
    TuiCommand("status", "/status", "Show project, session, MCP, and settings status", "Help"),
    TuiCommand("new", "/new", "Start a fresh TUI session", "Session"),
    TuiCommand("sessions", "/sessions", "List project sessions", "Session"),
    TuiCommand("resume", "/resume", "Resume a previous session", "Session"),
    TuiCommand("compact", "/compact", "Compact the active session context", "Session"),
    TuiCommand("skills", "/skills", "Manage local and market skills", "Skills"),
    TuiCommand("model", "/model", "Select model and reasoning mode", "Settings"),
    TuiCommand("view", "/view", "Hide or show reasoning transcript text", "Settings"),
    TuiCommand("input-suggestion", "/input-suggestion", "Toggle input suggestions", "Settings"),
    TuiCommand("theme", "/theme", "Select UI theme", "Settings"),
    TuiCommand("init", "/init", "Create or update project AGENTS.md", "System"),
    TuiCommand("reset", "/reset", "Reset config and run TUI setup", "System"),
    TuiCommand("mcp", "/mcp", "Show MCP status", "Tools"),
    TuiCommand("ps", "/ps", "Show background tasks", "Tools"),
    TuiCommand("stop", "/stop", "Choose background tasks to stop", "Tools"),
    TuiCommand("exit", "/exit", "Quit Deepy TUI", "System"),
)

UNSUPPORTED_TUI_COMMANDS: dict[str, str] = {}


def command_catalog_markdown() -> str:
    lines: list[str] = ["# Deepy TUI Commands", ""]
    current_group = ""
    for command in TUI_COMMANDS:
        if command.group != current_group:
            current_group = command.group
            lines.extend(["", f"## {current_group}"])
        lines.append(f"- **{command.label}** - {command.description}")
    if UNSUPPORTED_TUI_COMMANDS:
        lines.extend(["", "## Not Supported Yet"])
        for message in UNSUPPORTED_TUI_COMMANDS.values():
            lines.append(f"- {message}")
    return "\n".join(lines).strip()


def command_by_name(name: str) -> TuiCommand | None:
    return next((command for command in TUI_COMMANDS if command.name == name), None)


def ranked_tui_commands() -> list[TuiCommand]:
    return sorted(TUI_COMMANDS, key=lambda command: (slash_command_priority(command.name), command.name))


class DeepyCommandProvider(Provider):
    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        app = self.app
        matches = []
        for command in ranked_tui_commands():
            candidate = f"{command.label} {command.description} {command.group}"
            score = matcher.match(candidate)
            if score > 0:
                matches.append((score, command))
        for score, command in sorted(
            matches,
            key=lambda item: (-item[0], slash_command_priority(item[1].name), item[1].name),
        ):
            yield Hit(
                score,
                matcher.highlight(command.label),
                partial(app.invoke_tui_command, command.name),
                help=f"{command.group}: {command.description}",
            )

    async def discover(self) -> Hits:
        app = self.app
        for command in ranked_tui_commands():
            yield DiscoveryHit(
                command.label,
                partial(app.invoke_tui_command, command.name),
                help=f"{command.group}: {command.description}",
            )

    @property
    def app(self) -> DeepyTuiApp:
        from deepy.tui.app import DeepyTuiApp

        app = self.screen.app
        assert isinstance(app, DeepyTuiApp)
        return app
