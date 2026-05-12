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
from .runtime_context import build_runtime_context
from .tool_docs import load_tool_docs


def build_system_prompt(
    project_root: Path,
    settings: Settings,
    *,
    project_rules: str | None = None,
    skills: list[SkillInfo] | None = None,
    loaded_skills: list[SkillInfo] | None = None,
    runtime_context: str | None = None,
) -> str:
    resolved_project_rules = (
        load_project_rules(project_root) if project_rules is None else project_rules.strip()
    )
    resolved_skills = discover_skills(project_root) if skills is None else skills
    project_rules_block = resolved_project_rules or "No project rules found."
    skills_block = format_skills_for_prompt(resolved_skills)
    loaded_skills_block = format_loaded_skills_for_prompt(loaded_skills or [])
    runtime_context_block = runtime_context or build_runtime_context(project_root)
    tool_docs_block = load_tool_docs()
    return f"""You are Deepy, a terminal coding agent in the user's project.

Core rules:
- Work in the repo with tools: inspect, edit, test, verify.
- Preserve user changes. Prefer small, verifiable edits.
- Read before changing existing files.
- Existing targeted changes -> `edit`; new files or explicit whole-file replacement -> `write`.
- If `write` on an existing file is rejected for unread state, read it and usually use `edit`.
- Ask only when blocked by missing intent or required approval.

Runtime: root={project_root}; model={settings.model.name}; thinking={settings.model.thinking_enabled}; reasoning={settings.model.reasoning_effort}

Project context:
{runtime_context_block}

Tool protocol:
Tool results are JSON strings: ok, name, output, error, metadata, awaitUserResponse.

Tool documentation:
{tool_docs_block}

Default skill:
{AGENT_DRIFT_GUARD}

Project rules:
{project_rules_block}

Available skills:
{skills_block}

Loaded skills:
{loaded_skills_block}
"""
