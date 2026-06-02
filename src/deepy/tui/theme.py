from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TuiThemeOption:
    name: str
    label: str
    description: str
    shared_theme: str | None = None


TUI_DARK_THEME = "tokyo-night"
TUI_LIGHT_THEME = "solarized-light"
TUI_THEME_BY_UI_THEME = {
    "dark": TUI_DARK_THEME,
    "light": TUI_LIGHT_THEME,
}
TUI_TEXTUAL_THEME_OPTIONS: tuple[TuiThemeOption, ...] = (
    TuiThemeOption("dark", "dark", f"Shared dark -> {TUI_DARK_THEME}", shared_theme="dark"),
    TuiThemeOption("light", "light", f"Shared light -> {TUI_LIGHT_THEME}", shared_theme="light"),
    TuiThemeOption("nord", "nord", "Calm dark theme"),
    TuiThemeOption("tokyo-night", "tokyo-night", "Default high-contrast dark theme"),
    TuiThemeOption("catppuccin-mocha", "catppuccin-mocha", "Warm dark theme"),
    TuiThemeOption("gruvbox", "gruvbox", "Earth-tone dark theme"),
    TuiThemeOption("monokai", "monokai", "Classic high-contrast dark theme"),
    TuiThemeOption("solarized-light", "solarized-light", "Balanced light theme"),
    TuiThemeOption("catppuccin-latte", "catppuccin-latte", "Soft light theme"),
    TuiThemeOption("atom-one-light", "atom-one-light", "Clean light theme"),
)
TUI_TEXTUAL_THEME_NAMES = frozenset(
    option.name for option in TUI_TEXTUAL_THEME_OPTIONS if option.shared_theme is None
)


def textual_theme_for_ui_theme(theme: str, textual_theme: str | None = None) -> str:
    """Map Deepy's shared UI theme contract to a Textual built-in theme."""

    if textual_theme and textual_theme in TUI_TEXTUAL_THEME_NAMES:
        return textual_theme
    return TUI_THEME_BY_UI_THEME.get(theme, TUI_DARK_THEME)


def is_supported_textual_theme(theme: str) -> bool:
    return theme in TUI_TEXTUAL_THEME_NAMES


def textual_theme_option(theme: str) -> TuiThemeOption | None:
    return next((option for option in TUI_TEXTUAL_THEME_OPTIONS if option.name == theme), None)
