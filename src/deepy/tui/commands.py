from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from textual.command import DiscoveryHit, Hit, Hits, Provider

from deepy.ui.slash_commands import (
    SlashCommandItem,
    categorized_command_markdown,
    slash_command_priority,
    textual_builtin_commands,
)

if TYPE_CHECKING:
    from deepy.tui.app import DeepyTuiApp


UNSUPPORTED_TUI_COMMANDS: dict[str, str] = {}


def command_catalog_markdown() -> str:
    lines = [categorized_command_markdown(ranked_tui_commands())]
    if UNSUPPORTED_TUI_COMMANDS:
        lines.extend(["", "", "## Not Supported Yet"])
        for message in UNSUPPORTED_TUI_COMMANDS.values():
            lines.append(f"- {message}")
    return "\n".join(lines).strip()


def command_by_name(name: str) -> SlashCommandItem | None:
    normalized = name.lower().lstrip("/")
    return next(
        (
            command
            for command in textual_builtin_commands()
            if command.name == normalized or normalized in command.aliases
        ),
        None,
    )


def ranked_tui_commands() -> list[SlashCommandItem]:
    return sorted(
        textual_builtin_commands(),
        key=lambda command: (slash_command_priority(command.name), command.name),
    )


class DeepyCommandProvider(Provider):
    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        app = self.app
        matches = []
        for command in ranked_tui_commands():
            candidate = f"{command.label} {command.description} {command.category}"
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
                help=f"{command.category}: {command.description}",
            )

    async def discover(self) -> Hits:
        app = self.app
        for command in ranked_tui_commands():
            yield DiscoveryHit(
                command.label,
                partial(app.invoke_tui_command, command.name),
                help=f"{command.category}: {command.description}",
            )

    @property
    def app(self) -> DeepyTuiApp:
        from deepy.tui.app import DeepyTuiApp

        app = self.screen.app
        assert isinstance(app, DeepyTuiApp)
        return app
