"""Full-screen skill market / installed-skill menu picker."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import Box, Frame, RadioList

from deepy.skill_market import MarketSkill
from deepy.ui.classic.pickers.skill_picker_types import (
    InstalledSkillView,
    SkillMenuAction,
    _skill_picker_style,
    format_installed_skill_label,
    format_market_skill_label,
)

_EMPTY_VALUE = "__empty__"
SkillMenuView = str


def pick_skill_menu_action(
    market_skills: Sequence[MarketSkill] | None,
    installed_skills: Sequence[InstalledSkillView],
    *,
    market_loader: Callable[[], Sequence[MarketSkill]] | None = None,
    initial_view: SkillMenuView = "market",
) -> SkillMenuAction | None:
    return SkillMenuPicker(
        market_skills,
        installed_skills,
        market_loader=market_loader,
        initial_view=initial_view,
    ).run()


class SkillMenuPicker:
    def __init__(
        self,
        market_skills: Sequence[MarketSkill] | None,
        installed_skills: Sequence[InstalledSkillView],
        *,
        market_loader: Callable[[], Sequence[MarketSkill]] | None = None,
        initial_view: SkillMenuView = "market",
    ) -> None:
        self._market_skills = list(market_skills or [])
        self._installed_skills = list(installed_skills)
        self._installed_names = {skill.name for skill in self._installed_skills}
        self._installed_by_name = {skill.name: skill for skill in self._installed_skills}
        self._market_by_name = {skill.name: skill for skill in self._market_skills}
        self._market_loader = market_loader
        self._market_loading = market_loader is not None and market_skills is None
        self._market_error = ""
        self._view: SkillMenuView = initial_view if initial_view in {"market", "installed"} else "market"
        self._radio_list = RadioList[str](
            values=[(_EMPTY_VALUE, "")],
            default=_EMPTY_VALUE,
            show_numbers=False,
            select_on_focus=True,
            open_character="",
            select_character="›",
            close_character="",
            show_cursor=False,
            show_scrollbar=True,
            container_style="class:skill-list",
            checked_style="class:skill-list.checked",
        )
        self._set_view(self._view)
        self._app = self._build_app()

    def run(self) -> SkillMenuAction | None:
        if self._market_loading and self._market_loader is not None:
            thread = threading.Thread(target=self._load_market_skills, daemon=True)
            thread.start()
        return self._app.run()

    def _load_market_skills(self) -> None:
        try:
            loaded = list(self._market_loader() if self._market_loader is not None else [])
        except Exception as exc:
            self._market_error = str(exc)
            loaded = []
        self._market_skills = loaded
        self._market_by_name = {skill.name: skill for skill in self._market_skills}
        self._market_loading = False
        if self._view == "market":
            self._set_view("market")
        else:
            self._app.invalidate()

    def _current_name(self) -> str:
        value = self._radio_list.current_value
        return "" if value == _EMPTY_VALUE else value

    def _primary_action(self) -> SkillMenuAction | None:
        name = self._current_name()
        if not name:
            return None
        if self._view == "market":
            return SkillMenuAction(
                "update" if name in self._installed_names else "choose-install-scope",
                name,
            )
        installed = self._installed_by_name.get(name)
        return SkillMenuAction(
            "show",
            name,
            scope=installed.scope if installed is not None else "",
            path=installed.path if installed is not None else None,
            version=installed.version if installed is not None else "",
            installed_at=installed.installed_at if installed is not None else "",
            managed_by_market=bool(installed and installed.managed_by_market),
        )

    def _toggle_action(self) -> SkillMenuAction | None:
        name = self._current_name()
        if not name:
            return None
        if self._view == "market":
            return SkillMenuAction(
                "update" if name in self._installed_names else "choose-install-scope",
                name,
            )
        installed = self._installed_by_name.get(name)
        return SkillMenuAction(
            "uninstall" if installed and installed.managed_by_market else "remove-local",
            name,
            scope=installed.scope if installed is not None else "",
            path=installed.path if installed is not None else None,
            managed_by_market=bool(installed and installed.managed_by_market),
        )

    def _view_action(self) -> SkillMenuAction | None:
        name = self._current_name()
        if not name:
            return None
        installed = self._installed_by_name.get(name)
        if self._view == "market":
            if installed is not None:
                return SkillMenuAction(
                    "show",
                    name,
                    scope=installed.scope,
                    path=installed.path,
                    version=installed.version,
                    installed_at=installed.installed_at,
                    managed_by_market=installed.managed_by_market,
                )
            market_skill = self._market_by_name.get(name)
            return SkillMenuAction(
                "show",
                name,
                scope="market",
                market_skill=market_skill,
            )
        return SkillMenuAction(
            "show",
            name,
            scope=installed.scope if installed is not None else "",
            path=installed.path if installed is not None else None,
            version=installed.version if installed is not None else "",
            installed_at=installed.installed_at if installed is not None else "",
            managed_by_market=bool(installed and installed.managed_by_market),
        )

    def _update_action(self) -> SkillMenuAction | None:
        name = self._current_name()
        if not name:
            return None
        if self._view == "market" and name not in self._installed_names:
            return None
        installed = self._installed_by_name.get(name)
        if self._view == "installed" and not (installed and installed.managed_by_market):
            return None
        return SkillMenuAction("update", name)

    def _set_view(self, view: SkillMenuView) -> None:
        self._view = view
        values = self._values_for_view(view)
        if not values:
            values = [(_EMPTY_VALUE, self._empty_label_for_view(view))]
        self._radio_list.values = values
        self._radio_list.current_value = values[0][0]
        self._radio_list.current_values = [values[0][0]]
        self._radio_list._selected_index = 0  # pyright: ignore[reportPrivateUsage]
        if hasattr(self, "_app"):
            self._app.invalidate()

    def _values_for_view(self, view: SkillMenuView) -> list[tuple[str, str]]:
        if view == "market":
            return [(skill.name, format_market_skill_label(skill)) for skill in self._market_skills]
        return [(skill.name, format_installed_skill_label(skill)) for skill in self._installed_skills]

    def _empty_label_for_view(self, view: SkillMenuView) -> str:
        if view != "market":
            return "No installed skills."
        if self._market_loading:
            return "Loading market skills..."
        if self._market_error:
            return f"Failed to load market skills: {self._market_error}\n  Press r to retry."
        return "No market skills found."

    def _header_fragments(self) -> StyleAndTextTuples:
        market_style = "class:tab.active" if self._view == "market" else "class:tab"
        installed_style = "class:tab.active" if self._view == "installed" else "class:tab"
        return [
            ("class:header.title", " Skills "),
            (market_style, f" Market {len(self._market_skills)} "),
            ("class:header.sep", " "),
            (installed_style, f" Installed {len(self._installed_skills)} "),
            ("class:header.meta", " loading " if self._market_loading else ""),
        ]

    def _footer_fragments(self) -> StyleAndTextTuples:
        if self._view == "market":
            action_hint = "Enter/Space install or update"
        else:
            action_hint = "Enter view · Space uninstall"
        return [
            ("class:footer.text", " ↑/↓ navigate"),
            ("class:footer.text", " · "),
            ("class:footer.text", "Tab switch"),
            ("class:footer.text", " · "),
            ("class:footer.text", action_hint),
            ("class:footer.text", " · "),
            ("class:footer.text", "v view"),
            ("class:footer.text", " · "),
            ("class:footer.text", "u update"),
            ("class:footer.text", " · "),
            ("class:footer.text", "r refresh"),
            ("class:footer.text", " · "),
            ("class:footer.text", "Esc close "),
        ]

    def _build_app(self) -> Application[SkillMenuAction | None]:
        kb = KeyBindings()

        @kb.add("escape")
        @kb.add("c-c")
        def _cancel(event: KeyPressEvent) -> None:
            event.app.exit(result=None)

        @kb.add("tab", eager=True)
        def _switch(event: KeyPressEvent) -> None:
            self._set_view("installed" if self._view == "market" else "market")

        @kb.add("r", eager=True)
        def _refresh(event: KeyPressEvent) -> None:
            if self._market_loader is None:
                event.app.exit(result=SkillMenuAction("refresh"))
                return
            self._market_loading = True
            self._market_error = ""
            self._set_view("market")
            thread = threading.Thread(target=self._load_market_skills, daemon=True)
            thread.start()

        @kb.add("enter", eager=True)
        def _select(event: KeyPressEvent) -> None:
            event.app.exit(result=self._primary_action())

        @kb.add(" ", eager=True)
        def _toggle(event: KeyPressEvent) -> None:
            event.app.exit(result=self._toggle_action())

        @kb.add("v", eager=True)
        def _view(event: KeyPressEvent) -> None:
            event.app.exit(result=self._view_action())

        @kb.add("u", eager=True)
        def _update(event: KeyPressEvent) -> None:
            event.app.exit(result=self._update_action())

        _ = (_cancel, _switch, _refresh, _select, _toggle, _view, _update)

        header = Window(
            FormattedTextControl(self._header_fragments),
            height=1,
            style="class:header",
        )
        body = Frame(
            Box(self._radio_list, padding=1),
            title=lambda: " Skill Market " if self._view == "market" else " Installed Skills ",
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
            style=_skill_picker_style(),
        )
