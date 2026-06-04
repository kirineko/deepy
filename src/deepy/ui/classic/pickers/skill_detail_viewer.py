"""Full-screen viewer for a single skill's details."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import Box, Frame, TextArea

from deepy.ui.classic.pickers.skill_picker_types import (
    SkillDetailView,
    _skill_picker_style,
    format_skill_detail_text,
)


def show_skill_detail_view(detail: SkillDetailView) -> None:
    SkillDetailViewer(detail).run()


class SkillDetailViewer:
    def __init__(self, detail: SkillDetailView) -> None:
        self._detail = detail
        self._body = TextArea(
            text=format_skill_detail_text(detail),
            read_only=True,
            scrollbar=True,
            line_numbers=False,
            wrap_lines=True,
            focusable=True,
            style="class:skill-list",
        )
        self._app = self._build_app()

    def run(self) -> None:
        self._app.run()

    def _header_fragments(self) -> StyleAndTextTuples:
        scope = f" {self._detail.scope} " if self._detail.scope else ""
        return [
            ("class:header.title", " Skill details "),
            ("class:header.meta", f" {self._detail.name}"),
            ("class:header.meta", scope),
        ]

    def _footer_fragments(self) -> StyleAndTextTuples:
        return [
            ("class:footer.text", " ↑/↓ scroll"),
            ("class:footer.text", " · "),
            ("class:footer.text", "PgUp/PgDn page"),
            ("class:footer.text", " · "),
            ("class:footer.text", "Esc/q close "),
        ]

    def _build_app(self) -> Application[None]:
        kb = KeyBindings()

        @kb.add("escape")
        @kb.add("c-c")
        @kb.add("q")
        def _close(event: KeyPressEvent) -> None:
            event.app.exit()

        _ = _close

        header = Window(
            FormattedTextControl(self._header_fragments),
            height=1,
            style="class:header",
        )
        body = Frame(Box(self._body, padding=1), title=lambda: " View Skill ")
        footer = Window(
            FormattedTextControl(self._footer_fragments),
            height=1,
            style="class:footer",
        )
        return Application(
            layout=Layout(HSplit([header, body, footer]), focused_element=self._body),
            key_bindings=kb,
            full_screen=True,
            erase_when_done=True,
            mouse_support=True,
            style=_skill_picker_style(),
        )
