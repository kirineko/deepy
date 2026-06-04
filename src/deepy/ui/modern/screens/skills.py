"""Skill management modal screen and its label helpers for the Modern UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option


@dataclass(frozen=True)
class SkillScreenEntry:
    name: str
    scope: str
    description: str = ""
    version: str = ""
    path: str = ""
    installed: bool = False
    managed_by_market: bool = False
    source: Literal["installed", "market"] = "installed"
    removable: bool = True


@dataclass(frozen=True)
class SkillScreenAction:
    action: Literal["use", "show", "install", "uninstall", "update", "refresh"]
    name: str = ""
    source: Literal["installed", "market"] = "installed"


class SkillManagementScreen(ModalScreen[SkillScreenAction | None]):
    class ActionRequested(Message):
        def __init__(self, screen: SkillManagementScreen, action: SkillScreenAction) -> None:
            self.screen = screen
            self.action = action
            super().__init__()

    BINDINGS = [
        Binding("tab", "toggle_view", "View", priority=True),
        Binding("enter", "primary", "Detail"),
        Binding("v", "show_skill", "View"),
        Binding("i", "install_skill", "Install"),
        Binding("u", "uninstall_skill", "Uninstall"),
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    CSS = """
    SkillManagementScreen {
        align: center middle;
    }

    SkillManagementScreen > Vertical {
        width: 172;
        max-width: 98%;
        height: 82%;
        max-height: 94%;
        background: $panel;
        padding: 1 2;
    }

    SkillManagementScreen OptionList {
        height: 1fr;
        margin-top: 0;
    }

    SkillManagementScreen .screen-help {
        color: $text-muted;
        margin: 0;
    }

    SkillManagementScreen .screen-tabs {
        height: 1;
        color: $text-muted;
        margin: 0;
    }
    """

    def __init__(
        self,
        installed: list[SkillScreenEntry],
        market: list[SkillScreenEntry],
        *,
        view: Literal["installed", "market"] = "market",
        market_error: str = "",
        market_loading: bool = False,
    ) -> None:
        super().__init__()
        self.installed = installed
        self.market = market
        self.view: Literal["installed", "market"] = view
        self.market_error = market_error
        self.market_loading = market_loading
        self.loading_message = "Loading skill market..." if market_loading else ""
        self._title_label: Label | None = None
        self._tabs_text: Static | None = None
        self._help_text: Static | None = None
        self._options: OptionList | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            self._title_label = Label(self._title(), id="skill-title", classes="block-title")
            self._tabs_text = Static(self._tabs(), id="skill-tabs", classes="screen-tabs")
            self._help_text = Static(self._help(), id="skill-help", classes="screen-help")
            self._options = OptionList(id="skill-options")
            yield self._title_label
            yield self._tabs_text
            yield self._help_text
            yield self._options

    def on_mount(self) -> None:
        self._refresh_options()
        self._skill_options().focus()

    @on(OptionList.OptionSelected, "#skill-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.action_primary()

    def action_toggle_view(self) -> None:
        self.view = "market" if self.view == "installed" else "installed"
        self._refresh_options()

    def action_primary(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        self._request(SkillScreenAction("show", entry.name, entry.source))

    def action_show_skill(self) -> None:
        entry = self._selected_entry()
        if entry is not None:
            self._request(SkillScreenAction("show", entry.name, entry.source))

    def action_install_skill(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        if entry.installed:
            self.notify(f"Already installed: {entry.name}", severity="warning")
            return
        if entry.source == "market":
            self._request(SkillScreenAction("install", entry.name, entry.source))

    def action_uninstall_skill(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        if not entry.removable:
            self.notify(f"Cannot uninstall built-in skill: {entry.name}", severity="warning")
            return
        self._request(SkillScreenAction("uninstall", entry.name, entry.source))

    def action_refresh(self) -> None:
        self._request(SkillScreenAction("refresh", source=self.view))

    async def action_dismiss(self, result: SkillScreenAction | None = None) -> None:
        self.dismiss(None)

    def update_installed(self, installed: list[SkillScreenEntry]) -> None:
        self.installed = installed
        self._refresh_options()

    def set_market_loading(self, message: str = "Loading skill market...") -> None:
        self.market_loading = True
        self.loading_message = message
        self.market_error = ""
        self._refresh_options()

    def update_market(self, market: list[SkillScreenEntry], *, market_error: str = "") -> None:
        self.market = market
        self.market_error = market_error
        self.market_loading = False
        self.loading_message = ""
        self._refresh_options()

    def set_operation_loading(self, message: str) -> None:
        self.loading_message = message
        self._refresh_options()

    def clear_operation_loading(self) -> None:
        if not self.market_loading:
            self.loading_message = ""
            self._refresh_options()

    def _refresh_options(self) -> None:
        title = self._skill_title()
        tabs = self._skill_tabs()
        help_text = self._skill_help()
        options = self._skill_options()
        title.update(self._title())
        tabs.update(self._tabs())
        help_text.update(self._help())
        options.clear_options()
        if self.loading_message:
            options.add_option(Option(_skill_status_label(self.loading_message), id="empty"))
            options.highlighted = 0
            self.call_after_refresh(options.refresh)
            return
        entries = self._entries()
        if entries:
            row_width = self._row_width()
            options.add_options(
                [
                    Option(_skill_option_label(entry, width=row_width), id=f"{entry.source}:{entry.name}")
                    for entry in entries
                ]
            )
            options.highlighted = 0
            self.call_after_refresh(options.refresh)
            return
        empty = self.market_error if self.view == "market" and self.market_error else "No skills found."
        options.add_option(Option(empty, id="empty"))
        options.highlighted = 0
        self.call_after_refresh(options.refresh)

    def _request(self, action: SkillScreenAction) -> None:
        self.post_message(self.ActionRequested(self, action))

    def _row_width(self) -> int:
        width = self.size.width - 8
        if width <= 0:
            width = 150
        return max(96, min(width, 168))

    def _entries(self) -> list[SkillScreenEntry]:
        return self.market if self.view == "market" else self.installed

    def _selected_entry(self) -> SkillScreenEntry | None:
        options = self._skill_options()
        if options.option_count == 0 or options.highlighted is None:
            return None
        option_id = str(options.get_option_at_index(options.highlighted).id or "")
        if option_id == "empty":
            return None
        source, _, name = option_id.partition(":")
        for entry in self._entries():
            if entry.source == source and entry.name == name:
                return entry
        return None

    def _skill_title(self) -> Label:
        if self._title_label is None:
            raise RuntimeError("Skill title widget is not mounted.")
        return self._title_label

    def _skill_help(self) -> Static:
        if self._help_text is None:
            raise RuntimeError("Skill help widget is not mounted.")
        return self._help_text

    def _skill_tabs(self) -> Static:
        if self._tabs_text is None:
            raise RuntimeError("Skill tabs widget is not mounted.")
        return self._tabs_text

    def _skill_options(self) -> OptionList:
        if self._options is None:
            raise RuntimeError("Skill option list is not mounted.")
        return self._options

    def _title(self) -> str:
        return "Skills"

    def _tabs(self) -> str:
        market = f"Market {len(self.market)}"
        installed = f"Installed {len(self.installed)}"
        if self.view == "market":
            market = f"[{market}]"
        else:
            installed = f"[{installed}]"
        return f"{market}  {installed}"

    def _help(self) -> str:
        if self.view == "market":
            return "Tab switch view · Enter detail · v detail · i install · r refresh · Esc close"
        return "Tab switch view · Enter detail · v detail · u uninstall · r refresh · Esc close"


def _skill_status_label(message: str) -> Text:
    label = Text(no_wrap=True, overflow="ellipsis")
    label.append(message, style="#a5b4fc")
    return label


def _skill_option_label(entry: SkillScreenEntry, *, width: int = 150) -> Text:
    label = Text(no_wrap=True, overflow="ellipsis")
    label.append(entry.name, style="bold #e5e7eb")
    tags: list[tuple[str, str]] = []
    if entry.source == "market":
        tags.append(("market", "#c084fc"))
        if entry.installed:
            tags.append(("installed", "#86efac"))
    else:
        scope_style = "#7dd3fc" if entry.scope == "project" else "#fbbf24"
        tags.append((entry.scope, scope_style))
        if not entry.removable:
            tags.append(("built-in", "#a5b4fc"))
        elif entry.managed_by_market:
            tags.append(("market", "#c084fc"))
    if tags:
        label.append("  ")
        for index, (tag, style) in enumerate(tags):
            if index:
                label.append(" ")
            label.append(f"[{tag}]", style=style)
    max_row_width = max(72, width)
    description_width = max(24, max_row_width - len(label.plain) - 5)
    description = _truncate_single_line(entry.description, description_width)
    if description:
        label.append("  - ", style="#6b7280")
        label.append(description, style="#a5b4fc")
    return label


def _truncate_single_line(text: str, limit: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(0, limit - 3)].rstrip() + "..."
