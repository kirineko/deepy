from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepy.config import Settings
from deepy.mcp import mcp_policy_to_dict
from deepy.prompts.runtime_context import build_runtime_context
from deepy.sessions import list_session_entries
from deepy.skills import discover_skills


@dataclass(frozen=True)
class StatusReport:
    project_root: Path
    model: str
    reasoning_mode: str
    api_key_configured: bool
    context_window_tokens: int
    compact_threshold_tokens: int
    reserved_context_tokens: int
    session_count: int
    skill_count: int
    mcp: dict[str, Any]
    runtime_context: str


def build_status_report(project_root: Path, settings: Settings) -> StatusReport:
    root = project_root.resolve()
    return StatusReport(
        project_root=root,
        model=settings.model.name,
        reasoning_mode=settings.model.reasoning_mode,
        api_key_configured=bool(settings.model.api_key),
        context_window_tokens=settings.context.window_tokens,
        compact_threshold_tokens=settings.context.resolved_compact_threshold,
        reserved_context_tokens=settings.context.reserved_context_tokens,
        session_count=len(list_session_entries(root)),
        skill_count=len(discover_skills(root)),
        mcp=mcp_policy_to_dict(settings),
        runtime_context=build_runtime_context(root),
    )


def format_status_report(report: StatusReport) -> str:
    return "\n".join(
        [
            f"Project: {report.project_root}",
            f"Model: {report.model}",
            f"Reasoning: {report.reasoning_mode}",
            f"API key: {'configured' if report.api_key_configured else 'missing'}",
            f"Context: {report.context_window_tokens} tokens",
            f"Compact threshold: {report.compact_threshold_tokens} tokens",
            f"Reserved context: {report.reserved_context_tokens} tokens",
            f"Sessions: {report.session_count}",
            f"Skills: {report.skill_count}",
            (
                "MCP: "
                f"{'enabled' if report.mcp.get('enabled') else 'disabled'} "
                f"config={report.mcp.get('config_path')}"
            ),
            "",
            report.runtime_context,
        ]
    )


def status_report_to_dict(report: StatusReport) -> dict[str, Any]:
    return {
        "project_root": str(report.project_root),
        "model": report.model,
        "reasoning_mode": report.reasoning_mode,
        "api_key_configured": report.api_key_configured,
        "context_window_tokens": report.context_window_tokens,
        "compact_threshold_tokens": report.compact_threshold_tokens,
        "reserved_context_tokens": report.reserved_context_tokens,
        "session_count": report.session_count,
        "skill_count": report.skill_count,
        "mcp": report.mcp,
        "runtime_context": report.runtime_context,
    }
