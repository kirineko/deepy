"""Modern UI widgets.

This package replaces the historical ``deepy.ui.modern.widgets`` module; the public
widget classes are re-exported here so existing imports keep working.
"""

from __future__ import annotations

from deepy.ui.modern.widgets.blocks import (
    AssistantBlock as AssistantBlock,
    ErrorBlock as ErrorBlock,
    InfoBlock as InfoBlock,
    StatusBar as StatusBar,
    ThinkingBlock as ThinkingBlock,
    TranscriptBlock as TranscriptBlock,
    UserBlock as UserBlock,
)
from deepy.ui.modern.widgets.decision import (
    AuditDecisionBlock as AuditDecisionBlock,
    InlineChoiceBlock as InlineChoiceBlock,
    InlineChoiceOption as InlineChoiceOption,
)
from deepy.ui.modern.widgets.diff import DiffBlock as DiffBlock
from deepy.ui.modern.widgets.prompt import (
    AttachmentRow as AttachmentRow,
    PromptPanel as PromptPanel,
    PromptTextArea as PromptTextArea,
)
from deepy.ui.modern.widgets.question import (
    QuestionBlock as QuestionBlock,
    QuestionOptionList as QuestionOptionList,
    QuestionTextArea as QuestionTextArea,
)
from deepy.ui.modern.widgets.tools import (
    LocalCommandBlock as LocalCommandBlock,
    ToolBlock as ToolBlock,
)

__all__ = [
    "AssistantBlock",
    "AttachmentRow",
    "AuditDecisionBlock",
    "DiffBlock",
    "ErrorBlock",
    "InfoBlock",
    "InlineChoiceBlock",
    "InlineChoiceOption",
    "LocalCommandBlock",
    "PromptPanel",
    "PromptTextArea",
    "QuestionBlock",
    "QuestionOptionList",
    "QuestionTextArea",
    "StatusBar",
    "ThinkingBlock",
    "ToolBlock",
    "TranscriptBlock",
    "UserBlock",
]
