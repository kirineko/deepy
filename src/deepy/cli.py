from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Sequence

import tomli_w

from . import __version__
from .config import (
    PROVIDER_CATALOG,
    Settings,
    allows_custom_model_for_provider,
    default_base_url_for_provider,
    default_model_for_provider,
    default_thinking_mode_for_provider,
    is_supported_provider,
    is_valid_thinking_mode_for_provider,
    load_settings,
    provider_info_for,
    settings_to_toml_dict,
    thinking_modes_for_provider,
    ui_setup_from_selection,
    ui_setup_number,
    ui_theme_from_selection,
    ui_theme_number,
    update_config_theme,
    update_config_ui_choice,
    write_config,
)
from .config.settings import DEFAULT_UI_THEME, UI_THEMES
from .errors import format_error_display
from .llm.cache_context import format_cache_usage
from .llm.multimodal import redact_image_data_urls
from .llm.provider import build_provider_bundle
from .llm.runner import DEFAULT_MAX_TURNS, run_prompt_once
from .sessions import DeepySession, list_session_entries
from .skills import discover_skills, find_skill, format_skills_for_terminal, read_skill_body
from .status import build_status_report, format_status_report, status_report_to_dict
from .usage import TokenUsage, format_usage_line, usage_from_run_result
from .ui.classic import run_interactive
from .ui.shared.render.styles import resolve_ui_palette
from .utils import json as json_utils


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deepy",
        description="Deepy - Vibe coding for DeepSeek models in your terminal.",
    )
    parser.add_argument("--version", action="version", version=f"Deepy {__version__}")
    parser.add_argument("--config", type=Path, help="Path to config.toml.")

    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser("config", help="Inspect local Deepy config.")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)
    show_parser = config_sub.add_parser("show", help="Print resolved TOML config.")
    show_parser.add_argument("--show-secret", action="store_true", help="Show API key.")
    show_parser.add_argument("--json", action="store_true", help="Print JSON instead of TOML.")
    init_parser = config_sub.add_parser("init", help="Create a TOML config file.")
    init_parser.add_argument("--api-key", help="Provider API key.")
    init_parser.add_argument("--provider", default="deepseek", help="Provider: deepseek, openrouter, or xiaomi.")
    init_parser.add_argument("--model", help="Model name.")
    init_parser.add_argument("--base-url", help="OpenAI-compatible base URL.")
    init_parser.add_argument("--thinking", help="Thinking mode for the provider.")
    init_parser.add_argument("--theme", default=DEFAULT_UI_THEME, help="UI theme: dark or light.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing config.")
    setup_parser = config_sub.add_parser("setup", help="Interactively configure Deepy.")
    setup_parser.add_argument("--force", action="store_true", help="Overwrite existing config.")
    config_sub.add_parser("reset", help="Delete local config and run interactive setup again.")
    theme_parser = config_sub.add_parser("theme", help="Show or update terminal UI theme.")
    theme_parser.add_argument("theme", nargs="?", help="Theme to save: dark or light.")

    doctor_parser = subparsers.add_parser("doctor", help="Validate local Deepy setup.")
    doctor_parser.add_argument("--json", action="store_true", help="Print JSON diagnostics.")
    doctor_parser.add_argument("--live", action="store_true", help="Send one minimal live DeepSeek request.")

    run_parser = subparsers.add_parser("run", help="Run a single non-interactive prompt.")
    run_parser.add_argument("prompt", nargs="+", help="Prompt text to send to Deepy.")
    run_parser.add_argument(
        "--max-turns",
        type=int,
        default=DEFAULT_MAX_TURNS,
        help="Maximum agent turns.",
    )
    run_parser.add_argument("--session", help="Resume an existing session id.")
    run_parser.add_argument("--skill", action="append", default=[], help="Load a skill by name.")

    subparsers.add_parser("tui", help="Start the Modern UI.")

    sessions_parser = subparsers.add_parser("sessions", help="Inspect project sessions.")
    sessions_sub = sessions_parser.add_subparsers(dest="sessions_command", required=True)
    sessions_sub.add_parser("list", help="List sessions for the current project.")
    sessions_show = sessions_sub.add_parser("show", help="Print session items as JSON.")
    sessions_show.add_argument("session_id", help="Session id.")

    skills_parser = subparsers.add_parser("skills", help="Inspect available skills.")
    skills_sub = skills_parser.add_subparsers(dest="skills_command", required=True)
    skills_sub.add_parser("list", help="List user and project skills.")
    skills_show = skills_sub.add_parser("show", help="Print a skill document.")
    skills_show.add_argument("name", help="Skill name.")

    status_parser = subparsers.add_parser("status", help="Print current Deepy project status.")
    status_parser.add_argument("--json", action="store_true", help="Print JSON status.")

    return parser


