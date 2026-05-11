from __future__ import annotations

from pathlib import Path

from deepy.config import Settings
from deepy.skills import (
    SkillInfo,
    discover_skills,
    format_loaded_skills_for_prompt,
    format_skills_for_prompt,
)

from .rules import AGENT_DRIFT_GUARD, load_project_rules


def build_system_prompt(
    project_root: Path,
    settings: Settings,
    *,
    project_rules: str | None = None,
    skills: list[SkillInfo] | None = None,
    loaded_skills: list[SkillInfo] | None = None,
) -> str:
    resolved_project_rules = (
        load_project_rules(project_root) if project_rules is None else project_rules.strip()
    )
    resolved_skills = discover_skills(project_root) if skills is None else skills
    project_rules_block = resolved_project_rules or "No project rules found."
    skills_block = format_skills_for_prompt(resolved_skills)
    loaded_skills_block = format_loaded_skills_for_prompt(loaded_skills or [])
    return f"""You are Deepy, a terminal coding agent running in the user's project.

Work directly in the repository when asked to implement changes. Prefer small, verifiable edits.
Use tools for repository inspection and filesystem changes instead of guessing. Preserve user
changes you did not make.

Runtime:
- Project root: {project_root}
- Model: {settings.model.name}
- Thinking enabled: {settings.model.thinking_enabled}
- Reasoning effort: {settings.model.reasoning_effort}

Tool protocol:
- Tool results are JSON strings with ok, name, output, error, metadata, and awaitUserResponse.
- Read files before editing existing files.
- Ask the user only when the next action is genuinely blocked by missing intent or approval.

Default skill:
{AGENT_DRIFT_GUARD}

Project rules:
{project_rules_block}

Available skills:
{skills_block}

Loaded skills:
{loaded_skills_block}
"""
