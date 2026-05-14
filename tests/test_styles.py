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


def test_resolve_ui_palette_uses_dark_fallback_for_auto():
    palette = resolve_ui_palette("auto")

    assert palette.name == "dark"
    assert palette.saved_theme == "auto"


def test_status_style_uses_palette_roles():
    assert status_style(True, LIGHT_PALETTE) == LIGHT_PALETTE.success
    assert status_style(False, LIGHT_PALETTE) == LIGHT_PALETTE.error
    assert status_style(None, LIGHT_PALETTE) == LIGHT_PALETTE.warning
