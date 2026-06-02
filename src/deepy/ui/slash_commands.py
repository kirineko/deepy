from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import IntEnum

from deepy.skills import SkillInfo
from deepy.subagents import built_in_subagents


@dataclass(frozen=True)
class SlashCommandItem:
    kind: str
    name: str
    label: str
    description: str
    skill: SkillInfo | None = None
    category: str = "Commands"
    aliases: tuple[str, ...] = ()
    stable: bool = True
    textual: bool = True


BUILTIN_SLASH_COMMANDS: tuple[SlashCommandItem, ...] = (
    SlashCommandItem("compact", "compact", "/compact", "Compact the active conversation context", category="Session"),
    SlashCommandItem("exit", "exit", "/exit", "Quit Deepy", category="System", aliases=("quit",)),
    SlashCommandItem("help", "help", "/help", "Show commands, keybindings, and TUI state", category="Help"),
    SlashCommandItem("init", "init", "/init", "Create or update project AGENTS.md", category="System"),
    SlashCommandItem("input-suggestion", "input-suggestion", "/input-suggestion", "Toggle input suggestions", category="Settings"),
    SlashCommandItem("mcp", "mcp", "/mcp", "Show MCP status", category="Tools"),
    SlashCommandItem("model", "model", "/model", "Select model and thinking strength", category="Settings"),
    SlashCommandItem("new", "new", "/new", "Start a fresh conversation", category="Session"),
    SlashCommandItem("ps", "ps", "/ps", "Show background tasks", category="Tools"),
    SlashCommandItem("reset", "reset", "/reset", "Delete config and run setup again", category="System"),
    SlashCommandItem("resume", "resume", "/resume", "Pick a previous conversation to continue", category="Session"),
    SlashCommandItem("sessions", "sessions", "/sessions", "List project sessions", category="Session"),
    SlashCommandItem("skills", "skills", "/skills", "Manage skills", category="Skills"),
    SlashCommandItem("status", "status", "/status", "Show project, session, MCP, and settings status", category="Help"),
    SlashCommandItem("stop", "stop", "/stop", "Choose background tasks to stop", category="Tools"),
    SlashCommandItem("theme", "theme", "/theme", "Show or change UI theme", category="Settings"),
    SlashCommandItem("ui", "ui", "/ui", "Show or change Classic/Modern UI", category="Settings"),
    SlashCommandItem("view", "view", "/view", "Hide or show reasoning transcript text", category="Settings"),
)
SUBAGENT_SLASH_COMMANDS = tuple(
    SlashCommandItem(
        "subagent",
        definition.name,
        f"/{definition.name}",
        definition.description,
        category="Subagents",
    )
    for definition in sorted(built_in_subagents(), key=lambda item: item.name)
)
BUILTIN_SLASH_COMMAND_NAMES = frozenset(
    name for item in BUILTIN_SLASH_COMMANDS for name in (item.name, *item.aliases)
)
SUBAGENT_SLASH_COMMAND_NAMES = frozenset(
    name for item in SUBAGENT_SLASH_COMMANDS for name in (item.name, *item.aliases)
)
COMMON_WORKFLOW_COMMAND_ORDER = {
    "help": 0,
    "new": 1,
    "resume": 2,
    "sessions": 3,
    "model": 4,
    "view": 5,
    "skills": 6,
    "status": 7,
    "compact": 8,
    "mcp": 9,
    "exit": 10,
}
LOW_FREQUENCY_COMMAND_ORDER = {
    "init": 0,
    "theme": 1,
    "ui": 2,
    "input-suggestion": 3,
    "ps": 4,
    "stop": 5,
    "reset": 6,
}
SKILL_SCOPE_PRIORITY = {
    "project": 0,
    "user": 1,
    "builtin": 2,
}


class SlashCommandMatch(IntEnum):
    EXACT = 0
    PREFIX = 1
    WEAK = 2


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
            category="Skills",
            skill=replace(skill, is_loaded=skill.is_loaded or skill.name.lower() in loaded),
        )
        for skill in sorted(skills, key=lambda item: item.name.lower())
    ]
    return [*BUILTIN_SLASH_COMMANDS, *SUBAGENT_SLASH_COMMANDS, *skill_items]


def filter_slash_commands(items: list[SlashCommandItem], token: str) -> list[SlashCommandItem]:
    return rank_slash_commands(items, token)


def rank_slash_commands(items: list[SlashCommandItem], token: str) -> list[SlashCommandItem]:
    if not token.startswith("/"):
        return []
    query = token[1:].lower()
    if not query:
        return sorted(items, key=slash_command_sort_key)
    scored = [
        (match, slash_command_sort_key(item), item)
        for item in items
        if (match := slash_command_match(item, query)) is not None
    ]
    scored.sort(key=lambda scored_item: (scored_item[0], scored_item[1]))
    return [item for _match, _sort_key, item in scored]


