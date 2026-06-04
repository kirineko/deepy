from __future__ import annotations

from dataclasses import dataclass

from deepy.ui.shared.session.session_list import format_session_title
from deepy.ui.shared.session.session_list import resolve_session_selection


@dataclass(frozen=True)
class Entry:
    id: str
    updated_at: int = 100
    active_tokens: int = 42


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


def test_resolve_session_selection_accepts_number_exact_id_and_unique_prefix():
    entries = [Entry("abc123"), Entry("def456")]

    assert resolve_session_selection(entries, "2") == entries[1]
    assert resolve_session_selection(entries, "abc123") == entries[0]
    assert resolve_session_selection(entries, "def") == entries[1]
    assert resolve_session_selection(entries, "missing") is None
    assert resolve_session_selection([Entry("abc1"), Entry("abc2")], "abc") is None
