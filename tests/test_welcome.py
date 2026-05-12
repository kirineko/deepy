from __future__ import annotations

from pathlib import Path

from rich.console import Console

from deepy.skills import SkillInfo
from deepy.ui.welcome import build_welcome_panel
from deepy.ui.welcome import build_welcome_settings
from deepy.ui.welcome import build_welcome_tips
from deepy.ui.welcome import format_home_relative_path


def test_format_home_relative_path_returns_tilde_for_home():
    assert format_home_relative_path("/tmp/home", home="/tmp/home") == "~"


def test_format_home_relative_path_returns_home_relative_child():
    assert format_home_relative_path("/tmp/home/project", home="/tmp/home") == "~/project"


def test_format_home_relative_path_returns_absolute_path_outside_home():
    assert format_home_relative_path("/tmp/other/project", home="/tmp/home") == "/tmp/other/project"


def test_build_welcome_tips_includes_builtins_and_loaded_skills_only(tmp_path):
    tips = build_welcome_tips(
        [
            SkillInfo(
                name="review",
                description="Review current changes",
                path=tmp_path / "review" / "SKILL.md",
                is_loaded=True,
            ),
            SkillInfo(
                name="plan",
                description="Plan work",
                path=tmp_path / "plan" / "SKILL.md",
                is_loaded=False,
            ),
        ]
    )

    labels = [tip.label for tip in tips]
    assert "/review" in labels
    assert "/plan" not in labels
    assert "/resume" in labels
    assert "Enter" in labels
    assert "Ctrl+D twice" in labels


def test_build_welcome_settings_uses_deepy_fields(tmp_path):
    settings = build_welcome_settings(
        model="deepseek-v4-pro",
        thinking_enabled=True,
        reasoning_effort="max",
        project_root=Path("/tmp/home/project"),
        home=Path("/tmp/home"),
    )

    assert [(item.label, item.value) for item in settings] == [
        ("Model", "deepseek-v4-pro"),
        ("Thinking Enabled", "True"),
        ("Reasoning Effort", "max"),
        ("CWD", "~/project"),
    ]


def test_build_welcome_panel_renders_settings_and_tips(tmp_path):
    console = Console(record=True, width=120)

    console.print(
        build_welcome_panel(
            model="deepseek-v4-pro",
            thinking_enabled=True,
            reasoning_effort="max",
            project_root=tmp_path,
            skills=[],
            home=tmp_path.parent,
        )
    )

    rendered = console.export_text()
    assert "Deepy" in rendered
    assert "deepseek-v4-pro" in rendered
    assert "Reasoning Effort" in rendered
    assert "/resume" in rendered
