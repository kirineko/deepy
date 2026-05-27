from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepy.config import Settings
from deepy.llm.cache_context import format_cache_usage
from deepy.mcp import mcp_policy_to_dict
from deepy.prompts.runtime_context import build_runtime_context
from deepy.sessions import list_session_entries
from deepy.skills import discover_skills
from deepy.usage import context_window_usage, format_usage_line, merge_usage, normalize_usage
from deepy.utils import json as json_utils


BALANCE_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class BalanceInfo:
    currency: str
    total_balance: str
    granted_balance: str
    topped_up_balance: str


@dataclass(frozen=True)
class BalanceStatus:
    is_available: bool | None = None
    balance_infos: tuple[BalanceInfo, ...] = ()
    unavailable_reason: str | None = None

    @property
    def known(self) -> bool:
        return self.is_available is not None and self.unavailable_reason is None


@dataclass(frozen=True)
class StatusReport:
    project_root: Path
    provider: str
    model: str
    reasoning_mode: str
    api_key_configured: bool
    context_window_tokens: int
    compact_threshold_tokens: int
    reserved_context_tokens: int
    input_suggestions_enabled: bool
    session_count: int
    skill_count: int
    mcp: dict[str, Any]
    runtime_context: str
    active_session_id: str | None = None
    active_session_usage: dict[str, Any] | None = None
    project_usage: dict[str, Any] | None = None
    latest_context_window_tokens: int | None = None
    cache_prefix_generation: int | None = None
    cache_break_reason: str | None = None
    cache_usage: dict[str, Any] | None = None
    balance: BalanceStatus | None = None


def build_status_report(
    project_root: Path,
    settings: Settings,
    *,
    current_session_id: str | None = None,
    balance: BalanceStatus | None = None,
) -> StatusReport:
    root = project_root.resolve()
    entries = list_session_entries(root)
    active_entry = next((entry for entry in entries if entry.id == current_session_id), None)
    project_usage = merge_usage(*(entry.usage for entry in entries if entry.usage)).to_dict()
    latest_context_tokens = None
    if active_entry is not None:
        latest_context_tokens = active_entry.latest_context_window_tokens
        if latest_context_tokens is None and active_entry.usage:
            active_context_usage = context_window_usage(active_entry.usage)
            latest_context_tokens = (
                active_context_usage.used_tokens if active_context_usage is not None else None
            )
    return StatusReport(
        project_root=root,
        provider=settings.model.provider,
        model=settings.model.name,
        reasoning_mode=settings.model.reasoning_mode,
        api_key_configured=bool(settings.model.api_key),
        context_window_tokens=settings.context.window_tokens,
        compact_threshold_tokens=settings.context.resolved_compact_threshold,
        reserved_context_tokens=settings.context.reserved_context_tokens,
        input_suggestions_enabled=settings.ui.input_suggestions_enabled,
        session_count=len(entries),
        skill_count=len(discover_skills(root)),
        mcp=mcp_policy_to_dict(settings),
        runtime_context=build_runtime_context(root),
        active_session_id=current_session_id,
        active_session_usage=active_entry.usage if active_entry is not None else None,
        project_usage=project_usage or None,
        latest_context_window_tokens=latest_context_tokens,
        cache_prefix_generation=active_entry.cache_prefix_generation
        if active_entry is not None
        else None,
        cache_break_reason=active_entry.cache_break_reason if active_entry is not None else None,
        cache_usage=active_entry.cache_usage if active_entry is not None else None,
        balance=balance,
    )


