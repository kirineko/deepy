from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Label, Markdown, OptionList, Static
from textual.widgets.option_list import Option

from deepy.audit import PendingApproval
from deepy.ui.audit_approval_panel import build_approval_view
from deepy.ui.styles import DARK_PALETTE, UiPalette


AUDIT_APPROVAL_APPROVE = "approve"
AUDIT_APPROVAL_REJECT = "reject"


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


class AuditApprovalScreen(ModalScreen[str]):
    BINDINGS = [
        Binding("escape", "dismiss", "Reject"),
        Binding("y", "ignore_letter_shortcut", show=False),
        Binding("a", "ignore_letter_shortcut", show=False),
        Binding("n", "ignore_letter_shortcut", show=False),
        Binding("r", "ignore_letter_shortcut", show=False),
    ]

    CSS = """
    AuditApprovalScreen {
        align: center middle;
    }

    AuditApprovalScreen > Vertical {
        width: 112;
        max-width: 98%;
        height: auto;
        max-height: 92%;
        border: round $warning;
        background: $surface;
        padding: 1 2;
    }

    AuditApprovalScreen > Vertical.-has-preview {
        height: 92%;
    }

    AuditApprovalScreen .approval-summary {
        margin-top: 1;
    }

    AuditApprovalScreen .approval-preview {
        height: 1fr;
        max-height: 1fr;
        margin-top: 1;
        border: tall $warning;
        padding: 0 1;
    }

    AuditApprovalScreen OptionList {
        height: 4;
        max-height: 4;
        margin-top: 1;
    }

    AuditApprovalScreen .screen-help {
        color: $text-muted;
        margin: 1 0 0 0;
    }
    """

    def __init__(
        self,
        item: PendingApproval,
        *,
        project_root: str | Path | None = None,
        palette: UiPalette | None = None,
        width: int | None = None,
    ) -> None:
        super().__init__()
        self.item = item
        self.project_root = project_root
        self.palette = palette or DARK_PALETTE
        self.width = width
        self._title_label: Label | None = None
        self._summary: Static | None = None
        self._container: Vertical | None = None
        self._preview_container: VerticalScroll | None = None
        self._preview: Static | None = None
        self._options: OptionList | None = None

    def compose(self) -> ComposeResult:
        self._container = Vertical()
        with self._container:
            self._title_label = Label("", id="approval-title", classes="block-title")
            self._summary = Static("", id="approval-summary", classes="approval-summary")
            self._options = OptionList(id="approval-options")
            yield self._title_label
            yield self._summary
            self._preview_container = VerticalScroll(id="approval-preview", classes="approval-preview")
            with self._preview_container:
                self._preview = Static("", id="approval-preview-content")
                yield self._preview
            yield self._options
            yield Static("Use Up/Down to select, Enter to activate, Esc to reject.", classes="screen-help")

    def on_mount(self) -> None:
        self._refresh_view()
        self._approval_options().focus()

    @on(OptionList.OptionSelected, "#approval-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        option_id = str(event.option_id or "")
        if option_id == AUDIT_APPROVAL_APPROVE:
            self.dismiss(AUDIT_APPROVAL_APPROVE)
            return
        if option_id == AUDIT_APPROVAL_REJECT:
            self.dismiss(AUDIT_APPROVAL_REJECT)

    def action_ignore_letter_shortcut(self) -> None:
        return

    async def action_dismiss(self, result: str | None = None) -> None:
        self.dismiss(AUDIT_APPROVAL_REJECT)

    def _refresh_view(self) -> None:
        view = build_approval_view(
            self.item,
            palette=self.palette,
            project_root=self.project_root,
            expanded=True,
            width=self.width,
        )
        self._approval_title().update(view.title)
        summary = f"{view.target_label}: {view.target or '-'}"
        if view.metadata:
            summary += "\n" + "\n".join(f"{label}: {value}" for label, value in view.metadata)
        self._approval_summary().update(summary)
        preview = self._approval_preview()
        preview_container = self._approval_preview_container()
        container = self._approval_container()
        if view.preview is None:
            preview.update("")
            preview_container.display = False
            container.set_class(False, "-has-preview")
        else:
            preview.update(view.preview)
            preview_container.display = True
            container.set_class(True, "-has-preview")
        options = self._approval_options()
        options.clear_options()
        options.add_options(
            [
                Option("Approve", id=AUDIT_APPROVAL_APPROVE),
                Option("Reject", id=AUDIT_APPROVAL_REJECT),
            ]
        )
        options.highlighted = 0
        self.call_after_refresh(options.refresh)

    def _approval_title(self) -> Label:
        if self._title_label is None:
            raise RuntimeError("Approval title is not mounted.")
        return self._title_label

    def _approval_summary(self) -> Static:
        if self._summary is None:
            raise RuntimeError("Approval summary is not mounted.")
        return self._summary

    def _approval_container(self) -> Vertical:
        if self._container is None:
            raise RuntimeError("Approval container is not mounted.")
        return self._container

    def _approval_preview(self) -> Static:
        if self._preview is None:
            raise RuntimeError("Approval preview is not mounted.")
        return self._preview

    def _approval_preview_container(self) -> VerticalScroll:
        if self._preview_container is None:
            raise RuntimeError("Approval preview container is not mounted.")
        return self._preview_container

    def _approval_options(self) -> OptionList:
        if self._options is None:
            raise RuntimeError("Approval option list is not mounted.")
        return self._options


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
        width: 112;
        max-width: 98%;
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
    provider: str
    model: str
    base_url: str
    thinking: str
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
        provider: str,
        model: str,
        base_url: str,
        thinking: str,
        theme: str,
    ) -> None:
        super().__init__()
        self.api_key = api_key
        self.provider = provider
        self.model = model
        self.base_url = base_url
        self.thinking = thinking
        self.theme = theme

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Reset Deepy Config", classes="block-title")
            yield Static("Ctrl+S saves. Esc cancels.", classes="screen-help")
            yield Input(value=self.api_key, placeholder="API key", password=True, id="reset-api-key")
            yield Input(value=self.provider, placeholder="Provider: deepseek|openrouter|xiaomi", id="reset-provider")
            yield Input(value=self.model, placeholder="Model", id="reset-model")
            yield Input(value=self.base_url, placeholder="Base URL", id="reset-base-url")
            yield Input(value=self.thinking, placeholder="Thinking", id="reset-thinking")
            yield Input(value=self.theme, placeholder="Theme: dark|light", id="reset-theme")
            yield Footer()

    def on_mount(self) -> None:
        self.query_one("#reset-api-key", Input).focus()

    def action_submit(self) -> None:
        self.dismiss(
            ResetConfigResult(
                api_key=self.query_one("#reset-api-key", Input).value.strip(),
                provider=self.query_one("#reset-provider", Input).value.strip(),
                model=self.query_one("#reset-model", Input).value.strip(),
                base_url=self.query_one("#reset-base-url", Input).value.strip(),
                thinking=self.query_one("#reset-thinking", Input).value.strip(),
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
        self._title_label: Label | None = None
        self._help_text: Static | None = None
        self._options: OptionList | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            self._title_label = Label(self._title(), id="skill-title", classes="block-title")
            self._help_text = Static(self._help(), id="skill-help", classes="screen-help")
            self._options = OptionList(id="skill-options")
            yield self._title_label
            yield self._help_text
            yield self._options
            yield Footer()

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
        title = self._skill_title()
        help_text = self._skill_help()
        options = self._skill_options()
        title.update(self._title())
        help_text.update(self._help())
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

    def _skill_options(self) -> OptionList:
        if self._options is None:
            raise RuntimeError("Skill option list is not mounted.")
        return self._options

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
