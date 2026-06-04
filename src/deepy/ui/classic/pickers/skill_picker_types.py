"""Shared data types, label formatting and styling for the skill pickers.

Imported by the individual picker modules and re-exported from
``deepy.ui.classic.pickers.skill_picker``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from prompt_toolkit.styles import Style

from deepy.skill_market import MarketSkill
from deepy.ui.classic.markdown import render_markdown


@dataclass(frozen=True)
class SkillMenuAction:
    action: str
    name: str = ""
    scope: str = ""
    path: Path | None = None
    version: str = ""
    installed_at: str = ""
    managed_by_market: bool = False
    market_skill: MarketSkill | None = None


@dataclass(frozen=True)
class SkillInstallScope:
    scope: Literal["user", "project"]
    path: Path


@dataclass(frozen=True)
class InstalledSkillView:
    name: str
    scope: str
    path: Path
    version: str = ""
    installed_at: str = ""
    managed_by_market: bool = False


@dataclass(frozen=True)
class SkillDetailView:
    name: str
    body: str = ""
    scope: str = ""
    path: Path | None = None
    version: str = ""
    installed_at: str = ""
    managed_by_market: bool = False
    description: str = ""
    uploaded_at: str = ""
    sha256: str = ""
    installed: bool | None = None
    markdown: bool = False


def format_market_skill_label(skill: MarketSkill) -> str:
    marker = "[x]" if skill.installed else "[ ]"
    version = f"  {skill.version}" if skill.version else ""
    uploaded = f"  uploaded {skill.uploaded_at[:10]}" if skill.uploaded_at else ""
    description = _shorten(skill.description, 150)
    second_line = f"\n  {description}" if description else ""
    return f"{marker} {skill.name}{version}{uploaded}{second_line}"


def format_installed_skill_label(skill: InstalledSkillView) -> str:
    version = f"  {skill.version}" if skill.version else ""
    installed = f"  installed {skill.installed_at[:10]}" if skill.installed_at else ""
    marker = "[market]" if skill.managed_by_market else f"[{skill.scope}]"
    path = _shorten(str(skill.path), 120)
    return f"{marker} {skill.name}{version}{installed}\n  {path}"


def format_skill_detail_text(detail: SkillDetailView) -> str:
    metadata = [f"Name: {detail.name}"]
    if detail.scope:
        metadata.append(f"Scope: {detail.scope}")
    if detail.path is not None:
        metadata.append(f"Path: {detail.path}")
    if detail.version:
        metadata.append(f"Version: {detail.version}")
    if detail.installed_at:
        metadata.append(f"Installed: {detail.installed_at}")
    if detail.uploaded_at:
        metadata.append(f"Uploaded: {detail.uploaded_at}")
    if detail.managed_by_market:
        metadata.append("Managed by market: yes")
    if detail.installed is not None:
        metadata.append(f"Installed locally: {'yes' if detail.installed else 'no'}")
    if detail.sha256:
        metadata.append(f"SHA256: {detail.sha256}")
    if detail.description:
        metadata.append(f"Description: {detail.description}")
    body = _render_detail_body(detail)
    return "\n".join(metadata) + "\n\n" + body


def _render_detail_body(detail: SkillDetailView) -> str:
    source = detail.body.strip() or detail.description.strip()
    if not source:
        return "(no details available)"
    if not detail.markdown:
        return source
    return render_markdown(source, width=100).plain


def _shorten(value: str, max_chars: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _skill_picker_style() -> Style:
    return Style.from_dict(
        {
            "header": "bg:#1f2333 #8be9fd",
            "header.title": "bold",
            "header.meta": "#8a90aa",
            "header.sep": "#5f6688",
            "tab": "#8a90aa",
            "tab.active": "#1f2333 bg:#8be9fd bold",
            "frame.border": "#5f6688",
            "frame.label": "#8be9fd bold",
            "skill-list": "#c6d0f5",
            "skill-list.checked": "#8be9fd bold",
            "radio-selected": "#8be9fd bold",
            "footer": "bg:#1f2333 #8a90aa",
            "footer.text": "#8a90aa",
        }
    )
