from __future__ import annotations

import re
from dataclasses import dataclass, replace

from deepy.skills import SkillInfo
from deepy.subagents import built_in_subagents


@dataclass(frozen=True)
class SlashCommandItem:
    kind: str
    name: str
    label: str
    description: str
    skill: SkillInfo | None = None


BUILTIN_SLASH_COMMANDS = (
    SlashCommandItem("compact", "compact", "/compact", "Compact the active conversation context"),
    SlashCommandItem("exit", "exit", "/exit", "Quit Deepy"),
    SlashCommandItem("help", "help", "/help", "Show help"),
    SlashCommandItem("init", "init", "/init", "Create or update project AGENTS.md"),
    SlashCommandItem("input-suggestion", "input-suggestion", "/input-suggestion", "Toggle input suggestions"),
    SlashCommandItem("mcp", "mcp", "/mcp", "Show MCP server status and tools"),
    SlashCommandItem("model", "model", "/model", "Select model and thinking strength"),
    SlashCommandItem("new", "new", "/new", "Start a fresh conversation"),
    SlashCommandItem("ps", "ps", "/ps", "Show background tasks"),
    SlashCommandItem("reset", "reset", "/reset", "Delete config and run setup again"),
    SlashCommandItem("resume", "resume", "/resume", "Pick a previous conversation to continue"),
    SlashCommandItem("skills", "skills", "/skills", "Manage skills"),
    SlashCommandItem("status", "status", "/status", "Show status, usage, and DeepSeek balance"),
    SlashCommandItem("stop", "stop", "/stop", "Choose background tasks to stop"),
    SlashCommandItem("theme", "theme", "/theme", "Show or change UI theme"),
)
SUBAGENT_SLASH_COMMANDS = tuple(
    SlashCommandItem(
        "subagent",
        definition.name,
        f"/{definition.name}",
        definition.description,
    )
    for definition in sorted(built_in_subagents(), key=lambda item: item.name)
)
BUILTIN_SLASH_COMMAND_NAMES = frozenset(item.name for item in BUILTIN_SLASH_COMMANDS)
SUBAGENT_SLASH_COMMAND_NAMES = frozenset(item.name for item in SUBAGENT_SLASH_COMMANDS)


def build_slash_commands(
    skills: list[SkillInfo],
    loaded_skill_names: list[str] | None = None,
) -> list[SlashCommandItem]:
    loaded = {name.lower() for name in loaded_skill_names or []}
    skill_items = [
        SlashCommandItem(
            kind="skill",
            name=skill.name,
            label=f"/{skill.name}",
            description=skill.description or "(no description)",
            skill=replace(skill, is_loaded=skill.is_loaded or skill.name.lower() in loaded),
        )
        for skill in sorted(skills, key=lambda item: item.name.lower())
    ]
    return [*BUILTIN_SLASH_COMMANDS, *SUBAGENT_SLASH_COMMANDS, *skill_items]


def filter_slash_commands(items: list[SlashCommandItem], token: str) -> list[SlashCommandItem]:
    if not token.startswith("/"):
        return []
    query = token[1:].lower()
    if not query:
        return items
    return [
        item
        for item in items
        if item.name.lower().startswith(query) or item.label[1:].lower().startswith(query)
    ]


def find_exact_slash_command(
    items: list[SlashCommandItem],
    token: str,
) -> SlashCommandItem | None:
    if not token.startswith("/"):
        return None
    query = token[1:]
    matches = [
        item
        for item in items
        if item.name == query or (item.kind == "skill" and f"skill:{item.name}" == query)
    ]
    builtin = next((item for item in matches if item.kind != "skill"), None)
    return builtin or (matches[0] if matches else None)


def format_slash_command_description(description: str) -> str:
    return re.sub(r"\s+", " ", description or "(no description)").strip()


def format_slash_command_label(item: SlashCommandItem) -> str:
    loaded = bool(item.skill and item.skill.is_loaded)
    return f"{item.label} *" if item.kind == "skill" and loaded else item.label


def is_builtin_slash_command(name: str) -> bool:
    return name in BUILTIN_SLASH_COMMAND_NAMES


def is_subagent_slash_command(name: str) -> bool:
    return name in SUBAGENT_SLASH_COMMAND_NAMES


def build_subagent_slash_prompt(name: str, argument: str) -> str:
    task = argument.strip() or "Perform your default focused task for the current request."
    return (
        f"Use the `subagent_{name}` subagent for this task. "
        "Delegate the work to that subagent and then summarize its result for the user.\n\n"
        f"Task:\n{task}"
    )
