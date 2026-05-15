from __future__ import annotations

import re
from dataclasses import dataclass, replace

from deepy.skills import SkillInfo


@dataclass(frozen=True)
class SlashCommandItem:
    kind: str
    name: str
    label: str
    description: str
    skill: SkillInfo | None = None


BUILTIN_SLASH_COMMANDS = (
    SlashCommandItem("skills", "skills", "/skills", "Manage skills"),
    SlashCommandItem("model", "model", "/model", "Select model and thinking strength"),
    SlashCommandItem("new", "new", "/new", "Start a fresh conversation"),
    SlashCommandItem("init", "init", "/init", "Create or update project AGENTS.md"),
    SlashCommandItem("mcp", "mcp", "/mcp", "Show MCP server status and tools"),
    SlashCommandItem("resume", "resume", "/resume", "Pick a previous conversation to continue"),
    SlashCommandItem("compact", "compact", "/compact", "Compact the active conversation context"),
    SlashCommandItem("theme", "theme", "/theme", "Show or change UI theme"),
    SlashCommandItem("reset", "reset", "/reset", "Delete config and run setup again"),
    SlashCommandItem("exit", "exit", "/exit", "Quit Deepy"),
)


def build_slash_commands(
    skills: list[SkillInfo],
    loaded_skill_names: list[str] | None = None,
) -> list[SlashCommandItem]:
    loaded = {name.lower() for name in loaded_skill_names or []}
    skill_items = [
        SlashCommandItem(
            kind="skill",
            name=f"skill:{skill.name}",
            label=f"/skill:{skill.name}",
            description=skill.description or "(no description)",
            skill=replace(skill, is_loaded=skill.is_loaded or skill.name.lower() in loaded),
        )
        for skill in skills
    ]
    return [*skill_items, *BUILTIN_SLASH_COMMANDS]


def filter_slash_commands(items: list[SlashCommandItem], token: str) -> list[SlashCommandItem]:
    if not token.startswith("/"):
        return []
    query = token[1:].lower()
    if not query:
        return items
    return [item for item in items if query in item.name.lower() or query in item.label[1:].lower()]


def find_exact_slash_command(
    items: list[SlashCommandItem],
    token: str,
) -> SlashCommandItem | None:
    if not token.startswith("/"):
        return None
    query = token[1:]
    matches = [item for item in items if item.name == query]
    builtin = next((item for item in matches if item.kind != "skill"), None)
    return builtin or (matches[0] if matches else None)


def format_slash_command_description(description: str) -> str:
    return re.sub(r"\s+", " ", description or "(no description)").strip()


def format_slash_command_label(item: SlashCommandItem) -> str:
    loaded = bool(item.skill and item.skill.is_loaded)
    return f"{item.label} *" if item.kind == "skill" and loaded else item.label
