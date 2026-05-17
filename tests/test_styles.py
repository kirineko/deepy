from __future__ import annotations

from deepy.ui.styles import DARK_PALETTE
from deepy.ui.styles import LIGHT_PALETTE
from deepy.ui.styles import resolve_ui_palette
from deepy.ui.styles import status_style


def test_theme_palettes_expose_required_roles():
    for palette in (DARK_PALETTE, LIGHT_PALETTE):
        assert palette.muted
        assert palette.accent
        assert palette.assistant
        assert palette.user
        assert palette.tool
        assert palette.diff_added
        assert palette.diff_added_marker
        assert palette.diff_removed
        assert palette.diff_removed_marker
        assert palette.toolbar_background
        assert palette.toolbar_identity
        assert palette.toolbar_active
        assert palette.toolbar_loaded
        assert palette.toolbar_metadata


def test_resolve_ui_palette_uses_dark_fallback_for_auto():
    palette = resolve_ui_palette("auto")

    assert palette.name == "dark"
    assert palette.saved_theme == "auto"


def test_light_toolbar_background_uses_completed_prompt_tint():
    assert LIGHT_PALETTE.toolbar_background == "#d8d8f2"


def test_status_style_uses_palette_roles():
    assert status_style(True, LIGHT_PALETTE) == LIGHT_PALETTE.success
    assert status_style(False, LIGHT_PALETTE) == LIGHT_PALETTE.error
    assert status_style(None, LIGHT_PALETTE) == LIGHT_PALETTE.warning


def test_toolbar_roles_use_coordinated_single_foreground():
    for palette in (DARK_PALETTE, LIGHT_PALETTE):
        assert palette.toolbar_context == palette.toolbar_foreground
        assert palette.toolbar_metadata == palette.toolbar_foreground
        assert palette.toolbar_loaded == f"bold {palette.toolbar_foreground}"
        assert palette.toolbar_identity == f"bold {palette.toolbar_foreground}"
        assert palette.toolbar_active == f"bold {palette.toolbar_foreground}"
        assert palette.toolbar_separator != palette.toolbar_foreground
