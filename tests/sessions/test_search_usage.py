from deepy.sessions.session import DeepySession
from deepy.sessions.index import list_session_entries
from deepy.ui.shared.render.exit_summary import build_exit_summary_text


def test_search_usage_does_not_advance_chat_context(tmp_path):
    root = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepySession.create(root, deepy_home=home, session_id="search-test")
    session.record_usage({"input_tokens": 100, "output_tokens": 20})
    previous = list_session_entries(root, home)[0]
    session.record_web_search_usage(
        {
            "usage": {
                "input_tokens": 200,
                "cache_read_input_tokens": 50,
                "output_tokens": 10,
                "server_tool_use": {"web_search_requests": 1},
            }
        }
    )
    entry = list_session_entries(root, home)[0]
    assert entry.latest_context_window_tokens == previous.latest_context_window_tokens
    assert entry.usage["total_tokens"] == 380
    assert entry.web_search_usage["total_tokens"] == 260
    assert entry.web_search_usage["provider"] == "deepseek"
    assert entry.web_search_usage["search_requests"] == 1
    assert "web search" in build_exit_summary_text(session=entry)
    assert "deepseek/deepseek-flash" in build_exit_summary_text(session=entry)
    session.record_web_search_usage({"usage": None})
    assert list_session_entries(root, home)[0].usage == entry.usage


def test_suggestion_usage_keeps_actual_models_after_provider_switch(tmp_path):
    root, home = tmp_path / "project", tmp_path / "home"
    session = DeepySession.create(root, deepy_home=home, session_id="suggestions")
    session.record_input_suggestion_usage(
        {"input_tokens": 10, "output_tokens": 2}, model="deepseek-flash"
    )
    session.record_input_suggestion_usage({"input_tokens": 20, "output_tokens": 3}, model="kimi-k3")
    entry = list_session_entries(root, home)[0]
    buckets = entry.input_suggestion_usage["by_model"]
    assert buckets["deepseek/deepseek-flash"]["total_tokens"] == 12
    assert buckets["kimi/kimi-k3"]["total_tokens"] == 23
    summary = build_exit_summary_text(session=entry)
    assert "deepseek/deepseek-flash" in summary and "kimi/kimi-k3" in summary
    assert not entry.usage
