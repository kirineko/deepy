from __future__ import annotations

import asyncio
from typing import Literal

from deepy.skills import find_skill, format_skills_for_terminal
from deepy.ui.modern.app_helpers import _installed_skill_entries
from deepy.ui.modern.app_patchable import resolve as _resolve
from deepy.ui.modern.app_state_proto import AppStateProto
from deepy.ui.modern.screens import (
    Choice,
    ChoiceScreen,
    InfoScreen,
    SkillManagementScreen,
    SkillScreenAction,
    SkillScreenEntry,
)
from deepy.ui.modern.skills_tui import (
    _format_installed_records,
    _format_market_skills,
    _market_detail_markdown,
    _market_skill_entry,
    _remove_local_skill_directory,
    _skill_detail_markdown,
)
from deepy.ui.modern.widgets import ErrorBlock, InfoBlock


class AppSkillsMixin(AppStateProto):
    async def _handle_skills_command(self, argument: str) -> bool:
        action, _, rest = argument.partition(" ")
        action = action.strip().lower()
        name = rest.strip()
        if not action:
            await self._open_skill_management()
            return True
        if action == "list":
            await self._append_block(InfoBlock(format_skills_for_terminal(_resolve("discover_skills")(self.project_root))))
            return True
        if action == "use":
            if not name:
                await self._append_block(ErrorBlock("Usage: /skills use NAME"))
                return True
            skill = find_skill(self.project_root, name)
            if skill is None:
                await self._append_block(ErrorBlock(f"Skill not found: {name}"))
                return True
            if skill.name not in self.controller.loaded_skill_names:
                self.controller.loaded_skill_names.append(skill.name)
            self._refresh_prompt_commands()
            await self._append_block(InfoBlock(f"Loaded skill: {skill.name}"))
            self._update_status(f"Loaded skill {skill.name}")
            return True
        if action == "show":
            if not name:
                await self._append_block(ErrorBlock("Usage: /skills show NAME"))
                return True
            skill = find_skill(self.project_root, name)
            if skill is None:
                await self._append_block(ErrorBlock(f"Skill not found: {name}"))
                return True
            self.push_screen(InfoScreen(f"Skill: {skill.name}", _skill_detail_markdown(skill)))
            return True
        if action == "search":
            await self._skills_search(name)
            return True
        if action == "install":
            await self._skills_install(name)
            return True
        if action == "uninstall":
            await self._skills_uninstall(name)
            return True
        if action == "installed":
            await self._skills_installed()
            return True
        if action == "update":
            await self._skills_update(name)
            return True
        return False


    async def _open_skill_management(self) -> None:
        screen = SkillManagementScreen(
            _installed_skill_entries(self.project_root),
            [],
            view="market",
            market_loading=True,
        )
        self.push_screen(screen)
        self.run_worker(self._refresh_skill_management_market(screen), name="skill-market-refresh")


    async def on_skill_management_action(self, event: SkillManagementScreen.ActionRequested) -> None:
        event.stop()
        action = event.action
        screen = event.screen
        if action.action == "refresh":
            screen.set_market_loading("Refreshing skill market...")
            self.run_worker(self._refresh_skill_management_market(screen), name="skill-market-refresh")
            return
        self.run_worker(self._handle_skill_screen_action(action, screen), name="skill-management-action")


    async def _handle_skill_screen_action(
        self,
        action: SkillScreenAction,
        screen: SkillManagementScreen,
    ) -> bool:
        if action.action == "use":
            skill = find_skill(self.project_root, action.name)
            if skill is None:
                await self._append_block(ErrorBlock(f"Skill not found: {action.name}"))
                return True
            if skill.name not in self.controller.loaded_skill_names:
                self.controller.loaded_skill_names.append(skill.name)
            self._refresh_prompt_commands()
            await self._append_block(InfoBlock(f"Loaded skill: {skill.name}"))
            self._update_status(f"Loaded skill {skill.name}")
            return True
        if action.action == "show":
            if action.source == "market" and find_skill(self.project_root, action.name) is None:
                entry = next((item for item in screen.market if item.name == action.name), None)
                if entry is not None:
                    await self.push_screen_wait(
                        InfoScreen(f"Market Skill: {entry.name}", _market_detail_markdown(entry))
                    )
                    return True
            skill = find_skill(self.project_root, action.name)
            if skill is None:
                await self._append_block(ErrorBlock(f"Skill not found: {action.name}"))
                return True
            await self.push_screen_wait(InfoScreen(f"Skill: {skill.name}", _skill_detail_markdown(skill)))
            return True
        if action.action == "install":
            await self._skills_install_from_screen(action.name, screen=screen)
            return True
        if action.action == "uninstall":
            await self._skills_uninstall_from_screen(action.name, screen=screen)
            return True
        if action.action == "update":
            await self._skills_update(action.name)
            return True
        return False


    async def _refresh_skill_management_market(self, screen: SkillManagementScreen) -> None:
        market_entries, market_error = await self._load_market_entries()
        try:
            screen.update_installed(_installed_skill_entries(self.project_root))
            screen.update_market(market_entries, market_error=market_error)
        except RuntimeError:
            return


    async def _load_market_entries(self) -> tuple[list[SkillScreenEntry], str]:
        try:
            skills = await asyncio.to_thread(_resolve("search_market_skills"), "")
        except Exception as exc:
            return [], f"Skill market error: {exc}"
        local_names = {
            skill.name for skill in _resolve("discover_skills")(self.project_root) if skill.scope in {"project", "user"}
        }
        return [_market_skill_entry(skill, local_names=local_names) for skill in skills], ""


    async def _skills_search(self, query: str) -> None:
        try:
            skills = await asyncio.to_thread(_resolve("search_market_skills"), query)
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Skill market error: {exc}"))
            return
        await self._append_block(InfoBlock(_format_market_skills(skills)))


    async def _skills_install(self, name: str) -> None:
        if not name:
            await self._append_block(ErrorBlock("Usage: /skills install NAME"))
            return
        scope = await self.push_screen_wait(
            ChoiceScreen(
                "Install skill",
                [
                    Choice("user", "user", "Install into ~/.agents/skills"),
                    Choice("project", "project", "Install into this project's .agents/skills"),
                ],
            )
        )
        install_scope: Literal["user", "project"]
        if scope == "user":
            install_scope = "user"
        elif scope == "project":
            install_scope = "project"
        else:
            self._update_status("Install cancelled")
            return
        try:
            record = await asyncio.to_thread(
                _resolve("install_market_skill"),
                name,
                scope=install_scope,
                project_root=self.project_root,
            )
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Skill market error: {exc}"))
            return
        self._refresh_prompt_commands()
        await self._append_block(InfoBlock(f"Installed skill: {record.name} ({record.scope}) -> {record.install_path}"))
        self._update_status(f"Installed {record.name}")


    async def _skills_install_from_screen(self, name: str, *, screen: SkillManagementScreen) -> None:
        if not name:
            self._update_status("Select a skill to install")
            return
        scope = await self.push_screen_wait(
            ChoiceScreen(
                "Install skill",
                [
                    Choice("user", "user", "Install into ~/.agents/skills"),
                    Choice("project", "project", "Install into this project's .agents/skills"),
                ],
            )
        )
        install_scope: Literal["user", "project"]
        if scope == "user":
            install_scope = "user"
        elif scope == "project":
            install_scope = "project"
        else:
            self._update_status("Install cancelled")
            return
        screen.set_operation_loading(f"Installing {name}...")
        try:
            record = await asyncio.to_thread(
                _resolve("install_market_skill"),
                name,
                scope=install_scope,
                project_root=self.project_root,
            )
        except Exception as exc:
            self._update_status(f"Skill install failed: {exc}")
            screen.clear_operation_loading()
            return
        self._refresh_prompt_commands()
        self._update_status(f"Installed {record.name} ({record.scope})")
        screen.update_installed(_installed_skill_entries(self.project_root))
        screen.set_market_loading("Refreshing skill market...")
        self.run_worker(self._refresh_skill_management_market(screen), name="skill-market-refresh")


    async def _skills_uninstall(self, name: str) -> None:
        if not name:
            await self._append_block(ErrorBlock("Usage: /skills uninstall NAME"))
            return
        skill = find_skill(self.project_root, name)
        if skill is not None and skill.scope == "builtin":
            await self._append_block(ErrorBlock(f"Built-in skill cannot be uninstalled: {skill.name}"))
            return
        record = next((item for item in _resolve("list_installed_skills")() if item.name.lower() == name.lower()), None)
        if record is None and skill is not None and skill.scope in {"project", "user"}:
            try:
                removed_path = await asyncio.to_thread(_remove_local_skill_directory, skill.path.parent)
            except Exception as exc:
                await self._append_block(ErrorBlock(f"Skill remove failed: {exc}"))
                return
            self.controller.loaded_skill_names = [
                skill_name for skill_name in self.controller.loaded_skill_names if skill_name.lower() != name.lower()
            ]
            self._refresh_prompt_commands()
            await self._append_block(InfoBlock(f"Removed local skill: {skill.name} ({skill.scope}) -> {removed_path}"))
            self._update_status(f"Removed {skill.name}")
            return
        try:
            removed = await asyncio.to_thread(_resolve("uninstall_market_skill"), name)
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Skill market error: {exc}"))
            return
        self.controller.loaded_skill_names = [
            skill_name for skill_name in self.controller.loaded_skill_names if skill_name.lower() != name.lower()
        ]
        self._refresh_prompt_commands()
        await self._append_block(InfoBlock(f"Uninstalled skill: {removed}"))
        self._update_status(f"Uninstalled {removed}")


    async def _skills_uninstall_from_screen(self, name: str, *, screen: SkillManagementScreen) -> None:
        if not name:
            self._update_status("Select a skill to uninstall")
            return
        skill = find_skill(self.project_root, name)
        if skill is not None and skill.scope == "builtin":
            self._update_status(f"Built-in skill cannot be uninstalled: {skill.name}")
            return
        record = next((item for item in _resolve("list_installed_skills")() if item.name.lower() == name.lower()), None)
        screen.set_operation_loading(f"Uninstalling {name}...")
        if record is None and skill is not None and skill.scope in {"project", "user"}:
            try:
                await asyncio.to_thread(_remove_local_skill_directory, skill.path.parent)
            except Exception as exc:
                self._update_status(f"Skill remove failed: {exc}")
                screen.clear_operation_loading()
                return
            removed_name = skill.name
        else:
            try:
                removed_name = await asyncio.to_thread(_resolve("uninstall_market_skill"), name)
            except Exception as exc:
                self._update_status(f"Skill uninstall failed: {exc}")
                screen.clear_operation_loading()
                return
        self.controller.loaded_skill_names = [
            skill_name for skill_name in self.controller.loaded_skill_names if skill_name.lower() != name.lower()
        ]
        self._refresh_prompt_commands()
        self._update_status(f"Uninstalled {removed_name}")
        screen.update_installed(_installed_skill_entries(self.project_root))
        screen.set_market_loading("Refreshing skill market...")
        self.run_worker(self._refresh_skill_management_market(screen), name="skill-market-refresh")


    async def _skills_installed(self) -> None:
        records = await asyncio.to_thread(_resolve("list_installed_skills"))
        await self._append_block(InfoBlock(_format_installed_records(records)))


    async def _skills_update(self, name: str) -> None:
        if not name:
            await self._append_block(ErrorBlock("Usage: /skills update NAME|--all"))
            return
        try:
            if name == "--all":
                records = await asyncio.to_thread(_resolve("list_installed_skills"))
                if not records:
                    await self._append_block(InfoBlock("No market-installed skills."))
                    return
                lines = []
                for record in records:
                    status, updated = await asyncio.to_thread(_resolve("update_market_skill"), record.name)
                    lines.append(f"{updated.name}: {status}")
                await self._append_block(InfoBlock("\n".join(lines)))
            else:
                status, updated = await asyncio.to_thread(_resolve("update_market_skill"), name)
                await self._append_block(InfoBlock(f"{updated.name}: {status}"))
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Skill market error: {exc}"))
            return
        self._refresh_prompt_commands()
        self._update_status("Skills updated")


