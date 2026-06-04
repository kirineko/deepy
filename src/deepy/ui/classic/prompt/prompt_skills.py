"""Skill-selection helpers for the prompt input.

Extracted from ``deepy.ui.classic.prompt.prompt_input`` and re-exported there for backwards
compatibility.
"""

from __future__ import annotations

from deepy.skills import SkillInfo


def format_selected_skills_status(skills: list[SkillInfo]) -> str:
    names = [skill.name for skill in skills if skill.name]
    if not names:
        return ""
    return f"⚡ {', '.join(names)}"


def is_skill_selected(skills: list[SkillInfo], skill: SkillInfo) -> bool:
    return any(item.name == skill.name for item in skills)


def add_unique_skill(skills: list[SkillInfo], skill: SkillInfo) -> list[SkillInfo]:
    if is_skill_selected(skills, skill):
        return skills
    return [*skills, skill]


def toggle_skill_selection(skills: list[SkillInfo], skill: SkillInfo) -> list[SkillInfo]:
    if is_skill_selected(skills, skill):
        return [item for item in skills if item.name != skill.name]
    return [*skills, skill]
