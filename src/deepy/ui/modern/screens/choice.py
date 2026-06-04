"""Generic choice and text-input modal screens for the Modern UI."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.widgets.option_list import Option


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
        background: $panel;
        padding: 1;
    }

    ChoiceScreen OptionList {
        height: auto;
        max-height: 1fr;
        margin-top: 0;
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

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_choice_list)

    def _focus_choice_list(self) -> None:
        try:
            self.query_one(OptionList).focus()
        except NoMatches:
            return

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(str(event.option_id) if event.option_id is not None else None)

    async def action_dismiss(self, result: str | None = None) -> None:
        self.dismiss(None)


class TextInputScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("enter", "submit", "Submit"),
        Binding("escape", "dismiss", "Cancel"),
        Binding("q", "dismiss", "Cancel"),
    ]

    CSS = """
    TextInputScreen {
        align: center middle;
    }

    TextInputScreen > Vertical {
        width: 92;
        max-width: 95%;
        height: auto;
        max-height: 90%;
        background: $panel;
        padding: 1;
    }

    TextInputScreen Input {
        margin: 0;
    }

    TextInputScreen .screen-help {
        color: $text-muted;
        margin: 0;
    }
    """

    def __init__(
        self,
        title: str,
        *,
        value: str = "",
        placeholder: str = "",
        password: bool = False,
        help_text: str = "Enter submit · Esc cancel",
    ) -> None:
        super().__init__()
        self.title_text = title
        self.value = value
        self.placeholder = placeholder
        self.password = password
        self.help_text = help_text

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.title_text, classes="block-title")
            yield Static(self.help_text, classes="screen-help")
            yield Input(
                value=self.value,
                placeholder=self.placeholder,
                password=self.password,
                id="text-input",
            )

    def on_mount(self) -> None:
        self.query_one("#text-input", Input).focus()

    @on(Input.Submitted, "#text-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss(event.value.strip())

    def action_submit(self) -> None:
        self.dismiss(self.query_one("#text-input", Input).value.strip())

    async def action_dismiss(self, result: str | None = None) -> None:
        self.dismiss(None)
