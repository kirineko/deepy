from __future__ import annotations

from pathlib import Path

from deepy.skills import SkillInfo
from deepy.ui.slash_commands import (
    build_slash_commands,
    filter_slash_commands,
    find_exact_slash_command,
    format_slash_command_description,
    format_slash_command_label,
)


SKILLS = [
    SkillInfo("skill-writer", Path("/skills/skill-writer"), "Write a SKILL.md", "user"),
    SkillInfo("code-review", Path("/skills/code-review"), "Review code", "user"),
]


def test_build_slash_commands_orders_builtins_subagents_then_skills():
    items = build_slash_commands(SKILLS)

    assert [item.name for item in items if item.kind not in {"skill", "subagent"}] == [
        "compact",
        "exit",
        "help",
        "init",
        "input-suggestion",
        "mcp",
        "model",
        "new",
        "ps",
        "reset",
        "resume",
        "skills",
        "status",
        "stop",
        "theme",
    ]
    assert [item.name for item in items if item.kind == "subagent"] == [
        "explore",
        "reviewer",
        "tester",
    ]
    assert [item.name for item in items if item.kind == "skill"] == [
        "code-review",
        "skill-writer",
    ]


def test_filter_slash_commands_matches_partial_tokens():
    items = build_slash_commands(SKILLS)

    assert [item.name for item in filter_slash_commands(items, "/skil")] == [
        "skills",
        "code-review",
        "skill-writer",
    ]


def test_filter_slash_commands_ranks_prefixes_before_weaker_matches():
    items = build_slash_commands(SKILLS)

    names = [item.name for item in filter_slash_commands(items, "/re")]
    assert names[:3] == [
        "resume",
        "reviewer",
        "reset",
    ]
    assert "code-review" in names


def test_filter_slash_commands_ranks_bare_slash_by_user_intent():
    items = build_slash_commands(SKILLS)

    ranked = filter_slash_commands(items, "/")
    names = [item.name for item in ranked]
    assert names[:9] == [
        "help",
        "new",
        "resume",
        "model",
        "skills",
        "status",
        "compact",
        "mcp",
        "exit",
    ]
    assert names[9:12] == ["explore", "reviewer", "tester"]
    assert names.index("skill-writer") < names.index("reset")
    assert names.index("code-review") < names.index("reset")


def test_filter_slash_commands_ranks_loaded_skills_first():
    items = build_slash_commands(SKILLS, loaded_skill_names=["skill-writer"])

    skills = [item.name for item in filter_slash_commands(items, "/") if item.kind == "skill"]
    assert skills == ["skill-writer", "code-review"]


def test_filter_slash_commands_supports_legacy_skill_prefix():
    items = build_slash_commands(SKILLS)

    assert [item.name for item in filter_slash_commands(items, "/skill:")] == [
        "code-review",
        "skill-writer",
    ]


def test_filter_slash_commands_returns_nothing_for_non_slash_tokens():
    assert filter_slash_commands(build_slash_commands(SKILLS), "skill") == []


def test_find_exact_slash_command_returns_none_when_missing():
    assert find_exact_slash_command(build_slash_commands(SKILLS), "/missing") is None


def test_find_exact_slash_command_returns_builtins():
    items = build_slash_commands(SKILLS)

    assert find_exact_slash_command(items, "/new").kind == "new"
    assert find_exact_slash_command(items, "/init").kind == "init"
    assert find_exact_slash_command(items, "/skills").kind == "skills"
    assert find_exact_slash_command(items, "/model").kind == "model"
    assert find_exact_slash_command(items, "/input-suggestion").kind == "input-suggestion"
    assert find_exact_slash_command(items, "/mcp").kind == "mcp"
    assert find_exact_slash_command(items, "/ps").kind == "ps"
    assert find_exact_slash_command(items, "/stop").kind == "stop"
    assert find_exact_slash_command(items, "/status").kind == "status"
    assert find_exact_slash_command(items, "/theme").kind == "theme"
    assert find_exact_slash_command(items, "/reset").kind == "reset"


def test_find_exact_slash_command_returns_matching_skill():
    item = find_exact_slash_command(build_slash_commands(SKILLS), "/code-review")

    assert item is not None
    assert item.kind == "skill"
    assert item.skill and item.skill.name == "code-review"


def test_find_exact_slash_command_supports_legacy_skill_prefix():
    item = find_exact_slash_command(build_slash_commands(SKILLS), "/skill:code-review")

    assert item is not None
    assert item.kind == "skill"
    assert item.skill and item.skill.name == "code-review"


def test_format_slash_command_description_keeps_one_line():
    assert format_slash_command_description("Line one\n  line two") == "Line one line two"


def test_format_slash_command_label_marks_loaded_skills():
    items = build_slash_commands(
        [
            SkillInfo("loaded", Path("/skills/loaded"), "Loaded skill", "user", is_loaded=True),
            SkillInfo("fresh", Path("/skills/fresh"), "Fresh skill", "user"),
        ]
    )

    labels = {
        item.name: format_slash_command_label(item)
        for item in items
        if item.kind == "skill"
    }
    assert labels["loaded"] == "/loaded *"
    assert labels["fresh"] == "/fresh"


def test_build_slash_commands_marks_loaded_skill_names():
    items = build_slash_commands(SKILLS, loaded_skill_names=["code-review"])

    labels = {item.name: format_slash_command_label(item) for item in items}
    assert labels["skill-writer"] == "/skill-writer"
    assert labels["code-review"] == "/code-review *"
