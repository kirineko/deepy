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

from deepy.config import PROVIDER_CATALOG, provider_info_for, thinking_modes_for_provider


REASONING_MODE_CHOICES = (
    ("none", "none  Thinking disabled"),
    ("high", "high  Thinking enabled, lower reasoning effort"),
    ("max", "max   Thinking enabled, maximum reasoning effort"),
)
SWITCH_ONLY_THINKING_CHOICES = (
    ("disabled", "disabled  Thinking disabled"),
    ("enabled", "enabled   Thinking enabled"),
)
OPENROUTER_REASONING_CHOICES = (
    ("enabled", "enabled  Reasoning enabled with model default settings"),
    ("disabled", "disabled Reasoning disabled"),
    ("xhigh", "xhigh    Largest reasoning token allocation"),
    ("high", "high     Large reasoning token allocation"),
    ("medium", "medium   Moderate reasoning token allocation"),
    ("low", "low      Smaller reasoning token allocation"),
    ("minimal", "minimal  Minimal reasoning token allocation"),
    ("none", "none     Thinking disabled"),
)
LOCALHOST_REASONING_CHOICES = (
    ("none", "none    Thinking disabled"),
    ("low", "low     Smaller reasoning token allocation"),
    ("medium", "medium  Moderate reasoning token allocation (default)"),
    ("high", "high    Large reasoning token allocation"),
    ("xhigh", "xhigh   Largest reasoning token allocation"),
)


def thinking_mode_choices(provider: str) -> tuple[tuple[str, str], ...]:
    if provider == "openrouter":
        return OPENROUTER_REASONING_CHOICES
    if provider == "localhost":
        return LOCALHOST_REASONING_CHOICES
    modes = thinking_modes_for_provider(provider)
    if modes == ("disabled", "enabled"):
        return SWITCH_ONLY_THINKING_CHOICES
    return REASONING_MODE_CHOICES


def provider_api_key_reconfiguration_message(provider: str) -> str:
    provider_info = provider_info_for(provider)
    message = (
        f"Provider switched to {provider}. "
        "Reconfigure the API key for this provider with /reset or `deepy config setup`."
    )
    if provider_info.api_key_url:
        message += f" Create an API key at {provider_info.api_key_url}"
    return message


def pick_provider(current: str) -> str | None:
    return ProviderPicker(current).run()


def pick_model(current: str, *, provider: str = "deepseek") -> str | None:
    return ModelPicker(current, provider=provider).run()


def pick_reasoning_mode(current: str, *, provider: str = "deepseek") -> str | None:
    return ReasoningModePicker(current, provider=provider).run()


class ProviderPicker:
    def __init__(self, current: str) -> None:
        default = current if current in {provider.id for provider in PROVIDER_CATALOG} else "deepseek"
        self._radio_list = RadioList[str](
            values=[
                (provider.id, f"{provider.id}\n  {provider.description}")
                for provider in PROVIDER_CATALOG
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
            ("class:header.title", " Select provider "),
            ("class:header.meta", f" current {current} "),
        ]

    def _build_app(self, *, current: str) -> Application[str | None]:
        return _build_picker_app(
            radio_list=self._radio_list,
            header_fragments=lambda: self._header_fragments(current),
            frame_title=" Providers ",
        )


class ModelPicker:
    def __init__(self, current: str, *, provider: str) -> None:
        provider_info = provider_info_for(provider)
        default = current if current in {model.name for model in provider_info.models} else None
        if default is None:
            default = provider_info.default_model
        self._radio_list = RadioList[str](
            values=[
                (model.name, f"{model.name}\n  {model.description}")
                for model in provider_info.models
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
    def __init__(self, current: str, *, provider: str) -> None:
        choices = thinking_mode_choices(provider)
        default_mode = provider_info_for(provider).default_thinking_mode
        default = current if current in {value for value, _label in choices} else default_mode
        self._radio_list = RadioList[str](
            values=list(choices),
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
