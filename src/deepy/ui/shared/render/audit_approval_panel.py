from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from deepy.audit import PendingApproval
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette
from deepy.ui.shared.render.welcome import format_home_relative_path
from deepy.utils import json as json_utils


MAX_METADATA_VALUE_CHARS = 140


@dataclass(frozen=True)
class ApprovalPanelView:
    title: str
    target_label: str
    target: str
    metadata: tuple[tuple[str, str], ...] = ()
    preview: RenderableType | None = None
    can_expand: bool = False
    expanded: bool = False


def build_approval_panel(
    item: PendingApproval,
    *,
    palette: UiPalette | None = None,
    project_root: str | Path | None = None,
    expanded: bool = False,
    width: int | None = None,
) -> tuple[Panel, bool]:
    palette = palette or DARK_PALETTE
    view = build_approval_view(
        item,
        palette=palette,
        project_root=project_root,
        expanded=expanded,
        width=width,
    )
    return render_approval_panel(view, palette=palette), view.can_expand


def build_approval_view(
    item: PendingApproval,
    *,
    palette: UiPalette | None = None,
    project_root: str | Path | None = None,
    expanded: bool = False,
    width: int | None = None,
) -> ApprovalPanelView:
    palette = palette or DARK_PALETTE
    args = _json_object_arguments(item.arguments)
    tool_name = item.tool_name or item.name or "tool"
    if item.server_name or item.action_kind == "mcp_tool":
        return _mcp_approval_view(item, args)
    if tool_name == "test_shell":
        return _shell_approval_view(args, title="Approve test command?")
    if tool_name == "shell" or item.action_kind == "command":
        return _shell_approval_view(args)
    if tool_name == "Write":
        return _write_approval_view(
            args,
            palette=_approval_diff_palette(palette),
            project_root=project_root,
            expanded=expanded,
            width=width,
        )
    if tool_name == "Update":
        return _update_approval_view(
            args,
            palette=_approval_diff_palette(palette),
            project_root=project_root,
            expanded=expanded,
            width=width,
        )
    return _fallback_approval_view(item, args)


def render_approval_panel(view: ApprovalPanelView, *, palette: UiPalette | None = None) -> Panel:
    palette = palette or DARK_PALETTE
    summary = Text()
    summary.append(f"{view.target_label}: ", style=f"bold {palette.muted}")
    summary.append(view.target or "-")
    for label, value in view.metadata:
        summary.append("\n")
        summary.append(f"{label}: ", style=f"bold {palette.muted}")
        summary.append(value)

    renderables: list[RenderableType] = [summary]
    if view.preview is not None:
        renderables.append(Text())
        renderables.append(view.preview)

    return Panel(
        Group(*renderables),
        title=view.title,
        border_style=palette.warning,
        padding=(0, 1),
    )


def format_approval_path(path: str, *, project_root: str | Path | None = None) -> str:
    if not path:
        return ""
    raw_path = Path(path).expanduser()
    if project_root is not None:
        root = Path(project_root).expanduser().resolve(strict=False)
        target = raw_path if raw_path.is_absolute() else root / raw_path
        resolved_target = target.resolve(strict=False)
        try:
            relative = resolved_target.relative_to(root)
        except ValueError:
            return format_home_relative_path(resolved_target)
        return "." if str(relative) == "." else relative.as_posix()
    return format_home_relative_path(raw_path)


def _shell_approval_view(
    args: dict[str, Any] | None,
    *,
    title: str = "Approve shell command?",
) -> ApprovalPanelView:
    command = _string_arg(args, "command") or "(missing command)"
    metadata = _metadata_items(
        (
            ("description", _string_arg(args, "description")),
            ("background", "true" if _bool_arg(args, "run_in_background") else None),
        )
    )
    return ApprovalPanelView(
        title=title,
        target_label="command",
        target=command,
        metadata=metadata,
    )


def _mcp_approval_view(item: PendingApproval, args: dict[str, Any] | None) -> ApprovalPanelView:
    tool_name = item.tool_name or item.name or "tool"
    target = f"{item.server_name}/{tool_name}" if item.server_name else tool_name
    metadata = _metadata_items(
        (
            ("url", _string_arg(args, "url")),
            ("urls", _list_arg_summary(args, "urls")),
            ("query", _string_arg(args, "query")),
            ("format", _string_arg(args, "format")),
        )
    )
    return ApprovalPanelView(
        title="Approve MCP tool?",
        target_label="tool",
        target=target,
        metadata=metadata,
    )


def _write_approval_view(
    args: dict[str, Any] | None,
    *,
    palette: UiPalette,
    project_root: str | Path | None,
    expanded: bool,
    width: int | None,
) -> ApprovalPanelView:
    path = _string_arg(args, "path") or "(missing path)"
    display_path = format_approval_path(path, project_root=project_root) if path else path
    content = _string_arg(args, "content") or ""
    metadata = _metadata_items(
        (
            ("size", f"{len(content)} chars"),
            ("overwrite", "true" if _bool_arg(args, "overwrite") else None),
        )
    )
    return ApprovalPanelView(
        title=f"Approve write? {display_path}",
        target_label="path",
        target=display_path,
        metadata=metadata,
    )


