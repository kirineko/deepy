from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding import KeyPressEvent
from prompt_toolkit.layout import HSplit
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style


AuditApprovalChoice = str
AUDIT_APPROVAL_APPROVE = "approve"
AUDIT_APPROVAL_REJECT = "reject"
AUDIT_APPROVAL_TOGGLE_PREVIEW = "toggle_preview"
ApprovalPanelTextFactory = Callable[[bool], str]


def pick_audit_approval(
    *,
    can_toggle_preview: bool = False,
    expanded: bool = False,
    panel_text_factory: ApprovalPanelTextFactory | None = None,
) -> AuditApprovalChoice:
    return AuditApprovalPicker(
        can_toggle_preview=can_toggle_preview,
        expanded=expanded,
        panel_text_factory=panel_text_factory,
    ).run()


@dataclass(frozen=True)
class AuditApprovalOption:
    value: AuditApprovalChoice
    label: str


class AuditApprovalPicker:
    def __init__(
        self,
        *,
        can_toggle_preview: bool = False,
        expanded: bool = False,
        panel_text_factory: ApprovalPanelTextFactory | None = None,
    ) -> None:
        self._can_toggle_preview = can_toggle_preview
        self._expanded = expanded
        self._panel_text_factory = panel_text_factory
        self._panel_text = ""
        self._panel_line_count = 0
        self._panel_scroll = 0
        self._refresh_panel_text()
        self._options = _approval_options(
            can_toggle_preview=can_toggle_preview,
            expanded=expanded,
        )
        self._selected_index = _default_option_index(self._options, AUDIT_APPROVAL_APPROVE)
        self._control = FormattedTextControl(
            self._option_fragments,
            focusable=True,
            show_cursor=False,
        )
        self._app = self._build_app()

    def run(self) -> AuditApprovalChoice:
        result = self._app.run()
        return result if result in {option.value for option in self._options} else AUDIT_APPROVAL_REJECT

    def _build_app(self) -> Application[str | None]:
        kb = KeyBindings()

        @kb.add("escape")
        def _reject(event: KeyPressEvent) -> None:
            event.app.exit(result=AUDIT_APPROVAL_REJECT)

        @kb.add("up")
        def _up(event: KeyPressEvent) -> None:
            self._move_selection(-1)
            event.app.invalidate()

        @kb.add("k")
        def _scroll_up(event: KeyPressEvent) -> None:
            self._scroll_panel(-1)
            event.app.invalidate()

        @kb.add("down")
        def _down(event: KeyPressEvent) -> None:
            self._move_selection(1)
            event.app.invalidate()

        @kb.add("j")
        def _scroll_down(event: KeyPressEvent) -> None:
            self._scroll_panel(1)
            event.app.invalidate()

        @kb.add("enter", eager=True)
        def _select(event: KeyPressEvent) -> None:
            value = self._options[self._selected_index].value
            if value == AUDIT_APPROVAL_TOGGLE_PREVIEW:
                self._toggle_preview()
                event.app.invalidate()
                return
            event.app.exit(result=value)

        _ = (_reject, _up, _scroll_up, _down, _scroll_down, _select)

        title = Window(FormattedTextControl(_title_fragments), height=1, style="class:title")
        footer = Window(
            FormattedTextControl(self._footer_fragments),
            height=1,
            style="class:footer",
        )
        children = []
        if self._panel_text_factory is not None:
            children.append(Window(FormattedTextControl(self._panel_fragments), dont_extend_height=True))
        children.extend(
            [
                title,
                Window(self._control, dont_extend_height=True),
                footer,
            ]
        )
        with _prompt_toolkit_cpr_disabled():
            return Application(
                layout=Layout(
                    HSplit(children),
                    focused_element=self._control,
                ),
                key_bindings=kb,
                full_screen=False,
                erase_when_done=False,
                mouse_support=False,
                style=_audit_picker_style(),
            )

    def _move_selection(self, delta: int) -> None:
        if not self._options:
            return
        self._selected_index = (self._selected_index + delta) % len(self._options)

    def _toggle_preview(self) -> None:
        if not self._can_toggle_preview:
            return
        current_value = self._options[self._selected_index].value
        self._expanded = not self._expanded
        self._panel_scroll = 0
        self._refresh_panel_text()
        self._options = _approval_options(
            can_toggle_preview=self._can_toggle_preview,
            expanded=self._expanded,
        )
        self._selected_index = _default_option_index(self._options, current_value)

    def _panel_fragments(self) -> ANSI:
        return ANSI(self._visible_panel_text())

    def _visible_panel_text(self) -> str:
        text = self._refresh_panel_text()
        lines = text.splitlines()
        if not lines:
            return ""
        visible_height = self._panel_visible_height()
        if len(lines) <= visible_height:
            return text
        self._panel_scroll = min(self._panel_scroll, self._panel_max_scroll())
        return "\n".join(lines[self._panel_scroll : self._panel_scroll + visible_height])

    def _panel_visible_height(self) -> int:
        terminal_height = shutil.get_terminal_size(fallback=(80, 24)).lines
        reserved_rows = 6
        return max(6, terminal_height - reserved_rows)

    def _panel_max_scroll(self) -> int:
        return max(0, self._panel_line_count - self._panel_visible_height())

    def _scroll_panel(self, pages: int) -> None:
        if not self._expanded or self._panel_text_factory is None:
            return
        self._refresh_panel_text()
        page_size = max(1, self._panel_visible_height() - 1)
        next_scroll = max(0, min(self._panel_max_scroll(), self._panel_scroll + (pages * page_size)))
        self._panel_scroll = next_scroll

    def _can_scroll_down(self) -> bool:
        return self._expanded and self._panel_scroll < self._panel_max_scroll()

    def _refresh_panel_text(self) -> str:
        if self._panel_text_factory is None:
            self._panel_text = ""
            self._panel_line_count = 0
            self._panel_scroll = 0
            return self._panel_text
        self._panel_text = self._panel_text_factory(self._expanded)
        self._panel_line_count = max(1, len(self._panel_text.splitlines()))
        self._panel_scroll = min(self._panel_scroll, self._panel_max_scroll())
        return self._panel_text

    def _option_fragments(self) -> StyleAndTextTuples:
        fragments: StyleAndTextTuples = []
        for index, option in enumerate(self._options):
            selected = index == self._selected_index
            marker = "›" if selected else " "
            marker_style = "class:option.selected" if selected else "class:option"
            label_style = "class:option.selected" if selected else "class:option.label"
            fragments.extend(
                [
                    (marker_style, f" {marker} "),
                    (label_style, option.label),
                    ("", "\n"),
                ]
            )
        return fragments

    def _footer_fragments(self) -> StyleAndTextTuples:
        text = "↑/↓ navigate · Enter select · Esc reject"
        if self._expanded and self._panel_max_scroll() > 0:
            text += " · J/K scroll"
        return [("class:footer.text", text)]


