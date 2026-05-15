from __future__ import annotations

from pathlib import Path

from deepy.skill_market import MarketSkill
from deepy.ui.skill_picker import (
    InstalledSkillView,
    SkillInstallScope,
    SkillMenuPicker,
    format_installed_skill_label,
    format_market_skill_label,
)


def test_format_market_skill_label_marks_installed():
    label = format_market_skill_label(
        MarketSkill(
            name="docx",
            description="Create and edit Word documents.",
            version="1.0",
            uploaded_at="2026-05-15T00:00:00+00:00",
            installed=True,
        )
    )

    assert "[x] docx  1.0  uploaded 2026-05-15" in label
    assert "Create and edit Word documents." in label


def test_format_installed_skill_label_includes_path():
    label = format_installed_skill_label(
        InstalledSkillView(
            name="pdf",
            scope="user",
            path=Path("/tmp/.agents/skills/pdf"),
            version="1.0",
            installed_at="2026-05-15T00:00:00+00:00",
            managed_by_market=True,
        )
    )

    assert "[market] pdf  1.0  installed 2026-05-15" in label
    assert "/tmp/.agents/skills/pdf" in label


def test_skill_menu_picker_actions_match_view():
    picker = SkillMenuPicker(
        [
            MarketSkill(name="docx", installed=False),
            MarketSkill(name="pdf", installed=True),
        ],
        [
            InstalledSkillView(
                name="pdf",
                scope="user",
                path=Path("/tmp/pdf"),
                version="1.0",
                installed_at="now",
                managed_by_market=True,
            )
        ],
    )

    assert picker._primary_action().action == "choose-install-scope"
    picker._radio_list.current_value = "pdf"
    assert picker._primary_action().action == "update"
    picker._set_view("installed")
    assert picker._primary_action().action == "show"
    assert picker._toggle_action().action == "uninstall"


def test_skill_menu_picker_remove_local_for_manual_installed_skill():
    picker = SkillMenuPicker(
        [],
        [
            InstalledSkillView(
                name="manual",
                scope="project",
                path=Path("/tmp/project/.agents/skills/manual"),
            )
        ],
        initial_view="installed",
    )

    assert picker._primary_action().action == "show"
    assert picker._toggle_action().action == "remove-local"
    assert picker._update_action() is None


def test_skill_menu_picker_starts_with_loading_state_for_deferred_market():
    picker = SkillMenuPicker(
        None,
        [],
        market_loader=lambda: [MarketSkill(name="docx")],
    )

    assert picker._market_loading is True
    assert picker._radio_list.current_value == "__empty__"
    assert "Loading market skills" in picker._radio_list.values[0][1]


def test_skill_install_scope_paths(tmp_path):
    choice = SkillInstallScope("project", tmp_path / ".agents" / "skills" / "docx")

    assert choice.scope == "project"
    assert choice.path == tmp_path / ".agents" / "skills" / "docx"
