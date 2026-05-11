from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class SkillInfo:
    name: str
    path: Path
    description: str = ""
    scope: str = "user"


def discover_skills(project_root: Path, *, home: Path | None = None) -> list[SkillInfo]:
    home_dir = home or Path.home()
    roots = [
        ("user", home_dir / ".agents" / "skills"),
        ("project", project_root / ".deepy" / "skills"),
    ]
    by_name: dict[str, SkillInfo] = {}
    for scope, root in roots:
        for skill in _discover_skills_root(root, scope=scope):
            by_name[_normalize_name(skill.name)] = skill
    return sorted(by_name.values(), key=lambda item: item.name)


def find_skill(project_root: Path, name: str, *, home: Path | None = None) -> SkillInfo | None:
    normalized = _normalize_name(name)
    for skill in discover_skills(project_root, home=home):
        if _normalize_name(skill.name) == normalized:
            return skill
    return None


def read_skill_body(skill: SkillInfo) -> str:
    text = skill.path.read_text(encoding="utf-8", errors="replace")
    _frontmatter, body = _split_frontmatter(text)
    return body.strip()


def format_skills_for_prompt(skills: Iterable[SkillInfo]) -> str:
    return _format_skills(skills, include_paths=True)


def format_skills_for_terminal(skills: Iterable[SkillInfo]) -> str:
    return _format_skills(skills, include_paths=False)


def _format_skills(skills: Iterable[SkillInfo], *, include_paths: bool) -> str:
    grouped: dict[str, list[SkillInfo]] = {"project": [], "user": []}
    for skill in skills:
        grouped.setdefault(skill.scope, []).append(skill)

    lines: list[str] = []
    for scope in ("project", "user"):
        items = grouped.get(scope) or []
        if not items:
            continue
        lines.append(f"{scope.title()} skills:")
        for skill in sorted(items, key=lambda item: item.name):
            description = f" - {skill.description}" if skill.description else ""
            path = f" ({skill.path})" if include_paths else ""
            lines.append(f"- {skill.name}{description}{path}")
    return "\n".join(lines) if lines else "No skills found."


def _discover_skills_root(root: Path, *, scope: str) -> list[SkillInfo]:
    if not root.is_dir():
        return []
    skills: list[SkillInfo] = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        skill_path = entry / "SKILL.md"
        if not entry.is_dir() or not skill_path.is_file():
            continue
        skill = read_skill_info(skill_path, default_name=entry.name, scope=scope)
        if skill is not None:
            skills.append(skill)
    return skills


def read_skill_info(
    path: Path,
    *,
    default_name: str | None = None,
    scope: str = "user",
) -> SkillInfo | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    frontmatter, body = _split_frontmatter(text)
    name = _clean_scalar(frontmatter.get("name")) or default_name or path.parent.name
    description = _clean_scalar(frontmatter.get("description")) or _first_body_line(body)
    return SkillInfo(name=name, description=description, path=path, scope=scope)


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return _parse_simple_yaml(lines[1:index]), "\n".join(lines[index + 1 :])
    return {}, text


def _parse_simple_yaml(lines: list[str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key:
            data[key] = value.strip().strip('"').strip("'")
    return data


def _first_body_line(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.lstrip("#").strip()
    return ""


def _clean_scalar(value: str | None) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _normalize_name(name: str) -> str:
    return name.strip().lower()