def format_status_report(report: StatusReport) -> str:
    return "\n".join(
        [
            f"Project: {report.project_root}",
            f"Provider: {report.provider}",
            f"Model: {report.model}",
            f"Thinking: {report.reasoning_mode}",
            f"API key: {'configured' if report.api_key_configured else 'missing'}",
            f"Context: {report.context_window_tokens} tokens",
            f"Compact threshold: {report.compact_threshold_tokens} tokens",
            f"Reserved context: {report.reserved_context_tokens} tokens",
            f"Input suggestions: {'enabled' if report.input_suggestions_enabled else 'disabled'}",
            f"Sessions: {report.session_count}",
            f"Skills: {report.skill_count}",
            f"Session usage: {_format_status_usage(report.active_session_usage)}",
            f"Session cache: {_format_cache_status(report)}",
            f"Project usage: {_format_status_usage(report.project_usage)}",
            f"Context window: {_format_context_window_status(report)}",
            (
                "MCP: "
                f"{'enabled' if report.mcp.get('enabled') else 'disabled'} "
                f"config={report.mcp.get('config_path')}"
            ),
            "",
            report.runtime_context,
        ]
    )


def status_report_to_dict(report: StatusReport) -> dict[str, Any]:
    return {
        "project_root": str(report.project_root),
        "provider": report.provider,
        "model": report.model,
        "reasoning_mode": report.reasoning_mode,
        "api_key_configured": report.api_key_configured,
        "context_window_tokens": report.context_window_tokens,
        "compact_threshold_tokens": report.compact_threshold_tokens,
        "reserved_context_tokens": report.reserved_context_tokens,
        "input_suggestions_enabled": report.input_suggestions_enabled,
        "session_count": report.session_count,
        "skill_count": report.skill_count,
        "mcp": report.mcp,
        "runtime_context": report.runtime_context,
        "active_session_id": report.active_session_id,
        "active_session_usage": report.active_session_usage,
        "project_usage": report.project_usage,
        "latest_context_window_tokens": report.latest_context_window_tokens,
        "cache_prefix_generation": report.cache_prefix_generation,
        "cache_break_reason": report.cache_break_reason,
        "cache_usage": report.cache_usage,
        "balance": balance_status_to_dict(report.balance),
    }


