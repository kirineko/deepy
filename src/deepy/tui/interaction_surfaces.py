from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SurfaceKind = Literal[
    "inline-transcript",
    "composer-adjacent",
    "side-detail",
    "management-screen",
]


@dataclass(frozen=True)
class TuiInteractionSurface:
    name: str
    kind: SurfaceKind
    current_widget: str
    target: str
    management_reason: str = ""

    @property
    def interrupts_transcript(self) -> bool:
        return self.kind == "management-screen"


TUI_INTERACTION_SURFACES: tuple[TuiInteractionSurface, ...] = (
    TuiInteractionSurface(
        "help",
        "side-detail",
        "InfoScreen",
        "compact help/detail surface that preserves conversation context",
    ),
    TuiInteractionSurface(
        "status",
        "side-detail",
        "InfoScreen",
        "compact grouped status/detail surface",
    ),
    TuiInteractionSurface(
        "mcp",
        "side-detail",
        "InfoScreen",
        "compact grouped MCP detail surface",
    ),
    TuiInteractionSurface(
        "background-tasks",
        "side-detail",
        "InfoScreen",
        "compact background task detail surface",
    ),
    TuiInteractionSurface(
        "stop-background-task",
        "composer-adjacent",
        "ChoiceScreen",
        "short-choice surface near the main flow",
    ),
    TuiInteractionSurface(
        "theme-picker",
        "composer-adjacent",
        "ChoiceScreen",
        "short-choice surface near the main flow",
    ),
    TuiInteractionSurface(
        "model-picker",
        "composer-adjacent",
        "ChoiceScreen",
        "staged short-choice provider/model/thinking surface",
    ),
    TuiInteractionSurface(
        "session-resume",
        "side-detail",
        "ChoiceScreen",
        "embedded or side session list with preview",
    ),
    TuiInteractionSurface(
        "audit-approval",
        "inline-transcript",
        "AuditApprovalScreen",
        "inline audit decision block",
    ),
    TuiInteractionSurface(
        "ask-user-question",
        "inline-transcript",
        "QuestionBlock",
        "inline question decision block",
    ),
    TuiInteractionSurface(
        "reset-config",
        "composer-adjacent",
        "InlineChoiceBlock/TextInputScreen",
        "provider-aware staged reset flow aligned with Classic UI setup",
    ),
    TuiInteractionSurface(
        "skills-management",
        "management-screen",
        "SkillManagementScreen",
        "skill market and installed-skill management need list/detail/actions space",
        management_reason="skill market and installed skill workflow",
    ),
    TuiInteractionSurface(
        "skill-detail",
        "management-screen",
        "InfoScreen",
        "long skill details need readable dedicated space",
        management_reason="long skill detail reading",
    ),
)


def tui_interaction_surface(name: str) -> TuiInteractionSurface | None:
    normalized = name.lower()
    return next(
        (surface for surface in TUI_INTERACTION_SURFACES if surface.name == normalized),
        None,
    )


def transcript_interrupting_surfaces() -> list[TuiInteractionSurface]:
    return [surface for surface in TUI_INTERACTION_SURFACES if surface.interrupts_transcript]
