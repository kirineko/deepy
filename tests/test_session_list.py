from __future__ import annotations

from deepy.ui.session_list import format_session_title
from deepy.ui.session_list import max_visible_sessions
from deepy.ui.session_list import move_session_selection
from deepy.ui.session_list import session_list_window
from deepy.ui.session_list import visible_sessions


def test_format_session_title_replaces_newlines_with_spaces():
    assert (
        format_session_title("first line\nsecond line\r\nthird")
        == "first line second line third"
    )


def test_format_session_title_truncates_after_normalizing_whitespace():
    assert format_session_title("one\n two   three", 10) == "one two th…"


def test_format_session_title_uses_untitled_for_blank_values():
    assert format_session_title(None) == "Untitled"
    assert format_session_title("   ") == "Untitled"


def test_max_visible_sessions_matches_reference_layout_math():
    assert max_visible_sessions(5) == 1
    assert max_visible_sessions(14) == 2
    assert max_visible_sessions(30) == 7
    assert max_visible_sessions(80) == 7


def test_session_list_window_clamps_index_and_scrolls_to_selection():
    assert session_list_window(session_count=0, selected_index=10, rows=30).safe_index == 0

    window = session_list_window(session_count=10, selected_index=9, rows=14)

    assert window.safe_index == 9
    assert window.max_visible == 2
    assert window.scroll_offset == 8


def test_visible_sessions_returns_current_scroll_window():
    sessions = ["s0", "s1", "s2", "s3", "s4"]

    assert visible_sessions(sessions, selected_index=3, rows=14) == ["s2", "s3"]


def test_move_session_selection_handles_navigation_actions():
    assert move_session_selection(selected_index=2, session_count=5, action="up", rows=30) == 1
    assert move_session_selection(selected_index=2, session_count=5, action="down", rows=30) == 3
    assert move_session_selection(selected_index=4, session_count=5, action="down", rows=30) == 4
    assert move_session_selection(selected_index=4, session_count=10, action="page_up", rows=14) == 2
    assert move_session_selection(selected_index=4, session_count=10, action="page_down", rows=14) == 6
    assert move_session_selection(selected_index=4, session_count=10, action="home", rows=14) == 0
    assert move_session_selection(selected_index=4, session_count=10, action="end", rows=14) == 9
    assert move_session_selection(selected_index=4, session_count=10, action="unknown", rows=14) == 4