def _update_approval_view(
    args: dict[str, Any] | None,
    *,
    palette: UiPalette,
    project_root: str | Path | None,
    expanded: bool,
    width: int | None,
) -> ApprovalPanelView:
    edits = _update_edits(args)
    display_paths = _update_display_paths(edits, project_root=project_root)
    target = display_paths[0] if len(display_paths) == 1 else f"{len(display_paths)} files"
    has_diff_context = any(edit.old is not None or edit.new is not None for edit in edits)
    metadata = _metadata_items(
        (
            ("edits", str(len(edits)) if edits else None),
            ("summary", _update_argument_summary(args) if not has_diff_context else None),
        )
    )
    return ApprovalPanelView(
        title=f"Approve update? {target}",
        target_label="path",
        target=target,
        metadata=metadata,
    )


def _update_argument_summary(args: dict[str, Any] | None) -> str | None:
    if not args:
        return None
    keys = [key for key in ("replace_all", "expected_replacements", "edits") if key in args]
    if not keys:
        return None
    return ", ".join(keys)


def _fallback_approval_view(item: PendingApproval, args: dict[str, Any] | None) -> ApprovalPanelView:
    tool_name = item.tool_name or item.name or "tool"
    metadata = (("arguments", _bounded_json(args)),) if args else ()
    if not args and item.arguments:
        metadata = (("arguments", _truncate(item.arguments)),)
    return ApprovalPanelView(
        title="Approve tool call?",
        target_label="tool",
        target=tool_name,
        metadata=metadata,
    )


def _approval_diff_palette(palette: UiPalette) -> UiPalette:
    if palette.name == "light":
        return replace(
            palette,
            diff_added="#064e3b on #d1fae5",
            diff_added_gutter="#047857 on #d1fae5",
            diff_added_marker="bold #059669 on #d1fae5",
            diff_removed="#7f1d1d on #ffd6d9",
            diff_removed_gutter="#991b1b on #ffc6cc",
            diff_removed_marker="bold #b91c1c on #ffc6cc",
            diff_context="#4b5563",
        )
    return replace(
        palette,
        diff_added="#a7f3c2 on #18551a",
        diff_added_gutter="#a7f3c2 on #18551a",
        diff_added_marker="bold #a7f3c2 on #18551a",
        diff_removed="#f4c7c3 on #360000",
        diff_removed_gutter="#f4c7c3 on #360000",
        diff_removed_marker="bold #f4c7c3 on #360000",
        diff_context="#c6d0f5",
    )


@dataclass(frozen=True)
class _UpdateEditPreview:
    display_path: str
    old: str | None
    new: str | None


def _update_edits(args: dict[str, Any] | None) -> list[_UpdateEditPreview]:
    if not args:
        return []
    parent_path = _string_arg(args, "path")
    raw_edits = args.get("edits")
    if isinstance(raw_edits, list):
        edits: list[_UpdateEditPreview] = []
        for raw_edit in raw_edits:
            if not isinstance(raw_edit, dict):
                continue
            path = _string_arg(raw_edit, "path") or parent_path or ""
            edits.append(
                _UpdateEditPreview(
                    display_path=path,
                    old=_string_arg(raw_edit, "old"),
                    new=_string_arg(raw_edit, "new"),
                )
            )
        return edits
    path = parent_path or ""
    return [
        _UpdateEditPreview(
            display_path=path,
            old=_string_arg(args, "old"),
            new=_string_arg(args, "new"),
        )
    ]


def _update_display_paths(
    edits: list[_UpdateEditPreview],
    *,
    project_root: str | Path | None,
) -> list[str]:
    paths = [
        format_approval_path(edit.display_path, project_root=project_root)
        for edit in edits
        if edit.display_path
    ]
    unique = list(dict.fromkeys(paths))
    return unique or ["(missing path)"]


def _json_object_arguments(arguments: str) -> dict[str, Any] | None:
    if not arguments.strip():
        return None
    try:
        parsed = json_utils.loads(arguments)
    except json_utils.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _metadata_items(items: tuple[tuple[str, str | None], ...]) -> tuple[tuple[str, str], ...]:
    return tuple((label, _truncate(value)) for label, value in items if value)


def _string_arg(args: dict[str, Any] | None, key: str) -> str | None:
    if not args:
        return None
    value = args.get(key)
    return value if isinstance(value, str) and value else None


def _bool_arg(args: dict[str, Any] | None, key: str) -> bool:
    if not args:
        return False
    return bool(args.get(key) is True)


def _list_arg_summary(args: dict[str, Any] | None, key: str) -> str | None:
    if not args:
        return None
    value = args.get(key)
    if not isinstance(value, list) or not value:
        return None
    return ", ".join(_truncate(str(item), max_chars=80) for item in value[:3])


def _bounded_json(value: object) -> str:
    return _truncate(json_utils.dumps_pretty(value), max_chars=MAX_METADATA_VALUE_CHARS)


def _truncate(value: str, *, max_chars: int = MAX_METADATA_VALUE_CHARS) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."
