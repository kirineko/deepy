"""Base transcript block and the simple display blocks of the Modern UI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import Label, Markdown, Static

from deepy.ui.modern.render.transcript import TranscriptKind, transcript_display


class TranscriptBlock(Vertical, can_focus=True):
    BINDINGS = [
        Binding("space", "toggle_expand", "Expand", show=False),
    ]

    expanded = reactive(False)

    def __init__(
        self,
        title: str,
        body: str = "",
        *,
        classes: str | None = None,
        kind: TranscriptKind = "info",
    ) -> None:
        self.display_model = transcript_display(kind)
        super().__init__(classes=f"transcript-block {classes or self.display_model.css_class}".strip())
        self.title = title or self.display_model.label
        self.body = body

    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="block-title")
        yield Static(self.body, classes="block-body")

    def action_toggle_expand(self) -> None:
        self.expanded = not self.expanded
        if self.expanded:
            self.add_class("-expanded")
        else:
            self.remove_class("-expanded")


class InfoBlock(Vertical, can_focus=True):
    def __init__(self, text: str) -> None:
        self.display_model = transcript_display("info")
        super().__init__(classes="transcript-block info-block")
        self.body = text

    def compose(self) -> ComposeResult:
        with Horizontal(classes="role-line info-role-line"):
            yield Label("·", classes="block-title role-marker info-marker")
            yield Static(self.body, classes="block-body")


class UserBlock(TranscriptBlock):
    def __init__(self, text: str) -> None:
        display = transcript_display("user")
        super().__init__(display.label, text, classes=display.css_class, kind="user")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="role-line user-role-line"):
            yield Label(self.title, classes="block-title role-marker user-marker")
            yield Static(self.body, classes="block-body")


class ThinkingBlock(TranscriptBlock):
    def __init__(self, text: str = "") -> None:
        display = transcript_display("reasoning")
        super().__init__(display.label, text, classes=display.css_class, kind="reasoning")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="role-line thinking-role-line"):
            yield Label(self.display_model.label, classes="block-title role-marker thinking-marker")
            yield Static(self.body, classes="block-body thinking-body")

    def update_text(self, text: str) -> None:
        self.body = text
        self.query_one(".block-body", Static).update(text)


class AssistantBlock(Vertical, can_focus=True):
    def __init__(self, markdown: str = "", *, active: bool = False) -> None:
        self.display_model = transcript_display("assistant")
        super().__init__(classes="transcript-block assistant-block")
        self.markdown = markdown
        self.active = active
        if active:
            self.add_class("-active")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="role-line assistant-role-line"):
            yield Label(self._title_text(), classes="block-title role-marker assistant-marker")
            yield Markdown(self.markdown, classes="block-markdown")

    async def update_markdown(self, markdown: str) -> None:
        self.markdown = markdown
        await self.query_one(Markdown).update(markdown)

    def set_active(self, active: bool) -> None:
        self.active = active
        self.set_class(active, "-active")
        self.query_one(".block-title", Label).update(self._title_text())

    def _title_text(self) -> str:
        return self.display_model.label


class ErrorBlock(TranscriptBlock):
    def __init__(self, error: str) -> None:
        display = transcript_display("error")
        super().__init__(display.label, error, classes=display.css_class, kind="error")


class StatusBar(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label("Deepy Modern UI", id="status-left")
        yield Label("Idle", id="status-right")

    def update_status(self, status: str, context: str | None = None) -> None:
        try:
            if context is not None:
                self.query_one("#status-left", Label).update(context)
            self.query_one("#status-right", Label).update(status)
        except NoMatches:
            return
