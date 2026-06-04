"""Runtime status-line text rendering for the Classic terminal UI.

Pure helpers that build and fit the single-line working/runtime status shown in
the prompt toolbar. They operate only on their arguments plus a :class:`UiPalette`
and never touch session/runtime state, so they live outside ``terminal.py``.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from rich.cells import cell_len
from rich.text import Text

from deepy.ui.shared.render.message_view import format_tool_display_name
from deepy.ui.classic.status.status_footer import StatusFooter
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_STATUS_SEPARATOR = " · "


@dataclass(frozen=True)
class _RuntimeStatusSegments:
    prefix: str
    label: str = ""
    payload: str = ""


def _phase_status_text(text: str, palette: UiPalette) -> Text:
    return Text.assemble(
        ("• ", palette.toolbar_separator),
        (text, palette.toolbar_metadata),
    )


def _style_runtime_status_line(text: str, palette: UiPalette) -> Text:
    trailing_spaces = len(text) - len(text.rstrip(" "))
    visible = text.rstrip(" ")
    segments = _parse_runtime_status_segments(visible)
    if segments is None:
        styled = Text(visible, style=palette.toolbar_metadata)
    else:
        styled = Text()
        _append_runtime_status_prefix(styled, segments.prefix, palette)
        if segments.label:
            _append_runtime_status_separator(styled, palette)
            styled.append(segments.label, style=palette.toolbar_active)
        if segments.payload:
            _append_runtime_status_separator(styled, palette)
            styled.append(segments.payload, style=palette.toolbar_metadata)
    if trailing_spaces:
        styled.append(" " * trailing_spaces)
    return styled


def _append_runtime_status_prefix(text: Text, prefix: str, palette: UiPalette) -> None:
    spinner = ""
    rest = prefix
    if not rest.startswith("time ") and " time " in rest:
        spinner, rest = rest.split(" ", 1)
    if spinner:
        text.append(spinner, style=palette.toolbar_active)
        text.append(" ", style=palette.toolbar_separator)
    if not rest.startswith("time "):
        text.append(rest, style=palette.toolbar_metadata)
        return
    elapsed_and_hint = rest.removeprefix("time ")
    elapsed, separator, hint = elapsed_and_hint.partition(_STATUS_SEPARATOR)
    text.append("time ", style=palette.toolbar_metadata)
    text.append(elapsed, style=palette.toolbar_identity)
    if separator:
        _append_runtime_status_separator(text, palette)
        text.append(hint, style=palette.warning)


def _append_runtime_status_separator(text: Text, palette: UiPalette) -> None:
    text.append(_STATUS_SEPARATOR, style=palette.toolbar_separator)


def _sanitize_status_line(text: str) -> str:
    stripped = _ANSI_ESCAPE_RE.sub("", text)
    stripped = stripped.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    stripped = _CONTROL_CHAR_RE.sub("", stripped)
    return re.sub(r" {2,}", " ", stripped).strip()


def _truncate_status_line(text: str, *, max_width: int) -> str:
    if cell_len(text) <= max_width:
        return text
    if max_width <= 1:
        return "…" if max_width == 1 else ""
    suffix = "…"
    available = max_width - cell_len(suffix)
    used = 0
    result: list[str] = []
    for char in text:
        char_width = cell_len(char)
        if used + char_width > available:
            break
        result.append(char)
        used += char_width
    return "".join(result).rstrip() + suffix


def _fit_status_line(text: str, *, width: int) -> str:
    width = max(width, 0)
    sanitized = _sanitize_status_line(text)
    segments = _parse_runtime_status_segments(sanitized)
    line = (
        _fit_runtime_status_segments(segments, width=width)
        if segments is not None
        else _truncate_status_line(sanitized, max_width=width)
    )
    return line + (" " * max(0, width - cell_len(line)))


def _parse_runtime_status_segments(text: str) -> _RuntimeStatusSegments | None:
    interrupt = "esc to interrupt"
    interrupt_index = text.find(interrupt)
    if interrupt_index < 0:
        return None

    prefix_end = interrupt_index + len(interrupt)
    prefix = text[:prefix_end].strip()
    detail = text[prefix_end:]
    if detail.startswith(_STATUS_SEPARATOR):
        detail = detail[len(_STATUS_SEPARATOR) :].strip()
    else:
        detail = detail.strip()
    if not detail:
        return _RuntimeStatusSegments(prefix=prefix)

    if detail.startswith(f"local command{_STATUS_SEPARATOR}"):
        payload = detail.removeprefix(f"local command{_STATUS_SEPARATOR}").strip()
        return _RuntimeStatusSegments(prefix=prefix, label="local command", payload=payload)

    tool_match = re.match(r"(tool \[[^\]]+\])(?:\s+(.*))?$", detail)
    if tool_match:
        label, payload = tool_match.groups()
        payload_text = (payload or "").strip()
        if payload_text.startswith("·"):
            payload_text = payload_text.removeprefix("·").strip()
        return _RuntimeStatusSegments(prefix=prefix, label=label, payload=payload_text)

    return _RuntimeStatusSegments(prefix=prefix, label=detail)


def _fit_runtime_status_segments(segments: _RuntimeStatusSegments, *, width: int) -> str:
    if width <= 0:
        return ""

    full = _runtime_status_segments_text(segments)
    if cell_len(full) <= width:
        return full

    if cell_len(segments.prefix) >= width:
        return _truncate_status_line(segments.prefix, max_width=width)

    if not segments.label:
        return _truncate_status_line(segments.prefix, max_width=width)

    prefix_label = f"{segments.prefix}{_STATUS_SEPARATOR}{segments.label}"
    if segments.payload:
        base = f"{prefix_label}{_STATUS_SEPARATOR}"
        payload_width = width - cell_len(base)
        if payload_width > 0:
            payload = _truncate_status_line(segments.payload, max_width=payload_width)
            return f"{base}{payload}".rstrip()

    if cell_len(prefix_label) <= width:
        return prefix_label

    label_base = f"{segments.prefix}{_STATUS_SEPARATOR}"
    label_width = width - cell_len(label_base)
    if label_width > 0:
        label = _truncate_status_line(segments.label, max_width=label_width)
        return f"{label_base}{label}".rstrip()

    return _truncate_status_line(segments.prefix, max_width=width)


def _runtime_status_segments_text(segments: _RuntimeStatusSegments) -> str:
    parts = [segments.prefix]
    if segments.label:
        parts.append(segments.label)
    if segments.payload:
        parts.append(segments.payload)
    return _STATUS_SEPARATOR.join(parts)


def _working_status_text(
    started_at: float,
    detail: str = "",
    *,
    palette: UiPalette | None = None,
    footer: StatusFooter | None = None,
) -> Text:
    palette = palette or DARK_PALETTE
    elapsed = _format_duration_ms(int((time.monotonic() - started_at) * 1000)) or "0s"
    if footer is not None and footer.segments:
        return _runtime_status_text(
            elapsed=elapsed,
            detail=detail or "status working",
            spinner=_runtime_spinner_frame(started_at),
            palette=palette,
            detail_before_interrupt=True,
        )
    text = Text.assemble(
        ("Working ", f"bold {palette.muted}"),
        (f"({elapsed} · esc to interrupt)", palette.muted),
    )
    if detail:
        text.append(" · ", style=palette.muted)
        text.append(detail, style=palette.muted)
    return text


def _local_command_status_text(
    command: str,
    started_at: float,
    *,
    palette: UiPalette | None = None,
    footer: StatusFooter | None = None,
) -> Text:
    palette = palette or DARK_PALETTE
    elapsed = _format_duration_ms(int((time.monotonic() - started_at) * 1000)) or "0s"
    if footer is not None and footer.segments:
        text = _runtime_status_text(
            elapsed=elapsed,
            detail="local command",
            spinner=_runtime_spinner_frame(started_at),
            palette=palette,
        )
        text.append(" · ", style=palette.toolbar_separator)
        text.append(command, style=palette.toolbar_metadata)
        return text
    text = Text.assemble(
        ("Running local command ", f"bold {palette.muted}"),
        (f"({elapsed})", palette.muted),
    )
    text.append(" · ", style=palette.muted)
    text.append(command, style=palette.muted)
    return text


def _runtime_status_text(
    *,
    elapsed: str,
    detail: str,
    spinner: str = "",
    palette: UiPalette,
    detail_before_interrupt: bool = False,
) -> Text:
    text = Text()
    if spinner:
        text.append(spinner, style=palette.toolbar_active)
        text.append(" ", style=palette.toolbar_separator)
    text.append("time ", style=palette.toolbar_metadata)
    text.append(elapsed, style=palette.toolbar_identity)
    if detail and (detail_before_interrupt or detail.startswith("↓ ")):
        _append_runtime_status_separator(text, palette)
        _append_runtime_detail(text, detail, palette)
        _append_runtime_status_separator(text, palette)
        text.append("esc to interrupt", style=palette.warning)
    else:
        _append_runtime_status_separator(text, palette)
        text.append("esc to interrupt", style=palette.warning)
        if detail:
            _append_runtime_status_separator(text, palette)
            _append_runtime_detail(text, detail, palette)
    return text


def _append_runtime_detail(text: Text, detail: str, palette: UiPalette) -> None:
    tool_match = re.match(r"(tool \[[^\]]+\])(?:\s+(.*))?$", detail)
    if tool_match:
        label, payload = tool_match.groups()
        text.append(label, style=palette.toolbar_active)
        if payload:
            text.append(" ", style=palette.toolbar_separator)
            text.append(payload, style=palette.toolbar_metadata)
        return
    text.append(detail, style=palette.toolbar_active)


def _runtime_spinner_frame(started_at: float) -> str:
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    index = int(max(0.0, time.monotonic() - started_at)) % len(frames)
    return frames[index]


def _runtime_tool_activity_name(tool_name: str) -> str:
    if tool_name.startswith("mcp_"):
        return "MCP"
    return format_tool_display_name(tool_name)


def _format_duration_ms(duration_ms: int) -> str:
    seconds = max(0, int(duration_ms // 1000))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"
