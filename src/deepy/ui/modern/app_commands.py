from __future__ import annotations

import asyncio

from deepy.config import (
    PROVIDER_CATALOG,
    UI_SETUP_OPTIONS,
    allows_custom_model_for_provider,
    default_base_url_for_provider,
    default_model_for_provider,
    is_supported_model_for_provider,
    is_supported_provider,
    is_valid_thinking_mode_for_provider,
    is_valid_ui_theme,
    load_settings,
    provider_info_for,
    ui_setup_from_selection,
    update_config_input_suggestions_enabled,
    update_config_model_settings,
    update_config_theme,
    update_config_textual_theme,
    update_config_ui_interface,
    update_config_view_mode,
    write_config,
)
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.multimodal import supports_image_input
from deepy.mcp import format_mcp_status
from deepy.session_cost import supports_session_cost
from deepy.sessions import DeepySession
from deepy.status import (
    BalanceStatus,
    build_status_report,
    format_balance_status,
    format_status_report,
)
from deepy.ui.modern.app_helpers import _tui_session_entry
from deepy.ui.modern.app_patchable import resolve as _resolve
from deepy.ui.modern.app_state_proto import AppStateProto
from deepy.ui.modern.background_tasks_tui import _format_tui_background_tasks_transcript
from deepy.ui.modern.commands import command_catalog_markdown
from deepy.ui.modern.render.status_format import (
    _format_tui_audit_mode,
    _format_tui_cache_status,
    _format_tui_ui_interface_label,
    _format_view_mode_confirmation,
    _model_list_text,
    _model_usage_text,
    _reset_choice_description,
    _reset_config_validation_error,
)
from deepy.ui.modern.screens import Choice, InfoScreen, ResetConfigResult, TextInputScreen
from deepy.ui.modern.state import reset_turn_buffers, set_busy, set_session_id
from deepy.ui.modern.theme import (
    TUI_TEXTUAL_THEME_OPTIONS,
    is_supported_textual_theme,
    textual_theme_for_ui_theme,
    textual_theme_option,
)
from deepy.ui.modern.widgets import ErrorBlock, InfoBlock, PromptTextArea, UserBlock
from deepy.ui.shared.local_command import (
    LocalCommandInput,
    build_synthetic_shell_transcript_items,
    shell_tool_result_json,
)
from deepy.ui.shared.model_picker import provider_api_key_reconfiguration_message, thinking_mode_choices
from deepy.usage import format_usage_line


