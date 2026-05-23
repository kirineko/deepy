from __future__ import annotations

from pathlib import Path

from rich.console import Console

from deepy.skills import SkillInfo
from deepy.update_check import VersionUpdate
from deepy.ui.welcome import build_deepy_ascii_logo
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
    assert "/review" not in labels
    assert "/plan" not in labels
    assert "/resume" in labels
    assert "/new" in labels
    assert "/skills" in labels
    assert "/exit" not in labels
    assert "Enter" not in labels
    assert "Shift+Enter" not in labels
    assert "/" in labels
    assert "Esc" in labels
    assert "Ctrl+D twice" in labels


def test_build_welcome_settings_uses_deepy_fields(tmp_path):
    settings = build_welcome_settings(
        model="deepseek-v4-pro",
        thinking_enabled=True,
        reasoning_effort="max",
        project_root=Path("/tmp/home/project"),
        current_version="0.1.0",
        home=Path("/tmp/home"),
    )

    assert [(item.label, item.value) for item in settings] == [
        ("Version", "0.1.0"),
        ("Provider", "deepseek"),
        ("Model", "deepseek-v4-pro"),
        ("Thinking", "max"),
        ("CWD", "~/project"),
    ]


def test_build_welcome_settings_uses_none_when_thinking_is_disabled(tmp_path):
    settings = build_welcome_settings(
        model="deepseek-v4-pro",
        thinking_enabled=False,
        reasoning_effort="max",
        project_root=Path("/tmp/home/project"),
        current_version="0.1.0",
        home=Path("/tmp/home"),
    )

    assert ("Thinking", "none") in [(item.label, item.value) for item in settings]


def test_build_welcome_settings_includes_theme_when_available(tmp_path):
    settings = build_welcome_settings(
        model="deepseek-v4-pro",
        thinking_enabled=True,
        reasoning_effort="max",
        project_root=tmp_path,
        current_version="0.1.0",
        theme="dark",
        resolved_theme="dark",
    )

    assert ("Theme", "dark") in [(item.label, item.value) for item in settings]


def test_build_welcome_settings_shows_available_update(tmp_path):
    settings = build_welcome_settings(
        model="deepseek-v4-pro",
        thinking_enabled=True,
        reasoning_effort="max",
        project_root=tmp_path,
        current_version="0.1.0",
        version_update=VersionUpdate(
            current_version="0.1.0",
            latest_version="0.2.0",
            source="PyPI",
            url="https://pypi.org/project/deepy-cli/",
            install_hint="uv tool upgrade deepy-cli",
        ),
    )

    assert settings[0].label == "Version"
    assert settings[0].value == "0.1.0 -> 0.2.0 available from PyPI"
    assert (settings[-1].label, settings[-1].value) == ("Update", "uv tool upgrade deepy-cli")


def test_build_deepy_ascii_logo_contains_terminal_mark():
    rendered = build_deepy_ascii_logo().plain

    assert ".----." in rendered
    assert ">_" in rendered
    assert "Deepy" in rendered
    assert ".-''''-." not in rendered
    assert "____" not in rendered


def test_build_welcome_panel_renders_settings_and_tips(tmp_path):
    console = Console(record=True, width=120)

    console.print(
        build_welcome_panel(
            model="deepseek-v4-pro",
            thinking_enabled=True,
            reasoning_effort="max",
            project_root=tmp_path,
            skills=[],
            current_version="0.1.0",
            home=tmp_path.parent,
            theme="light",
            resolved_theme="light",
        )
    )

    rendered = console.export_text()
    assert "Deepy" in rendered
    assert ">_" in rendered
    assert "Terminal coding agent" in rendered
    assert "0.1.0" in rendered
    assert "deepseek" in rendered
    assert "deepseek-v4-pro" in rendered
    assert "Thinking" in rendered
    assert "Theme" in rendered
    assert "light" in rendered
    assert "/resume" in rendered
