from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from deepy.config import Settings
from deepy.prompts.runtime_context import build_runtime_context
from deepy.sessions import list_session_entries
from deepy.skills import discover_skills


@dataclass(frozen=True)
class StatusReport:
    project_root: Path
    model: str
    api_key_configured: bool
    context_window_tokens: int
    compact_threshold_tokens: int
    session_count: int
    skill_count: int
    runtime_context: str


def build_status_report(project_root: Path, settings: Settings) -> StatusReport:
    root = project_root.resolve()
    return StatusReport(
        project_root=root,
        model=settings.model.name,
        api_key_configured=bool(settings.model.api_key),
        context_window_tokens=settings.context.window_tokens,
        compact_threshold_tokens=settings.context.resolved_compact_threshold,
        session_count=len(list_session_entries(root)),
        skill_count=len(discover_skills(root)),
        runtime_context=build_runtime_context(root),
    )


def format_status_report(report: StatusReport) -> str:
    return "\n".join(
        [
            f"Project: {report.project_root}",
            f"Model: {report.model}",
            f"API key: {'configured' if report.api_key_configured else 'missing'}",
            f"Context: {report.context_window_tokens} tokens",
            f"Compact threshold: {report.compact_threshold_tokens} tokens",
            f"Sessions: {report.session_count}",
            f"Skills: {report.skill_count}",
            "",
            report.runtime_context,
        ]
    )
