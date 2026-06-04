from __future__ import annotations

import os

from prompt_toolkit.keys import Keys
from prompt_toolkit.renderer import CPR_Support

from deepy.ui.classic.pickers.audit_approval_picker import AUDIT_APPROVAL_APPROVE
from deepy.ui.classic.pickers.audit_approval_picker import AUDIT_APPROVAL_REJECT
from deepy.ui.classic.pickers.audit_approval_picker import AUDIT_APPROVAL_TOGGLE_PREVIEW
from deepy.ui.classic.pickers.audit_approval_picker import AuditApprovalPicker


def test_audit_approval_picker_renders_inline_in_conversation_flow():
    app = AuditApprovalPicker()._app

    assert app.full_screen is False
    assert app.erase_when_done is False
    assert AuditApprovalPicker()._control.show_cursor is False


def test_audit_approval_picker_disables_cpr_probe(monkeypatch):
    monkeypatch.delenv("PROMPT_TOOLKIT_NO_CPR", raising=False)

    app = AuditApprovalPicker()._app

    assert app.renderer.cpr_support == CPR_Support.NOT_SUPPORTED
    assert "PROMPT_TOOLKIT_NO_CPR" not in os.environ


def test_audit_approval_picker_has_separate_review_option_above_decisions():
    picker = AuditApprovalPicker(can_toggle_preview=True)

    assert [option.value for option in picker._options] == [
        AUDIT_APPROVAL_TOGGLE_PREVIEW,
        AUDIT_APPROVAL_APPROVE,
        AUDIT_APPROVAL_REJECT,
    ]
    fragments = "".join(text for _style, text in picker._option_fragments())

    assert fragments.index("Diff full") < fragments.index("Approve")
    assert "Diff full" in fragments
    assert "Show full diff" not in fragments
    assert "Approve / Reject" not in fragments
    assert "Approve" in fragments
    assert "Reject" in fragments


def test_audit_approval_picker_marks_collapse_when_expanded():
    picker = AuditApprovalPicker(can_toggle_preview=True, expanded=True)
    fragments = "".join(text for _style, text in picker._option_fragments())

    assert "Diff compact" in fragments
    assert "Diff full" not in fragments


def test_audit_approval_picker_compact_mode_does_not_show_scroll_controls():
    picker = AuditApprovalPicker(
        can_toggle_preview=True,
        expanded=False,
        panel_text_factory=lambda _expanded: "\n".join(f"line {index}" for index in range(20)),
    )
    fragments = "".join(text for _style, text in picker._option_fragments())
    footer = "".join(text for _style, text in picker._footer_fragments())

    assert "Diff compact" not in fragments
    assert "scroll" not in footer.lower()


def test_audit_approval_picker_toggles_diff_label_without_exiting_decision():
    picker = AuditApprovalPicker(can_toggle_preview=True)

    picker._move_selection(-1)
    assert picker._options[picker._selected_index].value == AUDIT_APPROVAL_TOGGLE_PREVIEW
    picker._toggle_preview()
    fragments = "".join(text for _style, text in picker._option_fragments())

    assert picker._options[picker._selected_index].value == AUDIT_APPROVAL_TOGGLE_PREVIEW
    assert "Diff compact" in fragments


def test_audit_approval_picker_moves_selection_with_up_and_down_only():
    picker = AuditApprovalPicker(can_toggle_preview=True)

    assert picker._options[picker._selected_index].value == AUDIT_APPROVAL_APPROVE
    picker._move_selection(-1)
    assert picker._options[picker._selected_index].value == AUDIT_APPROVAL_TOGGLE_PREVIEW
    picker._move_selection(1)
    assert picker._options[picker._selected_index].value == AUDIT_APPROVAL_APPROVE
    picker._move_selection(1)
    assert picker._options[picker._selected_index].value == AUDIT_APPROVAL_REJECT


def test_audit_approval_picker_scrolls_expanded_panel_with_vim_keys(monkeypatch):
    monkeypatch.setattr("deepy.ui.classic.pickers.audit_approval_picker.shutil.get_terminal_size", lambda fallback: os.terminal_size((80, 12)))
    picker = AuditApprovalPicker(
        can_toggle_preview=True,
        expanded=True,
        panel_text_factory=lambda _expanded: "\n".join(f"line {index}" for index in range(20)),
    )

    assert [option.value for option in picker._options] == [
        AUDIT_APPROVAL_TOGGLE_PREVIEW,
        AUDIT_APPROVAL_APPROVE,
        AUDIT_APPROVAL_REJECT,
    ]
    footer = "".join(text for _style, text in picker._footer_fragments())
    assert "J/K scroll" in footer
    assert "line 0" in picker._visible_panel_text()
    assert "line 7" not in picker._visible_panel_text()

    picker._scroll_panel(1)

    assert [option.value for option in picker._options] == [
        AUDIT_APPROVAL_TOGGLE_PREVIEW,
        AUDIT_APPROVAL_APPROVE,
        AUDIT_APPROVAL_REJECT,
    ]
    assert "line 0" not in picker._visible_panel_text()
    assert "line 5" in picker._visible_panel_text()


def test_audit_approval_picker_binds_only_navigation_enter_and_escape():
    picker = AuditApprovalPicker(can_toggle_preview=True)
    bound_keys = {binding.keys[0] for binding in picker._app.key_bindings.bindings}

    assert bound_keys == {Keys.Escape, Keys.Up, Keys.Down, Keys.ControlM, "j", "k"}
    assert "h" not in bound_keys
    assert "l" not in bound_keys
    assert "y" not in bound_keys
    assert "a" not in bound_keys
    assert "n" not in bound_keys
    assert "r" not in bound_keys