def _cmd_config_show(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    data = settings_to_toml_dict(settings, reveal_secret=args.show_secret)
    if args.json:
        print(json_utils.dumps_pretty(data))
    else:
        print(tomli_w.dumps(data), end="")
    return 0


def _cmd_config_init(args: argparse.Namespace) -> int:
    config_path = args.config.expanduser() if args.config else Path.home() / ".deepy" / "config.toml"
    if config_path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    if config_path.exists() and not args.force:
        print(f"Config already exists: {config_path}", file=sys.stderr)
        return 1
    _write_config(
        config_path,
        api_key=args.api_key or "",
        provider=args.provider,
        model=args.model or default_model_for_provider(args.provider),
        base_url=args.base_url,
        thinking_mode=args.thinking,
        theme=args.theme,
        interface="classic",
    )
    print(f"Wrote {config_path}")
    return 0


def _cmd_config_setup(args: argparse.Namespace) -> int:
    config_path = args.config.expanduser() if args.config else Path.home() / ".deepy" / "config.toml"
    if config_path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    previous_text = config_path.read_text(encoding="utf-8") if config_path.exists() else None
    try:
        _run_config_setup(config_path)
    except (KeyboardInterrupt, EOFError, StopIteration):
        print(_setup_cancelled_message(previous_text), file=sys.stderr)
        return 1
    print(f"Wrote {config_path}")
    return 0


def _run_config_setup(config_path: Path) -> None:
    if config_path.exists():
        existing = load_settings(config_path)
    else:
        existing = Settings(path=config_path)

    provider = _prompt_provider_value(default=existing.model.provider)
    provider_info = provider_info_for(provider)
    print(f"{provider_info.label} provider selected.")
    if provider_info.api_key_url:
        print(f"Create an API key at {provider_info.api_key_url}")
    api_key = _prompt_config_value("API key", default=existing.model.api_key or "", is_password=True)
    model = _prompt_model_value(provider, default=existing.model.name)
    base_default = (
        existing.model.base_url
        if existing.model.provider == provider
        else default_base_url_for_provider(provider)
    )
    base_url = _prompt_config_value("Base URL", default=base_default)
    thinking_mode = _prompt_thinking_mode_value(provider, default=existing.model.reasoning_mode)
    interface, theme = _prompt_ui_choice_value(
        default_interface=existing.ui.interface,
        default_theme=existing.ui.theme,
    )
    _write_config(
        config_path,
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        thinking_mode=thinking_mode,
        theme=theme,
        interface=interface,
    )


def _cmd_config_reset(args: argparse.Namespace) -> int:
    config_path = args.config.expanduser() if args.config else Path.home() / ".deepy" / "config.toml"
    if config_path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    previous_text = config_path.read_text(encoding="utf-8") if config_path.exists() else None
    if config_path.exists():
        config_path.unlink()
        print(f"Removed {config_path}")
    else:
        print(f"No existing config at {config_path}")
    print("Starting Deepy configuration setup...")
    try:
        _run_config_setup(config_path)
    except (KeyboardInterrupt, EOFError, StopIteration):
        _restore_config_after_failed_setup(config_path, previous_text)
        print(_setup_cancelled_message(previous_text), file=sys.stderr)
        return 1
    print(f"Wrote {config_path}")
    return 0


def _setup_cancelled_message(previous_text: str | None) -> str:
    if previous_text is None:
        return "Configuration setup cancelled. No config was written."
    return "Configuration setup cancelled. Existing config was left unchanged."


def _restore_config_after_failed_setup(config_path: Path, previous_text: str | None) -> None:
    if previous_text is None:
        try:
            config_path.unlink()
        except FileNotFoundError:
            pass
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(previous_text, encoding="utf-8")
    try:
        config_path.chmod(0o600)
    except OSError:
        pass


def _prompt_config_value(label: str, *, default: str, is_password: bool = False) -> str:
    from prompt_toolkit import PromptSession

    prompt = f"{label}"
    if default and not is_password:
        prompt += f" [{default}]"
    prompt += ": "
    value = PromptSession().prompt(prompt, default="" if is_password else default, is_password=is_password)
    value = value.strip()
    return value or default


def _prompt_provider_value(*, default: str = "deepseek") -> str:
    print("Provider:")
    for index, provider in enumerate(PROVIDER_CATALOG, 1):
        print(f"{index}. {provider.id}  {provider.description}")
    value = _prompt_config_value("Provider number or name", default=_provider_number(default))
    return _provider_from_selection(value, default=default)


def _provider_number(provider: str) -> str:
    for index, item in enumerate(PROVIDER_CATALOG, 1):
        if item.id == provider:
            return str(index)
    return "1"


def _provider_from_selection(value: str, *, default: str = "deepseek") -> str:
    normalized = value.strip().lower()
    by_number = {str(index): item.id for index, item in enumerate(PROVIDER_CATALOG, 1)}
    if normalized in by_number:
        return by_number[normalized]
    if is_supported_provider(normalized):
        return normalized
    return default if is_supported_provider(default) else "deepseek"


def _prompt_model_value(provider: str, *, default: str) -> str:
    provider_info = provider_info_for(provider)
    print("Model:")
    for index, model in enumerate(provider_info.models, 1):
        print(f"{index}. {model.name}  {model.description}")
    if allows_custom_model_for_provider(provider):
        print("Or paste any model name copied from the OpenRouter models page.")
    default_value = default if default in {model.name for model in provider_info.models} else provider_info.default_model
    value = _prompt_config_value("Model number or name", default=_model_number(provider, default_value))
    return _model_from_selection(provider, value, default=default_value)


def _model_number(provider: str, model: str) -> str:
    for index, item in enumerate(provider_info_for(provider).models, 1):
        if item.name == model:
            return str(index)
    return "1"


def _model_from_selection(provider: str, value: str, *, default: str) -> str:
    normalized = value.strip()
    models = provider_info_for(provider).models
    by_number = {str(index): item.name for index, item in enumerate(models, 1)}
    if normalized in by_number:
        return by_number[normalized]
    if normalized in {item.name for item in models}:
        return normalized
    if allows_custom_model_for_provider(provider) and normalized:
        return normalized
    return default_model_for_provider(provider) if not default else default


def _prompt_thinking_mode_value(provider: str, *, default: str) -> str:
    if provider == "openrouter":
        return _prompt_openrouter_thinking_mode(default=default)
    modes = thinking_modes_for_provider(provider)
    print("Thinking:")
    for index, mode in enumerate(modes, 1):
        print(f"{index}. {mode}")
    default_value = default if is_valid_thinking_mode_for_provider(default, provider) else default_thinking_mode_for_provider(provider)
    value = _prompt_config_value("Thinking number or name", default=_thinking_mode_number(provider, default_value))
    return _thinking_mode_from_selection(provider, value, default=default_value)


def _thinking_mode_number(provider: str, mode: str) -> str:
    for index, item in enumerate(thinking_modes_for_provider(provider), 1):
        if item == mode:
            return str(index)
    return "1"


def _prompt_openrouter_thinking_mode(*, default: str) -> str:
    current_enabled = default not in {"none", "disabled"}
    print("Thinking:")
    print("1. enabled  Reasoning enabled")
    print("2. disabled Reasoning disabled")
    state_default = "1" if current_enabled else "2"
    state_value = _prompt_config_value("Thinking number or name", default=state_default)
    state = _openrouter_thinking_state_from_selection(state_value, default="enabled" if current_enabled else "disabled")
    if state == "disabled":
        return "none"
    print("Reasoning effort:")
    print("1. default  Use the model default reasoning strength")
    for index, effort in enumerate(("xhigh", "high", "medium", "low", "minimal"), 2):
        print(f"{index}. {effort}")
    effort_default = _openrouter_effort_number(default)
    effort_value = _prompt_config_value("Reasoning effort number or name", default=effort_default)
    return _openrouter_effort_from_selection(effort_value, default=default)


def _openrouter_thinking_state_from_selection(value: str, *, default: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"1", "enabled", "enable", "on", "true", "yes"}:
        return "enabled"
    if normalized in {"2", "disabled", "disable", "off", "false", "no", "none"}:
        return "disabled"
    return default


def _openrouter_effort_number(mode: str) -> str:
    return {
        "enabled": "1",
        "xhigh": "2",
        "high": "3",
        "medium": "4",
        "low": "5",
        "minimal": "6",
    }.get(mode, "1")


def _openrouter_effort_from_selection(value: str, *, default: str) -> str:
    normalized = value.strip().lower()
    by_number = {
        "1": "enabled",
        "2": "xhigh",
        "3": "high",
        "4": "medium",
        "5": "low",
        "6": "minimal",
    }
    if normalized in by_number:
        return by_number[normalized]
    if normalized in {"default", "enabled"}:
        return "enabled"
    if normalized in {"xhigh", "high", "medium", "low", "minimal"}:
        return normalized
    return default if default in {"enabled", "xhigh", "high", "medium", "low", "minimal"} else "enabled"


def _thinking_mode_from_selection(provider: str, value: str, *, default: str) -> str:
    normalized = value.strip().lower()
    modes = thinking_modes_for_provider(provider)
    by_number = {str(index): mode for index, mode in enumerate(modes, 1)}
    if normalized in by_number:
        return by_number[normalized]
    if normalized in modes:
        return normalized
    return default


def _prompt_theme_value(*, default: str = DEFAULT_UI_THEME) -> str:
    print("UI theme:")
    print("1. dark  Optimized for dark terminal backgrounds")
    print("2. light Optimized for light terminal backgrounds")
    value = _prompt_config_value("UI theme number", default=ui_theme_number(default))
    return ui_theme_from_selection(value, default=default)


def _prompt_ui_choice_value(
    *,
    default_interface: str = "classic",
    default_theme: str = DEFAULT_UI_THEME,
) -> tuple[str, str]:
    print("UI:")
    print("1. Classic UI + dark theme  Default terminal UI")
    print("2. Classic UI + light theme")
    print("3. Modern UI + dark theme   Textual UI")
    print("4. Modern UI + light theme  Textual UI")
    value = _prompt_config_value(
        "UI number",
        default=ui_setup_number(default_interface, default_theme),
    )
    return ui_setup_from_selection(
        value,
        default_interface=default_interface,
        default_theme=default_theme,
    )


def _write_config(
    config_path: Path,
    *,
    api_key: str,
    provider: str,
    model: str,
    base_url: str | None,
    theme: str,
    interface: str,
    thinking_mode: str | None,
) -> None:
    write_config(
        config_path,
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        theme=theme,
        interface=interface,
        thinking_mode=thinking_mode,
    )


def _cmd_config_theme(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    if args.theme is None:
        palette = resolve_ui_palette(settings.ui.theme)
        print(f"saved: {settings.ui.theme}")
        print(f"resolved: {palette.name}")
        return 0
    if args.theme not in UI_THEMES:
        print("Invalid theme. Usage: deepy config theme [dark|light]", file=sys.stderr)
        return 1
    config_path = settings.path or (args.config.expanduser() if args.config else Path.home() / ".deepy" / "config.toml")
    update_config_theme(config_path, args.theme)
    print(f"Saved UI theme: {args.theme}")
    return 0


def _doctor(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    settings = load_settings(args.config)
    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    check("config", True, str(settings.path))
    check("config_permissions", *_config_permissions_check(settings.path))
    check(
        "api_key",
        bool(settings.model.api_key),
        "configured" if settings.model.api_key else "missing; run `deepy config setup`",
    )
    check("model", bool(settings.model.name), settings.model.name)
    check("provider", bool(settings.model.provider), settings.model.provider)
    check("base_url", bool(settings.model.base_url), settings.model.base_url)
    check(
        "context_window",
        settings.context.window_tokens >= 1_000_000,
        str(settings.context.window_tokens),
    )
    check(
        "compact_threshold",
        settings.context.resolved_compact_threshold
        == int(settings.context.window_tokens * 0.8 + 0.999999)
        or settings.context.resolved_compact_threshold > 0,
        str(settings.context.resolved_compact_threshold),
    )
    check(
        "reserved_context",
        settings.context.reserved_context_tokens > 0,
        str(settings.context.reserved_context_tokens),
    )

    try:
        build_provider_bundle(settings)
    except Exception as exc:
        check("openai_agents_provider", False, str(exc))
    else:
        check("openai_agents_provider", True, "OpenAIChatCompletionsModel ready")

    ok = all(bool(item["ok"]) for item in checks)
    return 0 if ok else 1, {
        "ok": ok,
        "checks": checks,
            "thinking": {
                "provider": settings.model.provider,
                "enabled": settings.model.thinking_enabled,
                "reasoning_effort": settings.model.reasoning_effort,
                "reasoning_mode": settings.model.reasoning_mode,
        },
    }


async def _doctor_live(settings: Settings) -> dict[str, Any]:
    from agents import Agent, RunConfig, Runner

    provider = build_provider_bundle(settings)
    agent = Agent(
        name="Deepy Doctor",
        instructions="Reply with OK.",
        model=provider.model,
        model_settings=provider.model_settings,
        tools=[],
    )
    result = await Runner.run(
        agent,
        "Reply with OK.",
        max_turns=1,
        run_config=RunConfig(
            workflow_name="Deepy Doctor",
            trace_include_sensitive_data=False,
            reasoning_item_id_policy="omit",
        ),
    )
    output = getattr(result, "final_output", "")
    usage = usage_from_run_result(result)
    return {
        "ok": True,
        "provider": settings.model.provider,
        "model": settings.model.name,
        "base_url": settings.model.base_url,
        "api_key": "configured",
        "response_summary": str(output).strip()[:200],
        "usage": usage.to_dict(),
    }


def _config_permissions_check(path: Path | None) -> tuple[bool, str]:
    if path is None or not path.exists():
        return False, "missing"
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        return False, f"{mode:o}; expected private permissions like 600"
    return True, f"{mode:o}"


def _cmd_doctor(args: argparse.Namespace) -> int:
    code, report = _doctor(args)
    if args.live:
        settings = load_settings(args.config)
        if code != 0:
            report["live"] = {"ok": False, "error": "local doctor checks failed"}
        else:
            try:
                report["live"] = asyncio.run(_doctor_live(settings))
            except Exception as exc:
                report["live"] = {"ok": False, "error": format_error_display(exc)}
                code = 1
    if args.json:
        print(json_utils.dumps_pretty(report))
        return code
    for item in report["checks"]:
        status = "ok" if item["ok"] else "fail"
        print(f"{status:4} {item['name']}: {item['detail']}")
    thinking = report["thinking"]
    print(f"info provider: {thinking['provider']}")
    print(f"info thinking: mode={thinking['reasoning_mode']}")
    live = report.get("live")
    if isinstance(live, dict):
        if live.get("ok"):
            usage = live.get("usage")
            print(
                    "ok   live: "
                    f"provider={live.get('provider')} model={live.get('model')} base_url={live.get('base_url')} "
                f"response={live.get('response_summary')!r} "
                f"{format_usage_line(usage if isinstance(usage, dict) else TokenUsage())}"
            )
        else:
            print(f"fail live: {live.get('error')}")
    return code


def _cmd_run(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    prompt = " ".join(args.prompt)

    def emit(delta: str) -> None:
        print(delta, end="", flush=True)

    try:
        summary = asyncio.run(
            run_prompt_once(
                prompt,
                settings=settings,
                emit=emit,
                max_turns=args.max_turns,
                session_id=args.session,
                skill_names=args.skill,
            )
        )
    except Exception as exc:
        print(f"deepy run failed: {format_error_display(exc)}", file=sys.stderr)
        return 1
    if summary.output and not summary.output.endswith("\n"):
        print()
    return 0 if summary.complete else 1


def _cmd_sessions(args: argparse.Namespace) -> int:
    if args.sessions_command == "list":
        entries = list_session_entries(Path.cwd())
        if not entries:
            print("No sessions found.")
            return 0
        for entry in entries:
            print(
                f"{entry.id}\tupdated={entry.updated_at}\thistory_estimate={entry.active_tokens}\t"
                f"{format_usage_line(entry.usage)}\tcache={_format_session_cache(entry)}"
            )
        return 0
    if args.sessions_command == "show":
        session = DeepySession.open(Path.cwd(), args.session_id)
        items = asyncio.run(session.get_items())
        entry = next(
            (item for item in list_session_entries(Path.cwd()) if item.id == args.session_id),
            None,
        )
        print(
            json_utils.dumps_pretty(
                {
                    "session_id": args.session_id,
                    "usage": entry.usage if entry is not None else None,
                    "cache_prefix_generation": entry.cache_prefix_generation
                    if entry is not None
                    else 0,
                    "cache_break_reason": entry.cache_break_reason if entry is not None else None,
                    "cache_usage": entry.cache_usage if entry is not None else None,
                    "items": redact_image_data_urls(items),
                }
            )
        )
        return 0
    return 1


def _format_session_cache(entry: Any) -> str:
    parts = []
    generation = getattr(entry, "cache_prefix_generation", 0)
    if generation:
        parts.append(f"gen {generation}")
    usage = format_cache_usage(getattr(entry, "cache_usage", None))
    if usage != "unknown":
        parts.append(usage)
    reason = getattr(entry, "cache_break_reason", None)
    if reason:
        parts.append(f"break {reason}")
    return " · ".join(parts) if parts else "unknown"


def _cmd_skills(args: argparse.Namespace) -> int:
    if args.skills_command == "list":
        print(format_skills_for_terminal(discover_skills(Path.cwd())))
        return 0
    if args.skills_command == "show":
        skill = find_skill(Path.cwd(), args.name)
        if skill is None:
            print(f"Skill not found: {args.name}", file=sys.stderr)
            return 1
        print(read_skill_body(skill))
        return 0
    return 1


def _cmd_status(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    report = build_status_report(Path.cwd(), settings)
    if args.json:
        print(json_utils.dumps_pretty(status_report_to_dict(report)))
    else:
        print(format_status_report(report))
    return 0


def _ensure_interactive_settings(args: argparse.Namespace) -> Settings:
    settings = load_settings(args.config)
    if not settings.model.api_key:
        print("Deepy needs a provider API key before starting interactive mode.")
        setup_args = argparse.Namespace(config=args.config, force=True)
        if _cmd_config_setup(setup_args) != 0:
            raise SystemExit(1)
        settings = load_settings(args.config)
    if settings.path is not None and not settings.ui.theme_configured:
        interface, theme = _prompt_ui_choice_value(
            default_interface=settings.ui.interface,
            default_theme=settings.ui.theme,
        )
        update_config_ui_choice(settings.path, interface=interface, theme=theme)
        settings = load_settings(args.config)
    return settings


def _cmd_tui(args: argparse.Namespace) -> int:
    if not sys.stdin.isatty():
        print("Modern UI requires a TTY; use `deepy run` for non-interactive prompts.", file=sys.stderr)
        return 1
    from deepy.ui.modern import run_tui

    return run_tui(_ensure_interactive_settings(args), project_root=Path.cwd())


def _cmd_interactive(args: argparse.Namespace) -> int:
    settings = _ensure_interactive_settings(args)
    if settings.ui.interface == "modern":
        if not sys.stdin.isatty():
            raise RuntimeError("Modern UI requires a TTY.")
        from deepy.ui.modern import run_tui

        return run_tui(settings, project_root=Path.cwd())
    return run_interactive(settings)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "config":
        if args.config_command == "show":
            return _cmd_config_show(args)
        if args.config_command == "init":
            return _cmd_config_init(args)
        if args.config_command == "setup":
            return _cmd_config_setup(args)
        if args.config_command == "reset":
            return _cmd_config_reset(args)
        if args.config_command == "theme":
            return _cmd_config_theme(args)
    if args.command == "doctor":
        return _cmd_doctor(args)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "sessions":
        return _cmd_sessions(args)
    if args.command == "skills":
        return _cmd_skills(args)
    if args.command == "status":
        return _cmd_status(args)
    if args.command == "tui":
        return _cmd_tui(args)

    if not sys.stdin.isatty():
        parser.error("interactive mode requires a TTY; use `deepy doctor` or `deepy config show`.")
    return _cmd_interactive(args)


if __name__ == "__main__":
    raise SystemExit(main())