def _title_fragments() -> StyleAndTextTuples:
    return [
        ("class:title.text", "Decision "),
        ("class:title.hint", "(Enter select, Esc reject)"),
    ]


def _approval_options(
    *,
    can_toggle_preview: bool,
    expanded: bool,
) -> list[AuditApprovalOption]:
    options: list[AuditApprovalOption] = []
    if can_toggle_preview:
        options.append(
            AuditApprovalOption(
                value=AUDIT_APPROVAL_TOGGLE_PREVIEW,
                label="Diff compact" if expanded else "Diff full",
            )
        )
    options.extend(
        [
            AuditApprovalOption(
                value=AUDIT_APPROVAL_APPROVE,
                label="Approve",
            ),
            AuditApprovalOption(
                value=AUDIT_APPROVAL_REJECT,
                label="Reject",
            ),
        ]
    )
    return options


def _default_option_index(options: list[AuditApprovalOption], value: AuditApprovalChoice) -> int:
    for index, option in enumerate(options):
        if option.value == value:
            return index
    return 0


@contextmanager
def _prompt_toolkit_cpr_disabled() -> Iterator[None]:
    previous = os.environ.get("PROMPT_TOOLKIT_NO_CPR")
    os.environ["PROMPT_TOOLKIT_NO_CPR"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PROMPT_TOOLKIT_NO_CPR", None)
        else:
            os.environ["PROMPT_TOOLKIT_NO_CPR"] = previous


def _audit_picker_style() -> Style:
    return Style.from_dict(
        {
            "title.text": "#f9e2af bold",
            "title.hint": "#8a90aa",
            "option": "#c6d0f5",
            "option.label": "#c6d0f5",
            "option.selected": "#8be9fd bold",
            "footer.text": "#8a90aa",
        }
    )
