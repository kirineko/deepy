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


def test_build_slash_commands_prefixes_skills_before_builtins():
    items = build_slash_commands(SKILLS)

    assert items[0].kind == "skill"
    assert items[0].name == "skill-writer"
    assert [item.name for item in items if item.kind != "skill"] == [
        "skills",
        "new",
        "resume",
        "exit",
    ]


def test_filter_slash_commands_matches_partial_tokens():
    items = build_slash_commands(SKILLS)

    assert [item.name for item in filter_slash_commands(items, "/skil")] == [
        "skill-writer",
        "skills",
    ]


def test_filter_slash_commands_returns_all_on_bare_slash():
    items = build_slash_commands(SKILLS)

    assert filter_slash_commands(items, "/") == items


def test_filter_slash_commands_returns_nothing_for_non_slash_tokens():
    assert filter_slash_commands(build_slash_commands(SKILLS), "skill") == []


def test_find_exact_slash_command_returns_none_when_missing():
    assert find_exact_slash_command(build_slash_commands(SKILLS), "/missing") is None


def test_find_exact_slash_command_returns_builtins():
    items = build_slash_commands(SKILLS)

    assert find_exact_slash_command(items, "/new").kind == "new"
    assert find_exact_slash_command(items, "/skills").kind == "skills"


def test_find_exact_slash_command_returns_matching_skill():
    item = find_exact_slash_command(build_slash_commands(SKILLS), "/code-review")

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

    assert format_slash_command_label(items[0]) == "/loaded *"
    assert format_slash_command_label(items[1]) == "/fresh"