def fetch_deepseek_balance(
    settings: Settings,
    *,
    urlopen: Any = urllib.request.urlopen,
    timeout: float = BALANCE_TIMEOUT_SECONDS,
) -> BalanceStatus:
    if not settings.model.api_key:
        return BalanceStatus(unavailable_reason="api key missing")
    parsed = urllib.parse.urlparse(settings.model.base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "api.deepseek.com":
        return BalanceStatus(unavailable_reason="unsupported api host")
    url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/user/balance", "", "", ""))
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {settings.model.api_key}",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        return BalanceStatus(unavailable_reason=f"http {exc.code}")
    except TimeoutError:
        return BalanceStatus(unavailable_reason="timeout")
    except (OSError, urllib.error.URLError):
        return BalanceStatus(unavailable_reason="network error")
    try:
        payload = json_utils.loads(raw.decode("utf-8"))
    except Exception:
        return BalanceStatus(unavailable_reason="invalid response")
    return parse_balance_payload(payload)


def parse_balance_payload(payload: Any) -> BalanceStatus:
    if not isinstance(payload, dict) or not isinstance(payload.get("is_available"), bool):
        return BalanceStatus(unavailable_reason="invalid response")
    raw_infos = payload.get("balance_infos")
    if not isinstance(raw_infos, list):
        return BalanceStatus(unavailable_reason="invalid response")
    infos: list[BalanceInfo] = []
    for item in raw_infos:
        if not isinstance(item, dict):
            return BalanceStatus(unavailable_reason="invalid response")
        currency = item.get("currency")
        total = item.get("total_balance")
        granted = item.get("granted_balance")
        topped_up = item.get("topped_up_balance")
        if not all(isinstance(value, str) for value in (currency, total, granted, topped_up)):
            return BalanceStatus(unavailable_reason="invalid response")
        infos.append(
            BalanceInfo(
                currency=currency,
                total_balance=total,
                granted_balance=granted,
                topped_up_balance=topped_up,
            )
        )
    return BalanceStatus(
        is_available=payload["is_available"],
        balance_infos=tuple(infos),
    )


def format_compact_status_report(report: StatusReport) -> str:
    rows = [
        ("model", f"{report.provider} {report.model}[{report.reasoning_mode}]"),
        ("api", "configured" if report.api_key_configured else "missing"),
        ("balance", format_balance_status(report.balance)),
        ("session usage", _format_status_usage(report.active_session_usage)),
        ("session cache", _format_cache_status(report)),
        ("project usage", _format_status_usage(report.project_usage)),
        ("ctx", _format_context_window_status(report)),
        ("project", str(report.project_root)),
        ("sessions", str(report.session_count)),
        ("skills", str(report.skill_count)),
        (
            "mcp",
            f"{'enabled' if report.mcp.get('enabled') else 'disabled'}"
            + (f" config={report.mcp.get('config_path')}" if report.mcp.get("config_path") else ""),
        ),
    ]
    return _simple_box("Deepy Status", rows)


def format_balance_status(balance: BalanceStatus | None) -> str:
    if balance is None:
        return "not requested"
    if balance.unavailable_reason:
        return f"unavailable ({balance.unavailable_reason})"
    state = "available" if balance.is_available else "unavailable"
    if not balance.balance_infos:
        return state
    details = ", ".join(
        f"{info.currency} {info.total_balance} "
        f"(grant {info.granted_balance}, top-up {info.topped_up_balance})"
        for info in balance.balance_infos
    )
    return f"{state}: {details}"


def balance_status_to_dict(balance: BalanceStatus | None) -> dict[str, Any] | None:
    if balance is None:
        return None
    return {
        "is_available": balance.is_available,
        "balance_infos": [
            {
                "currency": info.currency,
                "total_balance": info.total_balance,
                "granted_balance": info.granted_balance,
                "topped_up_balance": info.topped_up_balance,
            }
            for info in balance.balance_infos
        ],
        "unavailable_reason": balance.unavailable_reason,
    }


def _format_status_usage(usage: dict[str, Any] | None) -> str:
    normalized = normalize_usage(usage)
    if not normalized.known:
        return "unknown"
    prefix = f"requests {normalized.requests:,} · " if normalized.requests else ""
    return f"{prefix}{format_usage_line(normalized)}"


def _format_cache_status(report: StatusReport) -> str:
    parts = []
    if report.cache_prefix_generation is not None:
        parts.append(f"prefix gen {report.cache_prefix_generation}")
    usage = format_cache_usage(report.cache_usage)
    if usage != "unknown":
        parts.append(usage)
    if report.cache_break_reason:
        parts.append(f"last break: {report.cache_break_reason}")
    return " · ".join(parts) if parts else "unknown"


def _format_context_window_status(report: StatusReport) -> str:
    total = report.context_window_tokens
    if total <= 0:
        return "unknown"
    if report.latest_context_window_tokens is None:
        return f"unknown/{_format_token_count_short(total)}"
    used = report.latest_context_window_tokens
    remaining = max(total - used, 0)
    percentage = used / total * 100
    status = (
        f"{_format_token_count_short(used)}/{_format_token_count_short(total)} "
        f"({percentage:.1f}%, {_format_token_count_short(remaining)} left)"
    )
    if report.compact_threshold_tokens > 0 and used >= report.compact_threshold_tokens:
        status = f"{status} · compact next"
    return status


def _format_token_count_short(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
    return str(value)


def _simple_box(title: str, rows: list[tuple[str, str]]) -> str:
    key_width = max(len(key) for key, _ in rows)
    row_texts = [f"{key.ljust(key_width)}  {value}" for key, value in rows]
    width = max(88, len(title), *(len(text) for text in row_texts))
    border = "─" * width
    lines = [f"╭{border}╮", _box_line(title, width), f"├{border}┤"]
    for text in row_texts:
        lines.append(_box_line(text, width))
    lines.append(f"╰{border}╯")
    return "\n".join(lines)


def _box_line(text: str, width: int) -> str:
    clipped = text[:width]
    return f"│{clipped.ljust(width)}│"
