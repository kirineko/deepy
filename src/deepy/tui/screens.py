from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Label, Markdown, OptionList, Static
from textual.widgets.option_list import Option


class InfoScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    CSS = """
    InfoScreen {
        align: center middle;
    }

    InfoScreen > Vertical {
        width: 82;
        max-width: 95%;
        height: auto;
        max-height: 90%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    InfoScreen Markdown {
        height: auto;
        max-height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, title: str, markdown: str) -> None:
        super().__init__()
        self.title_text = title
        self.markdown = markdown

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.title_text, classes="block-title")
            yield Markdown(self.markdown)
            yield Footer()

    async def action_dismiss(self, result: None = None) -> None:
        self.dismiss(None)


@dataclass(frozen=True)
class Choice:
    label: str
    value: str
    description: str = ""


class ChoiceScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
        Binding("q", "dismiss", "Cancel"),
    ]

    CSS = """
    ChoiceScreen {
        align: center middle;
    }

    ChoiceScreen > Vertical {
        width: 76;
        max-width: 95%;
        height: auto;
        max-height: 90%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    ChoiceScreen OptionList {
        height: auto;
        max-height: 1fr;
        margin-top: 1;
    }
    """

    def __init__(self, title: str, choices: list[Choice]) -> None:
        super().__init__()
        self.title_text = title
        self.choices = choices

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.title_text, classes="block-title")
            yield OptionList(
                *[
                    Option(
                        f"{choice.label}" + (f"  {choice.description}" if choice.description else ""),
                        id=choice.value,
                    )
                    for choice in self.choices
                ],
                id="choice-list",
            )
            yield Footer()

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(str(event.option_id) if event.option_id is not None else None)

    async def action_dismiss(self, result: str | None = None) -> None:
        self.dismiss(None)


@dataclass(frozen=True)
class ResetConfigResult:
    api_key: str
    model: str
    base_url: str
    theme: str


class ResetConfigScreen(ModalScreen[ResetConfigResult | None]):
    BINDINGS = [
        Binding("ctrl+s", "submit", "Save"),
        Binding("escape", "dismiss", "Cancel"),
        Binding("q", "dismiss", "Cancel"),
    ]

    CSS = """
    ResetConfigScreen {
        align: center middle;
    }

    ResetConfigScreen > Vertical {
        width: 82;
        max-width: 95%;
        height: auto;
        max-height: 90%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    ResetConfigScreen Input {
        margin: 1 0 0 0;
    }

    ResetConfigScreen .screen-help {
        color: $text-muted;
        margin: 1 0 0 0;
    }
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        theme: str,
    ) -> None:
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.theme = theme

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Reset Deepy Config", classes="block-title")
            yield Static("Ctrl+S saves. Esc cancels.", classes="screen-help")
            yield Input(value=self.api_key, placeholder="API key", password=True, id="reset-api-key")
            yield Input(value=self.model, placeholder="Model", id="reset-model")
            yield Input(value=self.base_url, placeholder="Base URL", id="reset-base-url")
            yield Input(value=self.theme, placeholder="Theme: auto|dark|light", id="reset-theme")
            yield Footer()

    def on_mount(self) -> None:
        self.query_one("#reset-api-key", Input).focus()

    def action_submit(self) -> None:
        self.dismiss(
            ResetConfigResult(
                api_key=self.query_one("#reset-api-key", Input).value.strip(),
                model=self.query_one("#reset-model", Input).value.strip(),
                base_url=self.query_one("#reset-base-url", Input).value.strip(),
                theme=self.query_one("#reset-theme", Input).value.strip(),
            )
        )

    async def action_dismiss(self, result: ResetConfigResult | None = None) -> None:
        self.dismiss(None)


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
    BINDINGS = [
        Binding("tab", "toggle_view", "View", priority=True),
        Binding("enter", "primary", "Use/Install"),
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
        width: 132;
        max-width: 98%;
        height: 86%;
        max-height: 94%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    SkillManagementScreen OptionList {
        height: 1fr;
        margin-top: 1;
    }

    SkillManagementScreen .screen-help {
        color: $text-muted;
        margin: 1 0 0 0;
    }
    """

    def __init__(
        self,
        installed: list[SkillScreenEntry],
        market: list[SkillScreenEntry],
        *,
        view: Literal["installed", "market"] = "market",
        market_error: str = "",
    ) -> None:
        super().__init__()
        self.installed = installed
        self.market = market
        self.view: Literal["installed", "market"] = view
        self.market_error = market_error

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title(), id="skill-title", classes="block-title")
            yield Static(self._help(), id="skill-help", classes="screen-help")
            yield OptionList(id="skill-options")
            yield Footer()

    def on_mount(self) -> None:
        self._refresh_options()
        self.query_one("#skill-options", OptionList).focus()

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
        if self.view == "market" and not entry.installed:
            self.dismiss(SkillScreenAction("install", entry.name, "market"))
            return
        self.dismiss(SkillScreenAction("use", entry.name, entry.source))

    def action_show_skill(self) -> None:
        entry = self._selected_entry()
        if entry is not None:
            self.dismiss(SkillScreenAction("show", entry.name, entry.source))

    def action_install_skill(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        if entry.installed:
            self.notify(f"Already installed: {entry.name}", severity="warning")
            return
        if entry.source == "market":
            self.dismiss(SkillScreenAction("install", entry.name, entry.source))

    def action_uninstall_skill(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        if not entry.removable:
            self.notify(f"Cannot uninstall built-in skill: {entry.name}", severity="warning")
            return
        self.dismiss(SkillScreenAction("uninstall", entry.name, entry.source))

    def action_refresh(self) -> None:
        self.dismiss(SkillScreenAction("refresh", source=self.view))

    async def action_dismiss(self, result: SkillScreenAction | None = None) -> None:
        self.dismiss(None)

    def _refresh_options(self) -> None:
        self.query_one("#skill-title", Label).update(self._title())
        self.query_one("#skill-help", Static).update(self._help())
        options = self.query_one("#skill-options", OptionList)
        options.clear_options()
        entries = self._entries()
        if entries:
            options.add_options(
                [
                    Option(_skill_option_label(entry), id=f"{entry.source}:{entry.name}")
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

    def _entries(self) -> list[SkillScreenEntry]:
        return self.market if self.view == "market" else self.installed

    def _selected_entry(self) -> SkillScreenEntry | None:
        options = self.query_one("#skill-options", OptionList)
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

    def _title(self) -> str:
        count = len(self._entries())
        title = "Skill Market" if self.view == "market" else "Installed Skills"
        return f"{title} ({count})"

    def _help(self) -> str:
        if self.view == "market":
            return "Tab: Installed. Enter: install/use. v detail, i install, r refresh, esc close."
        return "Tab: Market. Enter: use. v detail, u uninstall market-installed skills, r refresh, esc close."


def _skill_option_label(entry: SkillScreenEntry) -> str:
    tags: list[str] = []
    if entry.source == "market":
        if entry.version:
            tags.append(entry.version)
        if entry.installed:
            tags.append("installed")
    else:
        tags.append(entry.scope)
        if not entry.removable:
            tags.append("built-in")
        elif entry.managed_by_market:
            tags.append("market")
    suffix = f"  [{' | '.join(tags)}]" if tags else ""
    description = _truncate_single_line(entry.description, 112)
    if description:
        return f"{entry.name}{suffix}\n  {description}"
    return f"{entry.name}{suffix}"


def _truncate_single_line(text: str, limit: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(0, limit - 3)].rstrip() + "..."
