"""Full-screen picker for choosing the install scope of a skill."""

from __future__ import annotations

from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import Box, Frame, RadioList

from deepy.ui.classic.pickers.skill_picker_types import SkillInstallScope, _skill_picker_style


def pick_skill_install_scope(name: str, *, home: Path, project_root: Path) -> SkillInstallScope | None:
    return SkillInstallScopePicker(name, home=home, project_root=project_root).run()


class SkillInstallScopePicker:
    def __init__(self, name: str, *, home: Path, project_root: Path) -> None:
        self._name = name
        self._choices = [
            SkillInstallScope("user", home / ".agents" / "skills" / name),
            SkillInstallScope("project", project_root / ".agents" / "skills" / name),
        ]
        self._radio_list = RadioList[str](
            values=[
                ("user", f"User  {self._choices[0].path}"),
                ("project", f"Project  {self._choices[1].path}"),
            ],
            default="user",
            show_numbers=False,
            select_on_focus=True,
            open_character="",
            select_character="›",
            close_character="",
            show_cursor=False,
            show_scrollbar=False,
            container_style="class:skill-list",
            checked_style="class:skill-list.checked",
        )
        self._app = self._build_app()

    def run(self) -> SkillInstallScope | None:
        result = self._app.run()
        if result is None:
            return None
        return next((choice for choice in self._choices if choice.scope == result), None)

    def _header_fragments(self) -> StyleAndTextTuples:
        return [
            ("class:header.title", " Install skill "),
            ("class:header.meta", f" {self._name} "),
        ]

    def _footer_fragments(self) -> StyleAndTextTuples:
        return [
            ("class:footer.text", " ↑/↓ choose"),
            ("class:footer.text", " · "),
            ("class:footer.text", "Enter install"),
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
        body = Frame(Box(self._radio_list, padding=1), title=lambda: " Install Target ")
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
            style=_skill_picker_style(),
        )
