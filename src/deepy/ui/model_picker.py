from __future__ import annotations

from collections.abc import Callable

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

from deepy.config import DEEPSEEK_MODEL_CATALOG


REASONING_MODE_CHOICES = (
    ("none", "none  Thinking disabled"),
    ("high", "high  Thinking enabled, lower reasoning effort"),
    ("max", "max   Thinking enabled, maximum reasoning effort"),
)


def pick_model(current: str) -> str | None:
    return ModelPicker(current).run()


def pick_reasoning_mode(current: str) -> str | None:
    return ReasoningModePicker(current).run()


class ModelPicker:
    def __init__(self, current: str) -> None:
        default = current if current in {model.name for model in DEEPSEEK_MODEL_CATALOG} else None
        if default is None:
            default = DEEPSEEK_MODEL_CATALOG[0].name
        self._radio_list = RadioList[str](
            values=[
                (model.name, f"{model.name}\n  {model.description}")
                for model in DEEPSEEK_MODEL_CATALOG
            ],
            default=default,
            show_numbers=False,
            select_on_focus=True,
            open_character="",
            select_character="›",
            close_character="",
            show_cursor=False,
            show_scrollbar=False,
            container_style="class:model-list",
            checked_style="class:model-list.checked",
        )
        self._app = self._build_app(current=current)

    def run(self) -> str | None:
        return self._app.run()

    def _header_fragments(self, current: str) -> StyleAndTextTuples:
        return [
            ("class:header.title", " Select model "),
            ("class:header.meta", f" current {current} "),
        ]

    def _build_app(self, *, current: str) -> Application[str | None]:
        return _build_picker_app(
            radio_list=self._radio_list,
            header_fragments=lambda: self._header_fragments(current),
            frame_title=" Models ",
        )


class ReasoningModePicker:
    def __init__(self, current: str) -> None:
        default = current if current in {value for value, _label in REASONING_MODE_CHOICES} else "max"
        self._radio_list = RadioList[str](
            values=list(REASONING_MODE_CHOICES),
            default=default,
            show_numbers=False,
            select_on_focus=True,
            open_character="",
            select_character="›",
            close_character="",
            show_cursor=False,
            show_scrollbar=False,
            container_style="class:model-list",
            checked_style="class:model-list.checked",
        )
        self._app = self._build_app(current=default)

    def run(self) -> str | None:
        return self._app.run()

    def _header_fragments(self, current: str) -> StyleAndTextTuples:
        return [
            ("class:header.title", " Select thinking "),
            ("class:header.meta", f" current {current} "),
        ]

    def _build_app(self, *, current: str) -> Application[str | None]:
        return _build_picker_app(
            radio_list=self._radio_list,
            header_fragments=lambda: self._header_fragments(current),
            frame_title=" Thinking ",
        )


def _build_picker_app(
    *,
    radio_list: RadioList[str],
    header_fragments: Callable[[], StyleAndTextTuples],
    frame_title: str,
) -> Application[str | None]:
    kb = KeyBindings()

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event: KeyPressEvent) -> None:
        event.app.exit(result=None)

    @kb.add("enter", eager=True)
    def _select(event: KeyPressEvent) -> None:
        event.app.exit(result=radio_list.current_value)

    _ = (_cancel, _select)

    header = Window(
        FormattedTextControl(header_fragments),
        height=1,
        style="class:header",
    )
    body = Frame(
        Box(radio_list, padding=1),
        title=lambda: frame_title,
    )
    footer = Window(
        FormattedTextControl(_footer_fragments),
        height=1,
        style="class:footer",
    )
    return Application(
        layout=Layout(HSplit([header, body, footer]), focused_element=radio_list),
        key_bindings=kb,
        full_screen=True,
        erase_when_done=True,
        mouse_support=True,
        style=_model_picker_style(),
    )


def _footer_fragments() -> StyleAndTextTuples:
    return [
        ("class:footer.text", " ↑/↓ navigate"),
        ("class:footer.text", " · "),
        ("class:footer.text", "Enter select"),
        ("class:footer.text", " · "),
        ("class:footer.text", "Esc cancel "),
    ]


def _model_picker_style() -> Style:
    return Style.from_dict(
        {
            "header": "bg:#1f2333 #8be9fd",
            "header.title": "bold",
            "header.meta": "#8a90aa",
            "frame.border": "#5f6688",
            "frame.label": "#8be9fd bold",
            "model-list": "#c6d0f5",
            "model-list.checked": "#8be9fd bold",
            "radio-selected": "#8be9fd bold",
            "footer": "bg:#1f2333 #8a90aa",
            "footer.text": "#8a90aa",
        }
    )
