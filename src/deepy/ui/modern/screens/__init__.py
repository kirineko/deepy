"""Modern UI modal screens.

This package replaces the historical ``deepy.ui.modern.screens`` module; the public
screen classes and result types are re-exported here so existing imports keep
working.
"""

from __future__ import annotations

from deepy.ui.modern.screens.choice import (
    Choice as Choice,
    ChoiceScreen as ChoiceScreen,
    TextInputScreen as TextInputScreen,
)
from deepy.ui.modern.screens.config import ResetConfigResult as ResetConfigResult
from deepy.ui.modern.screens.info import InfoScreen as InfoScreen
from deepy.ui.modern.screens.skills import (
    SkillManagementScreen as SkillManagementScreen,
    SkillScreenAction as SkillScreenAction,
    SkillScreenEntry as SkillScreenEntry,
)

__all__ = [
    "Choice",
    "ChoiceScreen",
    "InfoScreen",
    "ResetConfigResult",
    "SkillManagementScreen",
    "SkillScreenAction",
    "SkillScreenEntry",
    "TextInputScreen",
]
