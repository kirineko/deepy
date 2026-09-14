import asyncio

import pytest

from deepy.config import Settings
from deepy.tools.web.deepseek_search import parse_search_response, search


def payload(content=None, stop="end_turn"):
    return {
        "content": [
            {"type": "server_tool_use", "name": "web_search", "id": "search_1"},
            {
                "type": "web_search_tool_result",
                "tool_use_id": "search_1",
                "content": [] if content is None else content,
            },
        ],
        "stop_reason": stop,
        "usage": {
            "input_tokens": 12,
            "output_tokens": 3,
            "server_tool_use": {"web_search_requests": 1},
        },
    }


def test_actual_search_results_and_opaque_content():
    source = {
        "type": "web_search_result",
        "url": "https://example.com",
        "title": "Example",
        "encrypted_content": "opaque-secret",
    }
    result = parse_search_response(payload([source, source]), "query")
    assert result.ok
    assert result.metadata["resultCount"] == 1
    assert result.metadata["sources"] == [{"url": "https://example.com", "title": "Example"}]
    assert "opaque-secret" not in result.to_json()


def test_empty_partial_and_missing_record_are_distinct():
    assert parse_search_response(payload(), "q").metadata["status"] == "empty"
    assert not parse_search_response(
        {"content": [{"type": "text", "text": "I searched the web"}]}, "q"
    ).ok
    error = payload({"type": "web_search_tool_result_error", "error_code": "unavailable"})
    assert not parse_search_response(error, "q").ok
    partial = payload(
        [{"type": "web_search_result", "title": "Example", "url": "https://example.com"}],
        stop="max_tokens",
    )
    result = parse_search_response(partial, "q")
    assert result.ok and result.metadata["status"] == "partial"


def test_unrelated_tool_result_does_not_prove_search():
    data = payload()
    data["content"][1]["tool_use_id"] = "wrong"
    assert not parse_search_response(data, "q").ok


@pytest.mark.asyncio
async def test_missing_deepseek_key_is_search_only():
    settings = Settings.from_mapping({"active_provider": "mimo"}, env={"MIMO_API_KEY": "mimo-key"})
    result = await search(settings, "query")
    assert not result.ok and "DEEPSEEK_API_KEY" in result.error
    assert settings.model.api_key == "mimo-key"


@pytest.mark.asyncio
async def test_search_uses_independent_key_and_cancels(monkeypatch):
    calls = []
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    monkeypatch.setattr("deepy.tools.web.deepseek_search.httpx.AsyncClient", Client)
    settings = Settings.from_mapping(
        {"active_provider": "kimi"},
        env={"KIMI_API_KEY": "kimi-key", "DEEPSEEK_API_KEY": "search-key"},
    )
    task = asyncio.create_task(search(settings, "query"))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set() and len(calls) == 1
    url, request = calls[0]
    assert url == "https://api.deepseek.com/anthropic/v1/messages"
    assert request["headers"]["x-api-key"] == "search-key"
    assert request["json"]["tools"][0]["max_uses"] == 3
    assert request["json"]["model"] == "deepseek-flash"


@pytest.mark.parametrize("provider", ["deepseek", "mimo", "kimi", "cli_proxy"])
@pytest.mark.asyncio
async def test_builtin_function_search_integration(tmp_path, monkeypatch, provider):
    import json
    from deepy.tools.builtin import ToolRuntime
    from deepy.tools.agents import build_function_tools

    calls, usage = [], []

    async def fake_search(settings, query):
        calls.append((settings.model.provider, query))
        return parse_search_response(
            payload(
                [{"type": "web_search_result", "title": "Example", "url": "https://example.com"}]
            ),
            query,
        )

    monkeypatch.setattr("deepy.tools.runtime.web.search", fake_search)
    settings = Settings.from_mapping({"active_provider": provider})
    runtime = ToolRuntime(cwd=tmp_path, settings=settings, record_search_usage=usage.append)
    tool = next(
        t
        for t in build_function_tools(
            runtime, preferred_mcp_web_search_tools=["mcp_tavily__tavily_search"]
        )
        if t.name == "WebSearch"
    )
    assert "mcp_tavily__tavily_search" in tool.description and "fails" in tool.description
    result = json.loads(await tool.on_invoke_tool(None, '{"query":"example"}'))
    assert result["ok"] and result["metadata"]["provider"] == "deepseek"
    assert calls == [(provider, "example")] and len(usage) == 1
    assert runtime.running_processes == {}


def test_source_limit_preserves_upstream_search_count():
    data = payload(
        [
            {"type": "web_search_result", "title": str(i), "url": f"https://example.com/{i}"}
            for i in range(15)
        ]
    )
    data["usage"]["server_tool_use"]["web_search_requests"] = 3
    result = parse_search_response(data, "query")
    assert result.ok and len(result.metadata["sources"]) == 10
    assert result.metadata["usage"]["server_tool_use"]["web_search_requests"] == 3


@pytest.mark.asyncio
async def test_timeout_is_not_retried(monkeypatch):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] == 60

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            calls.append(url)
            raise TimeoutError

    monkeypatch.setattr("deepy.tools.web.deepseek_search.httpx.AsyncClient", Client)
    result = await search(Settings.from_mapping({}, env={"DEEPSEEK_API_KEY": "test"}), "query")
    assert not result.ok and len(calls) == 1
