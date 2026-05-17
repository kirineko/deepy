from __future__ import annotations

from dataclasses import dataclass


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


@dataclass(frozen=True)
class UiPalette:
    name: str
    saved_theme: str
    muted: str
    accent: str
    success: str
    warning: str
    error: str
    info: str
    assistant: str
    user: str
    system: str
    tool: str
    panel_border: str
    diff_added: str
    diff_added_gutter: str
    diff_added_marker: str
    diff_removed: str
    diff_removed_gutter: str
    diff_removed_marker: str
    diff_context: str
    prompt: str
    placeholder: str
    toolbar_background: str
    toolbar_foreground: str
    toolbar_context: str
    toolbar_separator: str
    toolbar_identity: str
    toolbar_active: str
    toolbar_loaded: str
    toolbar_metadata: str
    markdown_heading: str
    markdown_subheading: str
    markdown_bullet: str
    markdown_number: str
    markdown_quote: str
    markdown_inline_code: str
    markdown_bold: str
    markdown_code_lang: str
    markdown_code_block: str


DARK_PALETTE = UiPalette(
    name="dark",
    saved_theme="dark",
    muted=STYLE_MUTED,
    accent=STYLE_ACCENT,
    success=STYLE_SUCCESS,
    warning=STYLE_WARNING,
    error=STYLE_ERROR,
    info=STYLE_INFO,
    assistant=STYLE_ASSISTANT,
    user=STYLE_USER,
    system=STYLE_SYSTEM,
    tool=STYLE_TOOL,
    panel_border=STYLE_INFO,
    diff_added="#e5e7eb on #1f3d2b",
    diff_added_gutter="#cbd5e1 on #1f3d2b",
    diff_added_marker="bold #86efac on #1f3d2b",
    diff_removed="#e5e7eb on #4a2528",
    diff_removed_gutter="#cbd5e1 on #4a2528",
    diff_removed_marker="bold #fca5a5 on #4a2528",
    diff_context=STYLE_MUTED,
    prompt="ansicyan bold",
    placeholder="#8a90aa",
    toolbar_background="#161821",
    toolbar_foreground="#b7bdd4",
    toolbar_context="#b7bdd4",
    toolbar_separator="#4b5068",
    toolbar_identity="bold #b7bdd4",
    toolbar_active="bold #b7bdd4",
    toolbar_loaded="bold #b7bdd4",
    toolbar_metadata="#b7bdd4",
    markdown_heading="bold bright_cyan",
    markdown_subheading="bold cyan",
    markdown_bullet="bright_blue",
    markdown_number="yellow",
    markdown_quote="dim",
    markdown_inline_code="bold bright_yellow",
    markdown_bold="bold bright_white",
    markdown_code_lang="dim",
    markdown_code_block="bright_white on #1f2430",
)

LIGHT_PALETTE = UiPalette(
    name="light",
    saved_theme="light",
    muted="#4b5563",
    accent="#007c89",
    success="#047857",
    warning="#a16207",
    error="bold #b91c1c",
    info="#1d4ed8",
    assistant="#047857",
    user="#0369a1",
    system="#7e22ce",
    tool="#92400e",
    panel_border="#2563eb",
    diff_added="#064e3b on #ecfdf5",
    diff_added_gutter="#065f46 on #d1fae5",
    diff_added_marker="bold #047857 on #d1fae5",
    diff_removed="#7f1d1d on #fef2f2",
    diff_removed_gutter="#991b1b on #fee2e2",
    diff_removed_marker="bold #b91c1c on #fee2e2",
    diff_context="#374151",
    prompt="#0369a1 bold",
    placeholder="#64748b",
    toolbar_background="#d8d8f2",
    toolbar_foreground="#334155",
    toolbar_context="#334155",
    toolbar_separator="#94a3b8",
    toolbar_identity="bold #334155",
    toolbar_active="bold #334155",
    toolbar_loaded="bold #334155",
    toolbar_metadata="#334155",
    markdown_heading="bold #0f766e",
    markdown_subheading="bold #0369a1",
    markdown_bullet="#2563eb",
    markdown_number="#a16207",
    markdown_quote="#64748b",
    markdown_inline_code="bold #92400e",
    markdown_bold="bold #111827",
    markdown_code_lang="#64748b",
    markdown_code_block="#111827 on #e5e7eb",
)


def get_theme_palette(theme: str = "dark") -> UiPalette:
    return LIGHT_PALETTE if theme == "light" else DARK_PALETTE


def resolve_ui_palette(theme: str = "auto") -> UiPalette:
    if theme == "light":
        return LIGHT_PALETTE
    palette = DARK_PALETTE
    return UiPalette(**{**palette.__dict__, "saved_theme": theme if theme == "auto" else "dark"})


def status_style(ok: bool | None, palette: UiPalette | None = None) -> str:
    palette = palette or DARK_PALETTE
    if ok is True:
        return palette.success
    if ok is False:
        return palette.error
    return palette.warning
