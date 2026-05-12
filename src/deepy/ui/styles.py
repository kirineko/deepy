from __future__ import annotations


STYLE_MUTED = "dim"
STYLE_ACCENT = "bright_cyan"
STYLE_SUCCESS = "green"
STYLE_WARNING = "yellow"
STYLE_ERROR = "bold red"
STYLE_INFO = "bright_blue"
STYLE_ASSISTANT = "green"
STYLE_USER = "cyan"
STYLE_SYSTEM = "magenta"
STYLE_TOOL = "yellow"


def status_style(ok: bool | None) -> str:
    if ok is True:
        return STYLE_SUCCESS
    if ok is False:
        return STYLE_ERROR
    return STYLE_WARNING
