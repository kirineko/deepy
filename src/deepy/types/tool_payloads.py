from __future__ import annotations

from typing import NotRequired, TypedDict


class AskUserOption(TypedDict):
    label: str
    description: NotRequired[str]


class AskUserQuestion(TypedDict):
    question: str
    options: list[AskUserOption]
    multiSelect: NotRequired[bool]

