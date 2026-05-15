from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

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

from deepy.ui.session_list import format_session_title


_EMPTY_SESSION_ID = "__empty__"


@dataclass(frozen=True)
class ResumeSessionPreview:
    id: str
    title: str
    status: str
    updated_at: int
    active_tokens: int


def pick_resume_session(previews: Sequence[ResumeSessionPreview]) -> str | None:
    if not previews:
        return None
    return ResumeSessionPicker(previews).run()


def format_session_time(timestamp: int) -> str:
    if timestamp <= 0:
        return "unknown time"
    seconds = timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
    return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M:%S")


def format_resume_session_label(preview: ResumeSessionPreview) -> str:
    title = format_session_title(preview.title, max_chars=70)
    meta = (
        f"  {format_session_time(preview.updated_at)}"
        f" · {preview.status}"
        f" · history estimate {preview.active_tokens:,}"
        f" · {preview.id[:8]}"
    )
    return f"{title}\n{meta}"


def format_resume_session_choices(
    previews: Sequence[ResumeSessionPreview],
    *,
    max_entries: int = 10,
) -> str:
    if not previews:
        return "No sessions found."
    lines = [f"Resume a session ({len(previews)} total)"]
    for index, preview in enumerate(previews[:max_entries], 1):
        lines.append(f"{index}. {format_resume_session_label(preview)}")
    remaining = len(previews) - min(len(previews), max_entries)
    if remaining > 0:
        lines.append(f"...and {remaining} more.")
    return "\n".join(lines)


class ResumeSessionPicker:
    def __init__(self, previews: Sequence[ResumeSessionPreview]) -> None:
        self._previews = list(previews)
        self._radio_list = RadioList[str](
            values=self._build_values(),
            default=self._previews[0].id if self._previews else _EMPTY_SESSION_ID,
            show_numbers=False,
            select_on_focus=True,
            open_character="",
            select_character="›",
            close_character="",
            show_cursor=False,
            show_scrollbar=False,
            container_style="class:session-list",
            checked_style="class:session-list.checked",
        )
        self._app = self._build_app()

    def run(self) -> str | None:
        result = self._app.run()
        if result in {None, _EMPTY_SESSION_ID}:
            return None
        return result

    def _build_values(self) -> list[tuple[str, str]]:
        if not self._previews:
            return [(_EMPTY_SESSION_ID, "No sessions found.")]
        return [(preview.id, format_resume_session_label(preview)) for preview in self._previews]

    def _header_fragments(self) -> StyleAndTextTuples:
        total = len(self._previews)
        if total <= 0:
            selected = 0
        else:
            selected = min(self._radio_list._selected_index + 1, total)  # pyright: ignore[reportPrivateUsage]
        return [
            ("class:header.title", f" Resume a session ({total} total) "),
            ("class:header.meta", f" {selected}/{total} "),
        ]

    def _footer_fragments(self) -> StyleAndTextTuples:
        return [
            ("class:footer.text", " ↑/↓ navigate"),
            ("class:footer.text", " · "),
            ("class:footer.text", "PgUp/PgDn page"),
            ("class:footer.text", " · "),
            ("class:footer.text", "Enter select"),
            ("class:footer.text", " · "),
            ("class:footer.text", "Esc cancel "),
        ]

    def _build_app(self) -> Application[str | None]:
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
            FormattedTextControl(self._header_fragments),
            height=1,
            style="class:header",
        )
        body = Frame(
            Box(self._radio_list, padding=1),
            title=lambda: " Sessions ",
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
            style=_session_picker_style(),
        )


def _session_picker_style() -> Style:
    return Style.from_dict(
        {
            "header": "bg:#1f2333 #8be9fd",
            "header.title": "bold",
            "header.meta": "#8a90aa",
            "frame.border": "#5f6688",
            "frame.label": "#8be9fd bold",
            "session-list": "#c6d0f5",
            "session-list.checked": "#8be9fd bold",
            "radio-selected": "#8be9fd bold",
            "footer": "bg:#1f2333 #8a90aa",
            "footer.text": "#8a90aa",
        }
    )
