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
    runtime_context_block = runtime_context or build_runtime_context(
        project_root,
        include_git_dirty=False,
    )
    tool_docs_block = load_tool_docs()
    # Keep stable instructions before project/runtime blocks so DeepSeek can reuse
    # a longer request prefix through its context cache.
    return f"""You are Deepy, a terminal coding agent in the user's project.

Core rules:
- Work in the repo with tools: inspect, modify, test, verify.
- Preserve user changes. Prefer small, verifiable edits.
- Read before changing existing files.
- Use `modify` for file changes: `content` only creates new files; existing files use `old_string`/`new_string`.
- After project generators create scaffold files, read and edit the generated block instead of replacing the file.
- Run shell commands using the Runtime context's command dialect and path style: `powershell` -> PowerShell with Windows paths; `cmd` -> cmd; `posix` -> POSIX shell.
- Ask when clarification would materially improve the result: ambiguous intent, unclear scope,
  user preferences, high-impact trade-offs, or required approval. For low-impact details,
  proceed with a reasonable assumption and state it briefly.

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

Runtime context:
Runtime: root={project_root}; model={settings.model.name}; reasoning={settings.model.reasoning_mode}
{runtime_context_block}
"""
