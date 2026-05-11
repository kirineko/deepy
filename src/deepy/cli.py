from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import tomli_w

from . import __version__
from .config import load_settings, settings_to_toml_dict
from .llm.provider import build_provider_bundle


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

    doctor_parser = subparsers.add_parser("doctor", help="Validate local Deepy setup.")
    doctor_parser.add_argument("--json", action="store_true", help="Print JSON diagnostics.")

    return parser


def _cmd_config_show(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    data = settings_to_toml_dict(settings, reveal_secret=args.show_secret)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(tomli_w.dumps(data), end="")
    return 0


def _doctor(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    settings = load_settings(args.config)
    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    check("config", True, str(settings.path))
    check(
        "api_key",
        bool(settings.model.api_key),
        "configured" if settings.model.api_key else "missing",
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


def _cmd_doctor(args: argparse.Namespace) -> int:
    code, report = _doctor(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return code
    for item in report["checks"]:
        status = "ok" if item["ok"] else "fail"
        print(f"{status:4} {item['name']}: {item['detail']}")
    thinking = report["thinking"]
    print(f"info thinking: enabled={thinking['enabled']} effort={thinking['reasoning_effort']}")
    return code


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "config":
        if args.config_command == "show":
            return _cmd_config_show(args)
    if args.command == "doctor":
        return _cmd_doctor(args)

    if not sys.stdin.isatty():
        parser.error("interactive mode requires a TTY; use `deepy doctor` or `deepy config show`.")
    print("Deepy interactive TUI migration is not wired yet. Run `deepy doctor` to verify setup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