class AppCommandsMixin(AppStateProto):
    async def _run_tui_command(self, name: str, argument: str = "") -> None:
        if name == "help":
            self.push_screen(InfoScreen("Deepy Modern UI Help", self._help_markdown()))
            return
        if name == "status":
            balance = (
                _resolve("fetch_deepseek_balance")(self.settings)
                if supports_session_cost(self.settings)
                else BalanceStatus(unavailable_reason="unsupported provider")
            )
            self.push_screen(
                InfoScreen(
                    "Deepy Modern UI Status",
                    self._status_markdown(balance=balance),
                )
            )
            return
        if name == "mcp":
            await self._append_block(InfoBlock(format_mcp_status(self.mcp_runtime.statuses)))
            return
        if name == "ps":
            await self._append_block(InfoBlock(_format_tui_background_tasks_transcript(self.background_tasks.list())))
            self._update_status("Background tasks listed")
            return
        if name == "stop":
            await self._stop_background_tasks(argument.strip())
            return
        if name == "new":
            await self._new_session()
            return
        if name == "sessions":
            await self._show_sessions()
            return
        if name == "resume":
            await self._resume_session(argument.strip() or None)
            return
        if name == "compact":
            await self._compact_session(argument.strip() or None)
            return
        if name == "theme":
            await self._theme_command(argument.strip())
            return
        if name == "ui":
            await self._ui_command(argument.strip())
            return
        if name == "model":
            await self._model_command(argument.strip())
            return
        if name == "view":
            await self._view_command(argument.strip())
            return
        if name == "input-suggestion":
            await self._input_suggestion_command(argument.strip())
            return
        if name == "reset":
            await self._reset_command()
            return
        if name == "skills":
            await self._handle_skills_command(argument)
            return


    def _help_markdown(self) -> str:
        return "\n\n".join(
            [
                command_catalog_markdown(),
                "## Keybindings\n"
                "- **Enter** - send prompt\n"
                "- **Ctrl+J** - insert newline\n"
                "- **Ctrl+P** - command palette\n"
                "- **Ctrl+O** - toggle side panel\n"
                "- **Shift+Tab** - cycle audit mode\n"
                "- **Alt+Up / Alt+Down** - move between transcript blocks\n"
                "- **Ctrl+Up / Ctrl+Down** - prompt history\n"
                "- **Ctrl+D twice** - exit",
                self._status_markdown(include_runtime=False),
            ]
        )


    def _status_markdown(
        self,
        *,
        include_runtime: bool = True,
        balance: BalanceStatus | None = None,
    ) -> str:
        report = build_status_report(
            self.project_root,
            self.settings,
            current_session_id=self.state.session_id,
            balance=balance,
        )
        session_cache = _format_tui_cache_status(_tui_session_entry(self.project_root, self.state.session_id))
        mcp_status = "enabled" if report.mcp.get("enabled") else "disabled"
        lines = [
            "# Status",
            "",
            "## Model",
            f"- Provider: `{report.provider}`",
            f"- Model: `{report.model}`",
            f"- Thinking: `{report.reasoning_mode}`",
            "",
            "## Runtime",
            f"- UI: `{self.settings.ui.interface}`",
            f"- Audit: `{_format_tui_audit_mode(self.audit_state, self.settings)}`",
            f"- View: `{self.settings.ui.view_mode}`",
            f"- Input suggestions: `{'enabled' if self.settings.ui.input_suggestions_enabled else 'disabled'}`",
            (
                f"- Theme: `{self.settings.ui.theme}` -> "
                f"`{textual_theme_for_ui_theme(self.settings.ui.theme, self.settings.ui.textual_theme)}`"
            ),
            "",
            "## Project",
            f"- Root: `{report.project_root}`",
            f"- Config: `{self.settings.path or 'unknown'}`",
            f"- Sessions: `{report.session_count}`",
            f"- Skills: `{report.skill_count}`",
            "",
            "## Session",
            f"- Active: `{self.state.session_id or 'new'}`",
            f"- Loaded skills: `{', '.join(self.controller.loaded_skill_names) or 'none'}`",
            f"- Session usage: `{format_usage_line(report.active_session_usage) if report.active_session_usage else 'unknown'}`",
            f"- Session cache: `{session_cache}`",
            f"- Project usage: `{format_usage_line(report.project_usage) if report.project_usage else 'unknown'}`",
            "",
            "## MCP",
            f"- State: `{mcp_status}`",
        ]
        if balance is not None:
            lines.extend(["", "## Balance", f"- Account: `{format_balance_status(balance)}`"])
        if include_runtime:
            runtime = format_status_report(report)
            if runtime:
                lines.extend(["", "## Details", "```text", runtime, "```"])
        return "\n".join(lines)


    async def _theme_command(self, argument: str) -> None:
        theme = argument
        if not theme:
            theme = await self._choose_inline(
                "Select theme",
                [
                    Choice(option.label, option.name, option.description)
                    for option in TUI_TEXTUAL_THEME_OPTIONS
                ],
            ) or ""
        if not theme:
            self._update_status("Theme unchanged")
            return
        theme_option = textual_theme_option(theme)
        if not is_valid_ui_theme(theme) and not is_supported_textual_theme(theme):
            choices = ", ".join(option.name for option in TUI_TEXTUAL_THEME_OPTIONS)
            await self._append_block(ErrorBlock(f"Usage: /theme <theme>\nChoices: {choices}"))
            return
        if self.settings.path is None:
            await self._append_block(ErrorBlock("Cannot persist theme: config path is unknown."))
            return
        if theme_option is not None and theme_option.shared_theme is not None:
            update_config_theme(self.settings.path, theme_option.shared_theme)
            saved_message = f"Saved UI theme: {theme_option.shared_theme}"
        elif is_valid_ui_theme(theme):
            update_config_theme(self.settings.path, theme)
            saved_message = f"Saved UI theme: {theme}"
        else:
            update_config_textual_theme(self.settings.path, theme)
            saved_message = f"Saved TUI theme: {theme}"
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        self.input_suggestions.set_enabled(self.settings.ui.input_suggestions_enabled)
        self.image_attachments.supports_image_input = supports_image_input(self.settings)
        self._clear_input_suggestion()
        self._apply_theme()
        await self._append_block(InfoBlock(saved_message))
        self._update_status(f"Theme {self.theme}")


    async def _ui_command(self, argument: str) -> None:
        interface = argument.strip().lower()
        if not interface:
            selected = await self._choose_inline(
                "Select UI",
                [
                    Choice("classic", "classic", "Rich/prompt-toolkit terminal UI"),
                    Choice("modern", "modern", "Textual terminal UI"),
                ],
            )
            interface = selected or ""
        if not interface:
            self._update_status("UI unchanged")
            return
        if interface not in {"classic", "modern"}:
            await self._append_block(ErrorBlock("Usage: /ui classic|modern"))
            return
        if self.settings.path is None:
            await self._append_block(ErrorBlock("Cannot persist UI: config path is unknown."))
            return
        update_config_ui_interface(self.settings.path, interface)
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        await self._append_block(InfoBlock(f"Saved UI: {_format_tui_ui_interface_label(interface)}"))
        self._update_status("Restart Deepy to enter the selected UI")


    async def _model_command(self, argument: str) -> None:
        try:
            parts = argument.split()
            provider: str | None = None
            model: str | None = None
            reasoning: str | None = None
            if not parts:
                provider = await self._choose_inline(
                    "Select provider",
                    [
                        Choice(item.id, item.id, item.description)
                        for item in PROVIDER_CATALOG
                    ],
                    restore_prompt_focus=False,
                )
                if not provider:
                    self._update_status("Model unchanged")
                    self.query_one("#prompt-input", PromptTextArea).focus()
                    return
                model = await self._choose_inline(
                    "Select model",
                    [
                        Choice(item.name, item.name, item.description)
                        for item in provider_info_for(provider).models
                    ],
                    restore_prompt_focus=False,
                )
                if not model:
                    self._update_status("Model unchanged")
                    self.query_one("#prompt-input", PromptTextArea).focus()
                    return
                reasoning = await self._choose_inline(
                    "Select thinking",
                    [Choice(value, value, label) for value, label in thinking_mode_choices(provider)],
                    restore_prompt_focus=False,
                )
                if not reasoning:
                    self._update_status("Model unchanged")
                    self.query_one("#prompt-input", PromptTextArea).focus()
                    return
            elif parts[0] == "list" and len(parts) == 1:
                await self._append_block(InfoBlock(_model_list_text()))
                return
            elif parts[0] == "provider" and len(parts) == 2:
                provider = parts[1]
            elif parts[0] == "set" and len(parts) in {2, 3}:
                provider = "deepseek"
                model = parts[1]
                reasoning = parts[2] if len(parts) == 3 else None
            elif parts[0] == "set" and len(parts) == 4:
                provider = parts[1]
                model = parts[2]
                reasoning = parts[3]
            elif parts[0] in {"reasoning", "thinking"} and len(parts) == 2:
                reasoning = parts[1]
            else:
                await self._append_block(ErrorBlock(_model_usage_text()))
                return
            active_provider = provider or self.settings.model.provider
            if provider is not None and not is_supported_provider(provider):
                await self._append_block(ErrorBlock(f"Invalid provider: {provider}\n{_model_usage_text()}"))
                return
            if model is not None and not is_supported_model_for_provider(model, active_provider):
                await self._append_block(ErrorBlock(f"Invalid model: {model}\n{_model_usage_text()}"))
                return
            if reasoning is not None and not is_valid_thinking_mode_for_provider(reasoning, active_provider):
                await self._append_block(ErrorBlock(f"Invalid thinking mode: {reasoning}\n{_model_usage_text()}"))
                return
            if self.settings.path is None:
                await self._append_block(ErrorBlock("Cannot persist model settings: config path is unknown."))
                return
            previous_provider = self.settings.model.provider
            update_config_model_settings(
                self.settings.path,
                provider=provider,
                model=model,
                reasoning_mode=reasoning,
            )
            self.settings = load_settings(self.settings.path)
            self.controller.settings = self.settings
            self.image_attachments.supports_image_input = supports_image_input(self.settings)
            await self._append_block(
                InfoBlock(
                    "Saved model: "
                    f"{self.settings.model.provider} {self.settings.model.name} "
                    f"- thinking: {self.settings.model.reasoning_mode}"
                )
            )
            self.query_one("#prompt-input", PromptTextArea).focus()
            if self.settings.model.provider != previous_provider:
                await self._append_block(
                    InfoBlock(provider_api_key_reconfiguration_message(self.settings.model.provider))
                )
            self._update_status("Model saved")
        finally:
            self.call_after_refresh(self._focus_prompt_input)


    def _focus_prompt_input(self) -> None:
        self.query_one("#prompt-input", PromptTextArea).focus()


    async def _view_command(self, argument: str) -> None:
        argument = argument.strip().lower()
        current = self.settings.ui.view_mode
        if not argument or argument == "toggle":
            selected = "full" if current == "concise" else "concise"
        elif argument in {"concise", "full"}:
            selected = argument
        else:
            await self._append_block(ErrorBlock("Usage: /view [toggle|concise|full]"))
            return
        if self.settings.path is None:
            await self._append_block(ErrorBlock("Cannot persist view mode: config path is unknown."))
            return
        update_config_view_mode(self.settings.path, selected)
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        self.image_attachments.supports_image_input = supports_image_input(self.settings)
        await self._append_block(InfoBlock(_format_view_mode_confirmation(self.settings.ui.view_mode)))
        self._update_status("View updated")


    async def _input_suggestion_command(self, argument: str) -> None:
        if argument:
            await self._append_block(ErrorBlock("Usage: /input-suggestion"))
            return
        if self.settings.path is None:
            await self._append_block(
                ErrorBlock("Cannot persist input suggestion setting: config path is unknown.")
            )
            return
        enabled = not self.settings.ui.input_suggestions_enabled
        update_config_input_suggestions_enabled(self.settings.path, enabled)
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        self.input_suggestions.set_enabled(self.settings.ui.input_suggestions_enabled)
        self.image_attachments.supports_image_input = supports_image_input(self.settings)
        self._clear_input_suggestion()
        await self._append_block(
            InfoBlock(
                "Input suggestions "
                f"{'enabled' if self.settings.ui.input_suggestions_enabled else 'disabled'}."
            )
        )
        self._update_status("Input suggestions toggled")


    async def _reset_command(self) -> None:
        if self.settings.path is None:
            await self._append_block(ErrorBlock("Cannot reset config: config path is unknown."))
            return
        previous_interface = "modern"
        previous_theme = self.settings.ui.theme
        result = await self._collect_reset_config()
        if result is None:
            await self._append_block(InfoBlock("Reset cancelled. Existing config left unchanged."))
            self._update_status("Reset cancelled")
            return
        error = _reset_config_validation_error(result)
        if error:
            await self._append_block(ErrorBlock(error))
            return
        try:
            if self.settings.path.exists():
                self.settings.path.unlink()
            write_config(
                self.settings.path,
                api_key=result.api_key,
                provider=result.provider,
                model=result.model,
                base_url=result.base_url,
                thinking_mode=result.thinking,
                theme=result.theme,
                interface=result.interface,
            )
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Config reset failed: {exc}"))
            return
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        self.image_attachments.supports_image_input = supports_image_input(self.settings)
        self._apply_theme()
        await self._append_block(InfoBlock(f"Wrote {self.settings.path}"))
        if result.interface != previous_interface or result.theme != previous_theme:
            await self._append_block(
                InfoBlock(
                    "UI selection changed to "
                    f"{_format_tui_ui_interface_label(result.interface)} {result.theme}. "
                    "Restart Deepy for the UI and theme selection to take effect."
                )
            )
        self._update_status("Config reset")


    async def _collect_reset_config(self) -> ResetConfigResult | None:
        provider = await self._choose_inline(
            "Reset: select provider",
            [
                Choice(item.id, item.id, item.description)
                for item in PROVIDER_CATALOG
            ],
            restore_prompt_focus=False,
        )
        if not provider:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        provider_info = provider_info_for(provider)
        guidance = [f"Provider selected: {provider}"]
        if provider_info.api_key_url:
            guidance.append(f"Create an API key at {provider_info.api_key_url}")
        await self._append_block(InfoBlock("\n".join(guidance)))
        api_key = await self._prompt_reset_value(
            "Reset: API key",
            placeholder=f"API key for {provider}",
            password=True,
        )
        if api_key is None:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        model = await self._choose_reset_model(provider)
        if model is None:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        base_default = (
            self.settings.model.base_url
            if self.settings.model.provider == provider
            else default_base_url_for_provider(provider)
        )
        base_url = await self._prompt_reset_value(
            "Reset: base URL",
            value=base_default,
            placeholder=default_base_url_for_provider(provider),
        )
        if base_url is None:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        thinking_default = (
            self.settings.model.reasoning_mode
            if (
                self.settings.model.provider == provider
                and is_valid_thinking_mode_for_provider(self.settings.model.reasoning_mode, provider)
            )
            else provider_info.default_thinking_mode
        )
        thinking = await self._choose_inline(
            "Reset: select thinking",
            [
                Choice(value, value, _reset_choice_description(label, default=value == thinking_default))
                for value, label in thinking_mode_choices(provider)
            ],
            restore_prompt_focus=False,
        )
        if not thinking:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        ui_selection = await self._choose_inline(
            "Reset: select UI",
            [
                Choice(
                    f"{number}. {_format_tui_ui_interface_label(interface)} {theme}",
                    number,
                    _reset_choice_description("Default" if interface == "classic" and theme == "dark" else ""),
                )
                for number, interface, theme in UI_SETUP_OPTIONS
            ],
            restore_prompt_focus=False,
        )
        if not ui_selection:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        interface, theme = ui_setup_from_selection(
            ui_selection,
            default_interface=self.settings.ui.interface,
            default_theme=self.settings.ui.theme,
        )
        self.call_after_refresh(self._focus_prompt_input)
        return ResetConfigResult(
            api_key=api_key,
            provider=provider,
            model=model,
            base_url=base_url,
            thinking=thinking,
            interface=interface,
            theme=theme,
        )


    async def _choose_reset_model(self, provider: str) -> str | None:
        provider_info = provider_info_for(provider)
        model_default = (
            self.settings.model.name
            if (
                self.settings.model.provider == provider
                and is_supported_model_for_provider(self.settings.model.name, provider)
            )
            else default_model_for_provider(provider)
        )
        choices = [
            Choice(model.name, model.name, _reset_choice_description(model.description, default=model.name == model_default))
            for model in provider_info.models
        ]
        custom_value = "__custom_model__"
        if allows_custom_model_for_provider(provider):
            choices.append(
                Choice(
                    "Custom model",
                    custom_value,
                    "Paste any model name copied from the OpenRouter models page",
                )
            )
        selected = await self._choose_inline(
            "Reset: select model",
            choices,
            restore_prompt_focus=False,
        )
        if not selected:
            return None
        if selected != custom_value:
            return selected
        return await self._prompt_reset_value(
            "Reset: custom model",
            value=self.settings.model.name if self.settings.model.provider == provider else "",
            placeholder="provider/model-name",
        )


    async def _prompt_reset_value(
        self,
        title: str,
        *,
        value: str = "",
        placeholder: str = "",
        password: bool = False,
    ) -> str | None:
        return await self.push_screen_wait(
            TextInputScreen(
                title,
                value=value,
                placeholder=placeholder,
                password=password,
            )
        )


    async def _handle_local_command(self, command_input: LocalCommandInput) -> None:
        if not command_input.command:
            await self._append_block(ErrorBlock("Usage: !<command>"))
            return
        self.controller.add_prompt_history(command_input.raw_text)
        await self._append_block(UserBlock(command_input.raw_text))
        self.state = set_busy(reset_turn_buffers(self.state), True, "Running local command")
        self._update_status("Running local command")
        self._local_command_sequence += 1
        call_id = f"deepy-local-command-{self._local_command_sequence}"
        self.run_worker(self._run_local_command(command_input, call_id=call_id), exclusive=False)


    async def _run_local_command(self, command_input: LocalCommandInput, *, call_id: str) -> None:
        try:
            result = await asyncio.to_thread(
                _resolve("run_local_command"),
                command_input.command,
                cwd=self.project_root,
                should_interrupt=lambda: self.state.interrupt_requested,
            )
            tool_output = shell_tool_result_json(result, output=result.display_output)
            await self._handle_stream_event(
                DeepyStreamEvent(
                    kind="tool_output",
                    text=tool_output,
                    payload={"call_id": call_id},
                )
            )
            session = (
                DeepySession.open(self.project_root, self.state.session_id)
                if self.state.session_id
                else DeepySession.create(self.project_root)
            )
            await session.add_items(
                build_synthetic_shell_transcript_items(command_input.raw_text, result, call_id=call_id)
            )
            self.state = set_session_id(self.state, session.session_id)
            self.state = set_busy(reset_turn_buffers(self.state), False, "Idle")
            self._update_status("Idle")
        except Exception as exc:
            self.state = set_busy(reset_turn_buffers(self.state), False, "Error")
            await self._append_block(ErrorBlock(f"Local command failed: {exc}"))
            self._update_status("Error")


