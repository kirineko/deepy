from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Label, Markdown, OptionList
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
