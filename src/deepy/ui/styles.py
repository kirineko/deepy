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
    diff_removed: str
    diff_removed_gutter: str
    diff_context: str
    write_preview_gutter: str
    write_preview_content: str
    write_preview_removed: str
    prompt: str
    placeholder: str
    toolbar_background: str
    toolbar_foreground: str
    toolbar_context: str
    toolbar_separator: str
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
    diff_added="#e5e7eb on #14532d",
    diff_added_gutter="#cbd5e1 on #14532d",
    diff_removed="#e5e7eb on #7f1d1d",
    diff_removed_gutter="#cbd5e1 on #7f1d1d",
    diff_context=STYLE_MUTED,
    write_preview_gutter="#94a3b8 on #1f2937",
    write_preview_content="#d7def8 on #1f2937",
    write_preview_removed="#fecaca on #7f1d1d",
    prompt="ansicyan bold",
    placeholder="#8a90aa",
    toolbar_background="#161821",
    toolbar_foreground="#a6adc8",
    toolbar_context="#a6adc8",
    toolbar_separator="#4b5068",
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
    diff_added="#064e3b on #dcfce7",
    diff_added_gutter="#065f46 on #bbf7d0",
    diff_removed="#7f1d1d on #fee2e2",
    diff_removed_gutter="#991b1b on #fecaca",
    diff_context="#374151",
    write_preview_gutter="#475569 on #e2e8f0",
    write_preview_content="#111827 on #f8fafc",
    write_preview_removed="#7f1d1d on #fee2e2",
    prompt="#0369a1 bold",
    placeholder="#64748b",
    toolbar_background="#e2e8f0",
    toolbar_foreground="#0f172a",
    toolbar_context="#047857 bold",
    toolbar_separator="#64748b",
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