def slash_command_match(item: SlashCommandItem, query: str) -> SlashCommandMatch | None:
    normalized = query.lower()
    name = item.name.lower()
    label = item.label[1:].lower()
    description = item.description.lower()
    legacy_skill_name = f"skill:{name}" if item.kind == "skill" else ""
    values = [name, label, *(alias.lower() for alias in item.aliases)]
    if legacy_skill_name:
        values.append(legacy_skill_name)
    if any(value == normalized for value in values):
        return SlashCommandMatch.EXACT
    if any(value.startswith(normalized) for value in values):
        return SlashCommandMatch.PREFIX
    if normalized in name or normalized in label or normalized in description:
        return SlashCommandMatch.WEAK
    return None


def slash_command_sort_key(item: SlashCommandItem) -> tuple[int, int, int, str]:
    return (
        slash_command_priority(item),
        slash_command_loaded_priority(item),
        slash_command_scope_priority(item),
        item.name.lower(),
    )


def slash_command_priority(item: SlashCommandItem | str) -> int:
    if isinstance(item, str):
        name = item
        kind = "builtin"
    else:
        name = item.name
        kind = item.kind
    if name in COMMON_WORKFLOW_COMMAND_ORDER:
        return COMMON_WORKFLOW_COMMAND_ORDER[name]
    if kind == "subagent":
        return 100
    if kind == "skill":
        return 200
    if name in LOW_FREQUENCY_COMMAND_ORDER:
        return 300 + LOW_FREQUENCY_COMMAND_ORDER[name]
    return 250


def slash_command_loaded_priority(item: SlashCommandItem) -> int:
    if item.kind == "skill" and item.skill and item.skill.is_loaded:
        return 0
    return 1


def slash_command_scope_priority(item: SlashCommandItem) -> int:
    if item.kind != "skill" or item.skill is None:
        return 0
    return SKILL_SCOPE_PRIORITY.get(item.skill.scope, 3)


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
        if item.name == query
        or query in item.aliases
        or (item.kind == "skill" and f"skill:{item.name}" == query)
    ]
    builtin = next((item for item in matches if item.kind != "skill"), None)
    return builtin or (matches[0] if matches else None)


def format_slash_command_description(description: str) -> str:
    return re.sub(r"\s+", " ", description or "(no description)").strip()


def format_slash_command_label(item: SlashCommandItem) -> str:
    loaded = bool(item.skill and item.skill.is_loaded)
    return f"{item.label} *" if item.kind == "skill" and loaded else item.label


def format_slash_command_completion_label(item: SlashCommandItem, token: str = "") -> str:
    label = item.label
    if item.kind == "skill" and token[1:].lower().startswith("skill:"):
        label = f"/skill:{item.name}"
    loaded = bool(item.skill and item.skill.is_loaded)
    return f"{label} *" if item.kind == "skill" and loaded else label


def is_builtin_slash_command(name: str) -> bool:
    return name in BUILTIN_SLASH_COMMAND_NAMES


def is_subagent_slash_command(name: str) -> bool:
    return name in SUBAGENT_SLASH_COMMAND_NAMES


def builtin_command_by_name(name: str) -> SlashCommandItem | None:
    normalized = name.lower().lstrip("/")
    return next(
        (
            item
            for item in BUILTIN_SLASH_COMMANDS
            if item.name == normalized or normalized in item.aliases
        ),
        None,
    )


def textual_builtin_commands() -> list[SlashCommandItem]:
    return [item for item in BUILTIN_SLASH_COMMANDS if item.textual]


def categorized_command_markdown(
    commands: list[SlashCommandItem] | tuple[SlashCommandItem, ...],
    *,
    title: str = "Deepy Commands",
) -> str:
    lines: list[str] = [f"# {title}", ""]
    current_category = ""
    for command in commands:
        if command.category != current_category:
            current_category = command.category
            lines.extend(["", f"## {current_category}"])
        alias_text = (
            f" _(alias: {', '.join('/' + alias for alias in command.aliases)})_"
            if command.aliases
            else ""
        )
        lines.append(f"- **{command.label}** - {command.description}{alias_text}")
    return "\n".join(lines).strip()


def build_subagent_slash_prompt(name: str, argument: str) -> str:
    task = argument.strip() or "Perform your default focused task for the current request."
    return (
        f"Use the `subagent_{name}` subagent for this task. "
        "Delegate the work to that subagent and then summarize its result for the user.\n\n"
        f"Task:\n{task}"
    )
