from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Sequence

import tomli_w

from . import __version__
from .config import Settings, load_settings, settings_to_toml_dict
from .config.settings import DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_WEB_SEARCH_SEARXNG_URL
from .errors import format_error_display
from .llm.provider import build_provider_bundle
from .llm.runner import DEFAULT_MAX_TURNS, run_prompt_once
from .sessions import DeepyJsonlSession, list_session_entries
from .skills import discover_skills, find_skill, format_skills_for_terminal, read_skill_body
from .status import build_status_report, format_status_report, status_report_to_dict
from .usage import TokenUsage, format_usage_line, usage_from_run_result
from .ui import run_interactive
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
    init_parser.add_argument("--api-key", help="DeepSeek API key.")
    init_parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name.")
    init_parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI-compatible base URL.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing config.")
    setup_parser = config_sub.add_parser("setup", help="Interactively configure Deepy.")
    setup_parser.add_argument("--force", action="store_true", help="Overwrite existing config.")

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
        model=args.model,
        base_url=args.base_url,
    )
    print(f"Wrote {config_path}")
    return 0


def _cmd_config_setup(args: argparse.Namespace) -> int:
    config_path = args.config.expanduser() if args.config else Path.home() / ".deepy" / "config.toml"
    if config_path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    if config_path.exists() and not args.force:
        existing = load_settings(config_path)
    else:
        existing = Settings(path=config_path)

    print("DeepSeek API keys: https://platform.deepseek.com/api_keys")
    api_key = _prompt_config_value("API key", default=existing.model.api_key or "", is_password=True)
    model = _prompt_config_value("Model", default=existing.model.name)
    base_url = _prompt_config_value("Base URL", default=existing.model.base_url)
    _write_config(config_path, api_key=api_key, model=model, base_url=base_url)
    print(f"Wrote {config_path}")
    return 0


def _prompt_config_value(label: str, *, default: str, is_password: bool = False) -> str:
    from prompt_toolkit import PromptSession

    prompt = f"{label}"
    if default and not is_password:
        prompt += f" [{default}]"
    prompt += ": "
    value = PromptSession().prompt(prompt, default="" if is_password else default, is_password=is_password)
    value = value.strip()
    return value or default


def _write_config(config_path: Path, *, api_key: str, model: str, base_url: str) -> None:
    payload = {
        "model": {
            "name": model,
            "base_url": base_url,
            "api_key": api_key,
            "thinking": True,
            "reasoning_effort": "max",
        },
        "context": {
            "window_tokens": 1_048_576,
            "compact_trigger_ratio": 0.8,
            "compact_prompt_token_threshold": 838_861,
        },
        "logging": {
            "debug": False,
        },
        "notify": {
            "enabled": False,
            "command": "",
        },
        "tools": {
            "web_search": {
                "searxng_url": DEFAULT_WEB_SEARCH_SEARXNG_URL,
            },
        },
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(tomli_w.dumps(payload), encoding="utf-8")
    os.chmod(config_path, 0o600)


def _doctor(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
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
            "enabled": settings.model.thinking_enabled,
            "reasoning_effort": settings.model.reasoning_effort,
        },
    }


async def _doctor_live(settings: Settings) -> dict[str, object]:
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
    print(f"info thinking: enabled={thinking['enabled']} effort={thinking['reasoning_effort']}")
    live = report.get("live")
    if isinstance(live, dict):
        if live.get("ok"):
            usage = live.get("usage")
            print(
                "ok   live: "
                f"model={live.get('model')} base_url={live.get('base_url')} "
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
                f"{entry.id}\tupdated={entry.updated_at}\thistory_tokens={entry.active_tokens}\t"
                f"{format_usage_line(entry.usage)}"
            )
        return 0
    if args.sessions_command == "show":
        session = DeepyJsonlSession.open(Path.cwd(), args.session_id)
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
                    "items": items,
                }
            )
        )
        return 0
    return 1


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

    if not sys.stdin.isatty():
        parser.error("interactive mode requires a TTY; use `deepy doctor` or `deepy config show`.")
    settings = load_settings(args.config)
    if not settings.model.api_key:
        print("Deepy needs a DeepSeek API key before starting interactive mode.")
        setup_args = argparse.Namespace(config=args.config, force=True)
        _cmd_config_setup(setup_args)
        settings = load_settings(args.config)
    return run_interactive(settings)


if __name__ == "__main__":
    raise SystemExit(main())
