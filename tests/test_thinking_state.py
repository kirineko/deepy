from __future__ import annotations

from deepy.ui.thinking_state import find_expanded_thinking_id


def _message(message_id: str, role: str, *, as_thinking: bool = False) -> dict[str, object]:
    message: dict[str, object] = {
        "id": message_id,
        "sessionId": "s",
        "role": role,
        "content": "",
        "contentParams": None,
        "messageParams": None,
        "compacted": False,
        "visible": True,
        "createTime": "2026-04-28T00:00:00.000Z",
        "updateTime": "2026-04-28T00:00:00.000Z",
    }
    if as_thinking:
        message["meta"] = {"asThinking": True}
    return message


def test_find_expanded_thinking_id_returns_none_on_empty_list():
    assert find_expanded_thinking_id([]) is None


def test_find_expanded_thinking_id_returns_only_thinking_id_without_final_reply():
    messages = [
        _message("user", "user"),
        _message("a-1", "assistant", as_thinking=True),
    ]

    assert find_expanded_thinking_id(messages) == "a-1"


def test_find_expanded_thinking_id_picks_latest_thinking_id():
    messages = [
        _message("a-1", "assistant", as_thinking=True),
        _message("tool", "tool"),
        _message("a-2", "assistant", as_thinking=True),
    ]

    assert find_expanded_thinking_id(messages) == "a-2"


def test_find_expanded_thinking_id_returns_none_after_non_thinking_assistant_reply():
    messages = [
        _message("a-1", "assistant", as_thinking=True),
        _message("a-final", "assistant"),
    ]

    assert find_expanded_thinking_id(messages) is None


def test_find_expanded_thinking_id_picks_thinking_id_after_last_final_reply():
    messages = [
        _message("a-1", "assistant", as_thinking=True),
        _message("a-final", "assistant"),
        _message("a-2", "assistant", as_thinking=True),
        _message("a-3", "assistant", as_thinking=True),
    ]

    assert find_expanded_thinking_id(messages) == "a-3"
