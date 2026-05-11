from __future__ import annotations

from deepy.skills import SkillInfo
from deepy.ui.prompt_buffer import PromptBufferState


IMAGE_ATTACHMENT_CLEAR_HINT = "ctrl+x clear images"


def format_image_attachment_status(count: int) -> str:
    if count <= 0:
        return ""
    suffix = "" if count == 1 else "s"
    return f"📎 {count} image{suffix} attached"


def format_selected_skills_status(skills: list[SkillInfo]) -> str:
    names = [skill.name for skill in skills if skill.name]
    if not names:
        return ""
    return f"⚡ {', '.join(names)}"


def is_skill_selected(skills: list[SkillInfo], skill: SkillInfo) -> bool:
    return any(item.name == skill.name for item in skills)


def add_unique_skill(skills: list[SkillInfo], skill: SkillInfo) -> list[SkillInfo]:
    if is_skill_selected(skills, skill):
        return skills
    return [*skills, skill]


def toggle_skill_selection(skills: list[SkillInfo], skill: SkillInfo) -> list[SkillInfo]:
    if is_skill_selected(skills, skill):
        return [item for item in skills if item.name != skill.name]
    return [*skills, skill]


def remove_current_slash_token(state: PromptBufferState) -> PromptBufferState:
    start = state.cursor
    while start > 0 and not state.text[start - 1].isspace():
        start -= 1

    token = state.text[start : state.cursor]
    if not token.startswith("/"):
        return state

    text = f"{state.text[:start]}{state.text[state.cursor:]}"
    return PromptBufferState(text=text, cursor=start)


def is_clear_image_attachments_shortcut(input_text: str, *, ctrl: bool) -> bool:
    return ctrl and input_text in {"x", "X"}


def render_buffer_with_cursor(
    state: PromptBufferState,
    is_focused: bool,
    placeholder: str | None = None,
) -> str:
    text = state.text or ""
    cursor = min(max(state.cursor, 0), len(text))
    before = text[:cursor]
    at = text[cursor] if cursor < len(text) else None
    after = text[cursor + 1 :]

    if not text and placeholder:
        return _dim(f"  {placeholder}")

    if not is_focused:
        return f"{text} " if text.endswith("\n") else text

    if at is None:
        return before + _inverse(" ")
    if at == "\n":
        return before + _inverse(" ") + "\n" + after
    return before + _inverse(at) + after


def _inverse(value: str) -> str:
    return f"\x1b[7m{value}\x1b[0m"


def _dim(value: str) -> str:
    return f"\x1b[2m{value}\x1b[0m"
