from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
from prompt_toolkit.widgets import TextArea

from deepy.skill_market import MarketSkill
from deepy.ui.markdown import render_markdown


_EMPTY_VALUE = "__empty__"
SkillMenuView = str


@dataclass(frozen=True)
class SkillMenuAction:
    action: str
    name: str = ""
    scope: str = ""
    path: Path | None = None
    version: str = ""
    installed_at: str = ""
    managed_by_market: bool = False
    market_skill: MarketSkill | None = None


@dataclass(frozen=True)
class SkillInstallScope:
    scope: Literal["user", "project"]
    path: Path


@dataclass(frozen=True)
class InstalledSkillView:
    name: str
    scope: str
    path: Path
    version: str = ""
    installed_at: str = ""
    managed_by_market: bool = False


@dataclass(frozen=True)
class SkillDetailView:
    name: str
    body: str = ""
    scope: str = ""
    path: Path | None = None
    version: str = ""
    installed_at: str = ""
    managed_by_market: bool = False
    description: str = ""
    uploaded_at: str = ""
    sha256: str = ""
    installed: bool | None = None
    markdown: bool = False


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


def pick_skill_install_scope(name: str, *, home: Path, project_root: Path) -> SkillInstallScope | None:
    return SkillInstallScopePicker(name, home=home, project_root=project_root).run()


def show_skill_detail_view(detail: SkillDetailView) -> None:
    SkillDetailViewer(detail).run()


def format_market_skill_label(skill: MarketSkill) -> str:
    marker = "[x]" if skill.installed else "[ ]"
    version = f"  {skill.version}" if skill.version else ""
    uploaded = f"  uploaded {skill.uploaded_at[:10]}" if skill.uploaded_at else ""
    description = _shorten(skill.description, 150)
    second_line = f"\n  {description}" if description else ""
    return f"{marker} {skill.name}{version}{uploaded}{second_line}"


def format_installed_skill_label(skill: InstalledSkillView) -> str:
    version = f"  {skill.version}" if skill.version else ""
    installed = f"  installed {skill.installed_at[:10]}" if skill.installed_at else ""
    marker = "[market]" if skill.managed_by_market else f"[{skill.scope}]"
    path = _shorten(str(skill.path), 120)
    return f"{marker} {skill.name}{version}{installed}\n  {path}"


def format_skill_detail_text(detail: SkillDetailView) -> str:
    metadata = [f"Name: {detail.name}"]
    if detail.scope:
        metadata.append(f"Scope: {detail.scope}")
    if detail.path is not None:
        metadata.append(f"Path: {detail.path}")
    if detail.version:
        metadata.append(f"Version: {detail.version}")
    if detail.installed_at:
        metadata.append(f"Installed: {detail.installed_at}")
    if detail.uploaded_at:
        metadata.append(f"Uploaded: {detail.uploaded_at}")
    if detail.managed_by_market:
        metadata.append("Managed by market: yes")
    if detail.installed is not None:
        metadata.append(f"Installed locally: {'yes' if detail.installed else 'no'}")
    if detail.sha256:
        metadata.append(f"SHA256: {detail.sha256}")
    if detail.description:
        metadata.append(f"Description: {detail.description}")
    body = _render_detail_body(detail)
    return "\n".join(metadata) + "\n\n" + body


def _render_detail_body(detail: SkillDetailView) -> str:
    source = detail.body.strip() or detail.description.strip()
    if not source:
        return "(no details available)"
    if not detail.markdown:
        return source
    return render_markdown(source, width=100).plain


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


def _shorten(value: str, max_chars: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _skill_picker_style() -> Style:
    return Style.from_dict(
        {
            "header": "bg:#1f2333 #8be9fd",
            "header.title": "bold",
            "header.meta": "#8a90aa",
            "header.sep": "#5f6688",
            "tab": "#8a90aa",
            "tab.active": "#1f2333 bg:#8be9fd bold",
            "frame.border": "#5f6688",
            "frame.label": "#8be9fd bold",
            "skill-list": "#c6d0f5",
            "skill-list.checked": "#8be9fd bold",
            "radio-selected": "#8be9fd bold",
            "footer": "bg:#1f2333 #8a90aa",
            "footer.text": "#8a90aa",
        }
    )


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
