"""Skill slash-command and skill-menu handlers for the Classic terminal UI.

These handlers are fully self-contained: they render through the ``console``
argument and call the skill/skill-market entry points directly, with no
dependency on ``terminal.py`` internals. They were extracted from
``terminal.py`` so the skill surface can be tested and maintained in isolation.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from deepy.skill_market import (
    install_market_skill,
    list_installed_skills,
    search_market_skills,
    uninstall_market_skill,
    update_market_skill,
)
from deepy.skills import (
    SkillInfo,
    discover_skills,
    find_skill,
    format_skills_for_terminal,
    read_skill_body,
)
from deepy.ui.classic.pickers.skill_picker import (
    InstalledSkillView,
    SkillDetailView,
    SkillMenuAction,
    pick_skill_install_scope,
    pick_skill_menu_action,
    show_skill_detail_view,
)
from deepy.ui.shared.render.styles import UiPalette

if TYPE_CHECKING:
    from deepy.ui.shared.input.commands import SlashCommand


def _handle_skills_command(
    command: SlashCommand,
    console: Console,
    project_root: Path,
    current_session_id: str | None,
    loaded_skill_names: list[str],
    palette: UiPalette,
) -> str | None:
    action, _, rest = command.argument.partition(" ")
    action = action.strip().lower()
    argument = rest.strip()
    if not action:
        _run_skills_menu(console, project_root, loaded_skill_names, palette)
        return current_session_id
    if action == "list":
        console.print(format_skills_for_terminal(discover_skills(project_root)))
        return current_session_id
    if action == "show":
        if not argument:
            console.print(f"[{palette.error}]Usage:[/] /skills show NAME")
            return current_session_id
        skill = find_skill(project_root, argument)
        if skill is None:
            console.print(f"[{palette.error}]Skill not found:[/] {argument}")
            return current_session_id
        console.print(read_skill_body(skill) or "(empty skill)")
        return current_session_id
    if action == "use":
        if not argument:
            console.print(f"[{palette.error}]Usage:[/] /skills use NAME")
            return current_session_id
        skill = find_skill(project_root, argument)
        if skill is None:
            console.print(f"[{palette.error}]Skill not found:[/] {argument}")
            return current_session_id
        if skill.name not in loaded_skill_names:
            loaded_skill_names.append(skill.name)
        console.print(f"Loaded skill: {skill.name}")
        return current_session_id
    if action in {"search", "install", "uninstall", "installed", "update"}:
        changed = _handle_skill_market_command(action, argument, console, palette)
        if changed and action == "uninstall":
            loaded_skill_names[:] = [
                name for name in loaded_skill_names if name.lower() != argument.lower()
            ]
        return current_session_id
    console.print(
        f"[{palette.error}]Usage:[/] /skills [list|show NAME|use NAME|search QUERY|install NAME|"
        "uninstall NAME|installed|update NAME|update --all]"
    )
    return current_session_id


def _run_skills_menu(
    console: Console,
    project_root: Path,
    loaded_skill_names: list[str],
    palette: UiPalette,
) -> None:
    while True:
        try:
            installed_skills = _build_installed_skill_views(project_root)
        except Exception as exc:
            installed_skills = []
            console.print(f"[{palette.error}]Installed skills error:[/] {exc}")

        action = pick_skill_menu_action(
            None,
            installed_skills,
            market_loader=lambda: _load_market_skills_for_menu(project_root),
        )
        if action is None:
            return
        if action.action == "refresh":
            continue
        _handle_skill_menu_action(action, console, project_root, loaded_skill_names, palette)


def _build_installed_skill_views(project_root: Path) -> list[InstalledSkillView]:
    records = list_installed_skills()
    records_by_name = {record.name: record for record in records}
    views: list[InstalledSkillView] = []
    seen: set[str] = set()
    for skill in discover_skills(project_root):
        if skill.scope not in {"project", "user"}:
            continue
        record = records_by_name.get(skill.name)
        views.append(
            InstalledSkillView(
                name=skill.name,
                scope=record.scope if record is not None else skill.scope,
                path=record.install_path if record is not None else skill.path.parent,
                version=record.version if record is not None else "",
                installed_at=record.installed_at if record is not None else "",
                managed_by_market=record is not None,
            )
        )
        seen.add(skill.name)
    for record in records:
        if record.name in seen:
            continue
        views.append(
            InstalledSkillView(
                name=record.name,
                scope=record.scope,
                path=record.install_path,
                version=record.version,
                installed_at=record.installed_at,
                managed_by_market=True,
            )
        )
    return sorted(views, key=lambda item: (item.scope != "project", item.name))


def _load_market_skills_for_menu(project_root: Path):
    local_names = {
        skill.name
        for skill in discover_skills(project_root)
        if skill.scope in {"project", "user"}
    }
    return [
        replace(skill, installed=skill.installed or skill.name in local_names)
        for skill in search_market_skills("")
    ]


def _handle_skill_menu_action(
    action: SkillMenuAction,
    console: Console,
    project_root: Path,
    loaded_skill_names: list[str],
    palette: UiPalette,
) -> bool:
    if action.action == "choose-install-scope":
        install_scope = pick_skill_install_scope(
            action.name,
            home=Path.home(),
            project_root=project_root,
        )
        if install_scope is None:
            return False
        try:
            record = install_market_skill(
                action.name,
                scope=install_scope.scope,
                project_root=project_root,
            )
        except Exception as exc:
            console.print(f"[{palette.error}]Skill market error:[/] {exc}")
            return False
        console.print(f"Installed skill: {record.name} ({record.scope}) -> {record.install_path}")
        return True
    if action.action == "update":
        return _handle_skill_market_command("update", action.name, console, palette)
    if action.action == "uninstall":
        changed = _handle_skill_market_command("uninstall", action.name, console, palette)
        if changed:
            loaded_skill_names[:] = [
                name for name in loaded_skill_names if name.lower() != action.name.lower()
            ]
        return changed
    if action.action == "remove-local":
        return _remove_local_skill(action, console, loaded_skill_names, palette)
    if action.action == "show":
        if action.market_skill is not None and action.path is None:
            market_skill = action.market_skill
            show_skill_detail_view(
                SkillDetailView(
                    name=market_skill.name,
                    scope="market",
                    version=market_skill.version,
                    description=market_skill.description,
                    uploaded_at=market_skill.uploaded_at,
                    sha256=market_skill.sha256,
                    installed=market_skill.installed,
                    markdown=True,
                )
            )
            return False
        if action.path is not None:
            skill = SkillInfo(
                name=action.name,
                path=action.path / "SKILL.md",
                scope=action.scope or "user",
            )
        else:
            skill = find_skill(project_root, action.name)
        if skill is None:
            console.print(f"[{palette.error}]Skill not installed:[/] {action.name}")
            return False
        show_skill_detail_view(
            SkillDetailView(
                name=skill.name,
                body=read_skill_body(skill) or "(empty skill)",
                scope=skill.scope,
                path=skill.path.parent,
                version=action.version,
                installed_at=action.installed_at,
                managed_by_market=action.managed_by_market,
                markdown=True,
            )
        )
        return False
    return False


def _remove_local_skill(
    action: SkillMenuAction,
    console: Console,
    loaded_skill_names: list[str],
    palette: UiPalette,
) -> bool:
    if action.path is None:
        console.print(f"[{palette.error}]Skill path is unknown:[/] {action.name}")
        return False
    skill_path = action.path / "SKILL.md"
    if not action.path.is_dir() or not skill_path.is_file():
        console.print(f"[{palette.error}]Skill path is invalid:[/] {action.path}")
        return False
    if action.path.parent.name != "skills" or action.path.parent.parent.name != ".agents":
        console.print(f"[{palette.error}]Refusing to remove unexpected path:[/] {action.path}")
        return False
    shutil.rmtree(action.path)
    loaded_skill_names[:] = [
        name for name in loaded_skill_names if name.lower() != action.name.lower()
    ]
    console.print(f"Removed local skill: {action.name} ({action.scope}) -> {action.path}")
    return True


def _handle_skill_market_command(
    action: str,
    argument: str,
    console: Console,
    palette: UiPalette,
) -> bool:
    try:
        if action == "search":
            skills = search_market_skills(argument)
            if not skills:
                console.print(f"[{palette.muted}]No market skills found.[/]")
                return False
            for skill in skills:
                marker = " (installed)" if skill.installed else ""
                desc = f" - {skill.description}" if skill.description else ""
                uploaded = f" uploaded={skill.uploaded_at}" if skill.uploaded_at else ""
                console.print(f"{skill.name}{marker}{desc}{uploaded}")
            return False
        if action == "install":
            if not argument:
                console.print(f"[{palette.error}]Usage:[/] /skills install NAME")
                return False
            record = install_market_skill(argument)
            console.print(f"Installed skill: {record.name} -> {record.install_path}")
            return True
        if action == "uninstall":
            if not argument:
                console.print(f"[{palette.error}]Usage:[/] /skills uninstall NAME")
                return False
            removed = uninstall_market_skill(argument)
            console.print(f"Uninstalled skill: {removed}")
            return True
        if action == "installed":
            records = list_installed_skills()
            if not records:
                console.print(f"[{palette.muted}]No market-installed skills.[/]")
                return False
            for record in records:
                console.print(f"{record.name}\t{record.install_path}\tinstalled={record.installed_at}")
            return False
        if action == "update":
            records = list_installed_skills()
            if argument == "--all":
                if not records:
                    console.print(f"[{palette.muted}]No market-installed skills.[/]")
                    return False
                for record in records:
                    status, updated = update_market_skill(record.name)
                    console.print(f"{updated.name}: {status}")
                return True
            if not argument:
                console.print(f"[{palette.error}]Usage:[/] /skills update NAME|--all")
                return False
            status, updated = update_market_skill(argument)
            console.print(f"{updated.name}: {status}")
            return True
    except Exception as exc:
        console.print(f"[{palette.error}]Skill market error:[/] {exc}")
    return False
