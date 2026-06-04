"""Read-only informational modal screen for the Modern UI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Markdown


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
        background: $panel;
        padding: 1;
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

    async def action_dismiss(self, result: None = None) -> None:
        self.dismiss(None)
