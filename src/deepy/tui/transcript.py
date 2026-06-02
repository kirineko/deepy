from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TranscriptKind = Literal[
    "assistant",
    "decision",
    "diff",
    "error",
    "info",
    "reasoning",
    "tool",
    "usage",
    "user",
]


@dataclass(frozen=True)
class TranscriptDisplay:
    kind: TranscriptKind
    label: str
    css_class: str
    priority: int
    folded_by_default: bool = False


TRANSCRIPT_DISPLAYS: dict[TranscriptKind, TranscriptDisplay] = {
    "user": TranscriptDisplay("user", "›", "user-block", 10),
    "assistant": TranscriptDisplay("assistant", "•", "assistant-block", 20),
    "reasoning": TranscriptDisplay("reasoning", "·", "thinking-block", 30, folded_by_default=True),
    "tool": TranscriptDisplay("tool", "·", "tool-block", 40, folded_by_default=True),
    "diff": TranscriptDisplay("diff", "Diff", "diff-block", 45, folded_by_default=True),
    "decision": TranscriptDisplay("decision", "Decision", "question-block", 50),
    "error": TranscriptDisplay("error", "Error", "error-block", 60),
    "usage": TranscriptDisplay("usage", "Usage", "usage-line", 70, folded_by_default=True),
    "info": TranscriptDisplay("info", "Info", "info-block", 80, folded_by_default=True),
}


def transcript_display(kind: TranscriptKind) -> TranscriptDisplay:
    return TRANSCRIPT_DISPLAYS[kind]
