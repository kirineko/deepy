"""Public facade for the prompt_toolkit skill pickers.

The concrete implementations live in focused sibling modules; this module keeps
the historical ``deepy.ui.classic.pickers.skill_picker`` import surface stable for callers and
tests.
"""

from __future__ import annotations

from deepy.ui.classic.pickers.skill_detail_viewer import SkillDetailViewer as SkillDetailViewer
from deepy.ui.classic.pickers.skill_detail_viewer import show_skill_detail_view as show_skill_detail_view
from deepy.ui.classic.pickers.skill_install_scope_picker import SkillInstallScopePicker as SkillInstallScopePicker
from deepy.ui.classic.pickers.skill_install_scope_picker import pick_skill_install_scope as pick_skill_install_scope
from deepy.ui.classic.pickers.skill_menu_picker import SkillMenuPicker as SkillMenuPicker
from deepy.ui.classic.pickers.skill_menu_picker import pick_skill_menu_action as pick_skill_menu_action
from deepy.ui.classic.pickers.skill_picker_types import InstalledSkillView as InstalledSkillView
from deepy.ui.classic.pickers.skill_picker_types import SkillDetailView as SkillDetailView
from deepy.ui.classic.pickers.skill_picker_types import SkillInstallScope as SkillInstallScope
from deepy.ui.classic.pickers.skill_picker_types import SkillMenuAction as SkillMenuAction
from deepy.ui.classic.pickers.skill_picker_types import format_installed_skill_label as format_installed_skill_label
from deepy.ui.classic.pickers.skill_picker_types import format_market_skill_label as format_market_skill_label
from deepy.ui.classic.pickers.skill_picker_types import format_skill_detail_text as format_skill_detail_text

__all__ = [
    "InstalledSkillView",
    "SkillDetailView",
    "SkillDetailViewer",
    "SkillInstallScope",
    "SkillInstallScopePicker",
    "SkillMenuAction",
    "SkillMenuPicker",
    "format_installed_skill_label",
    "format_market_skill_label",
    "format_skill_detail_text",
    "pick_skill_install_scope",
    "pick_skill_menu_action",
    "show_skill_detail_view",
]
