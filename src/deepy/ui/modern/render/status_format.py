"""Status, cache, audit, model and reset formatters for the Modern UI.

These helpers operate purely on their arguments (a pre-fetched session entry,
settings, etc.) and call no monkeypatched runtime entry points. The
orchestrators that resolve the session entry or MCP config stay in
:mod:`deepy.ui.modern.app` so their patched lookups keep working.
"""

from __future__ import annotations

from typing import Any

from deepy.audit import AuditModeState
from deepy.config import (
    PROVIDER_CATALOG,
    Settings,
    allows_custom_model_for_provider,
    is_supported_model_for_provider,
    is_supported_provider,
    is_valid_thinking_mode_for_provider,
    is_valid_ui_theme,
)
from deepy.format_tokens import format_token_count_short as _format_token_count_short
from deepy.llm.cache_context import format_cache_hit_rate, format_cache_usage
from deepy.ui.modern.screens import ResetConfigResult
from deepy.usage import context_window_usage

_LIGHT_TEXTUAL_THEMES = {"solarized-light", "catppuccin-latte", "atom-one-light"}


def _model_list_text() -> str:
    lines = ["Available providers and models:"]
    for provider in PROVIDER_CATALOG:
        lines.append(f"- {provider.id}: {provider.description}")
        for model in provider.models:
            lines.append(f"  - {model.name}: {model.description}")
        lines.append(f"  - thinking: {', '.join(provider.thinking_modes)}")
    return "\n".join(lines)


def _model_usage_text() -> str:
    return (
        "Usage: /model | /model list | "
        "/model set deepseek-v4-pro|deepseek-v4-flash [none|high|max] | "
        "/model set openrouter xiaomi/mimo-v2.5-pro none|minimal|low|medium|high|xhigh | "
        "/model set xiaomi mimo-v2.5-pro enabled|disabled | "
        "/model set localhost gpt-5.6-terra none|low|medium|high|xhigh | "
        "/model provider deepseek|openrouter|xiaomi|localhost | "
        "/model thinking <mode>"
    )


def _format_view_mode_confirmation(view_mode: str) -> str:
    reasoning_state = "reasoning shown" if view_mode == "full" else "reasoning hidden"
    return f"View: {view_mode} · {reasoning_state}"


def _is_light_tui_theme(shared_theme: str, textual_theme: str) -> bool:
    return shared_theme == "light" or textual_theme in _LIGHT_TEXTUAL_THEMES


def _reset_choice_description(description: str, *, default: bool = False) -> str:
    parts = [description] if description else []
    if default:
        parts.append("current default")
    return " · ".join(parts)


def _reset_config_validation_error(result: ResetConfigResult) -> str:
    if not result.provider:
        return "Provider is required."
    if not is_supported_provider(result.provider):
        return f"Invalid provider: {result.provider}\n{_model_usage_text()}"
    if not result.model:
        return "Model is required."
    if not (
        is_supported_model_for_provider(result.model, result.provider)
        or (allows_custom_model_for_provider(result.provider) and result.model.strip())
    ):
        return f"Invalid model: {result.model}\n{_model_usage_text()}"
    if result.thinking and not is_valid_thinking_mode_for_provider(result.thinking, result.provider):
        return f"Invalid thinking mode: {result.thinking}\n{_model_usage_text()}"
    if not result.base_url:
        return "Base URL is required."
    if not result.theme:
        return "Theme is required."
    if result.interface not in {"classic", "modern"}:
        return "Usage: UI must be classic|modern"
    if not is_valid_ui_theme(result.theme):
        return "Usage: theme must be dark|light"
    return ""


def _format_tui_ui_interface_label(interface: str) -> str:
    return "Modern UI" if interface == "modern" else "Classic UI"


def _format_tui_status_cache_hit_rate(session_entry: Any | None) -> str:
    if session_entry is None:
        return "cache --"
    hit_rate = format_cache_hit_rate(getattr(session_entry, "cache_usage", None))
    if hit_rate == "unknown":
        return "cache --"
    return f"cache {hit_rate}"


def _active_tui_audit_mode(audit_state: AuditModeState | None, settings: Settings) -> str:
    if audit_state is not None:
        return audit_state.mode.value
    return settings.audit.mode.value


def _format_tui_audit_mode(audit_state: AuditModeState | None, settings: Settings) -> str:
    active = _active_tui_audit_mode(audit_state, settings)
    configured = settings.audit.mode.value
    if active == configured:
        return active
    return f"{active} (runtime, config {configured})"


def _format_tui_cache_status(session_entry: Any | None) -> str:
    if session_entry is None:
        return "unknown"
    parts: list[str] = []
    generation = getattr(session_entry, "cache_prefix_generation", 0)
    if generation:
        parts.append(f"gen {generation}")
    usage = format_cache_usage(getattr(session_entry, "cache_usage", None))
    if usage != "unknown":
        parts.append(usage)
    reason = getattr(session_entry, "cache_break_reason", None)
    if reason:
        parts.append(f"break {reason}")
    return " · ".join(parts) if parts else "unknown"


def _format_tui_context_window_status(
    session_entry: Any | None,
    window_tokens: int,
    compact_threshold: int,
) -> str:
    window_text = _format_token_count_short(window_tokens)
    if window_tokens <= 0:
        return "ctx unknown"
    if session_entry is not None and session_entry.latest_context_window_tokens is not None:
        used_tokens = session_entry.latest_context_window_tokens
    else:
        usage_payload = session_entry.usage if session_entry is not None else None
        usage = context_window_usage(usage_payload) if isinstance(usage_payload, dict) else None
        used_tokens = usage.used_tokens if usage is not None else None
    if used_tokens is None:
        return f"ctx unknown/{window_text}"
    percentage = used_tokens / window_tokens * 100
    status = f"ctx {_format_token_count_short(used_tokens)}/{window_text} ({percentage:.1f}%)"
    if compact_threshold > 0 and used_tokens >= compact_threshold:
        status = f"{status} · compact next"
    return status
