"""Skill formatting helpers for the Modern UI.

Pure helpers that build skill entries and markdown/text summaries. The
``_installed_skill_entries`` orchestrator stays in :mod:`deepy.ui.modern.app` because
it calls the monkeypatched ``list_installed_skills`` entry point.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from deepy.skill_market import InstalledSkill, MarketSkill
from deepy.skills import SkillInfo, read_skill_body
from deepy.ui.modern.screens import SkillScreenEntry


def _remove_local_skill_directory(path: Path) -> Path:
    skill_path = path / "SKILL.md"
    if not path.is_dir() or not skill_path.is_file():
        raise ValueError(f"Skill path is invalid: {path}")
    if path.parent.name != "skills" or path.parent.parent.name != ".agents":
        raise ValueError(f"Refusing to remove unexpected path: {path}")
    shutil.rmtree(path)
    return path


def _market_skill_entry(skill: MarketSkill, *, local_names: set[str]) -> SkillScreenEntry:
    return SkillScreenEntry(
        name=skill.name,
        scope="market",
        description=skill.description,
        version=skill.version,
        installed=skill.installed or skill.name in local_names,
        managed_by_market=skill.installed,
        source="market",
    )


def _skill_detail_markdown(skill: SkillInfo) -> str:
    body = read_skill_body(skill) or "(empty skill)"
    return "\n\n".join(
        [
            f"# {skill.name}",
            f"- Scope: `{skill.scope}`",
            f"- Path: `{skill.path.parent}`",
            body,
        ]
    )


def _market_detail_markdown(entry: SkillScreenEntry) -> str:
    lines = [
        f"# {entry.name}",
        "",
        f"- Scope: `{entry.scope}`",
        f"- Version: `{entry.version or 'unknown'}`",
        f"- Installed: `{'yes' if entry.installed else 'no'}`",
    ]
    if entry.description:
        lines.extend(["", entry.description])
    return "\n".join(lines)


def _format_market_skills(skills: list[MarketSkill]) -> str:
    if not skills:
        return "No market skills found."
    lines = ["Market skills:"]
    for skill in skills:
        marker = " (installed)" if skill.installed else ""
        description = f" - {skill.description}" if skill.description else ""
        version = f" version={skill.version}" if skill.version else ""
        lines.append(f"- {skill.name}{marker}{version}{description}")
    return "\n".join(lines)


def _format_installed_records(records: list[InstalledSkill]) -> str:
    if not records:
        return "No market-installed skills."
    lines = ["Market-installed skills:"]
    for record in records:
        lines.append(
            f"- {record.name} ({record.scope}) -> {record.install_path} installed={record.installed_at}"
        )
    return "\n".join(lines)
