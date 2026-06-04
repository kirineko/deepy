from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding import KeyPressEvent
from prompt_toolkit.layout import HSplit
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Box
from prompt_toolkit.widgets import Frame
from prompt_toolkit.widgets import RadioList


THEME_CHOICES = (
    ("dark", "dark  Optimized for dark terminal backgrounds"),
    ("light", "light Optimized for light terminal backgrounds"),
)


def pick_theme(current: str) -> str | None:
    return ThemePicker(current).run()


class ThemePicker:
    def __init__(self, current: str) -> None:
        default = current if current in {value for value, _label in THEME_CHOICES} else "dark"
        self._radio_list = RadioList[str](
            values=list(THEME_CHOICES),
            default=default,
            show_numbers=False,
            select_on_focus=True,
            open_character="",
            select_character="›",
            close_character="",
            show_cursor=False,
            show_scrollbar=False,
            container_style="class:theme-list",
            checked_style="class:theme-list.checked",
        )
        self._app = self._build_app(current=default)

    def run(self) -> str | None:
        return self._app.run()

    def _header_fragments(self, current: str) -> StyleAndTextTuples:
        return [
            ("class:header.title", " Select UI theme "),
            ("class:header.meta", f" current {current} "),
        ]

    def _footer_fragments(self) -> StyleAndTextTuples:
        return [
            ("class:footer.text", " ↑/↓ navigate"),
            ("class:footer.text", " · "),
            ("class:footer.text", "Enter select"),
            ("class:footer.text", " · "),
            ("class:footer.text", "Esc cancel "),
        ]

    def _build_app(self, *, current: str) -> Application[str | None]:
        kb = KeyBindings()

        @kb.add("escape")
        @kb.add("c-c")
        def _cancel(event: KeyPressEvent) -> None:
            event.app.exit(result=None)

        @kb.add("enter", eager=True)
        def _select(event: KeyPressEvent) -> None:
            event.app.exit(result=self._radio_list.current_value)

        _ = (_cancel, _select)

        header = Window(
            FormattedTextControl(lambda: self._header_fragments(current)),
            height=1,
            style="class:header",
        )
        body = Frame(
            Box(self._radio_list, padding=1),
            title=lambda: " Themes ",
        )
        footer = Window(
            FormattedTextControl(self._footer_fragments),
            height=1,
            style="class:footer",
        )
        return Application(
            layout=Layout(HSplit([header, body, footer]), focused_element=self._radio_list),
            key_bindings=kb,
            full_screen=True,
            erase_when_done=True,
            mouse_support=True,
            style=_theme_picker_style(),
        )


def _theme_picker_style() -> Style:
    return Style.from_dict(
        {
            "header": "bg:#1f2333 #8be9fd",
            "header.title": "bold",
            "header.meta": "#8a90aa",
            "frame.border": "#5f6688",
            "frame.label": "#8be9fd bold",
            "theme-list": "#c6d0f5",
            "theme-list.checked": "#8be9fd bold",
            "radio-selected": "#8be9fd bold",
            "footer": "bg:#1f2333 #8a90aa",
            "footer.text": "#8a90aa",
        }
    )
