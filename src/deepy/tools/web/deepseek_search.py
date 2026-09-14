"""Independent, bounded DeepSeek Messages search service."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx

from deepy.config import Settings

from ..result import ToolResult

ENDPOINT = "https://api.deepseek.com/anthropic/v1/messages"
MODEL = "deepseek-flash"


def parse_search_response(payload: dict[str, Any], query: str) -> ToolResult:
    blocks = payload.get("content", [])
    if not isinstance(blocks, list):
        return ToolResult.error_result("WebSearch", "Invalid search response.")
    invocations = {
        block.get("id")
        for block in blocks
        if isinstance(block, dict)
        and block.get("type") == "server_tool_use"
        and block.get("name") == "web_search"
        and isinstance(block.get("id"), str)
    }
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    completed: set[str] = set()
    errors: list[str] = []
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "web_search_tool_result":
            continue
        call_id = block.get("tool_use_id")
        if not isinstance(call_id, str) or call_id not in invocations:
            continue
        content = block.get("content")
        if not isinstance(content, list):
            errors.append("Server search tool failed.")
            continue
        completed.add(call_id)
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "web_search_tool_result_error":
                errors.append("Server search tool failed.")
                continue
            if item.get("type") != "web_search_result":
                continue
            url, title = item.get("url"), item.get("title")
            if not isinstance(url, str) or not isinstance(title, str):
                continue
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or url in seen:
                continue
            seen.add(url)
            source = {"title": title[:1000], "url": url}
            if isinstance(item.get("snippet"), str):
                source["snippet"] = item["snippet"][:2000]
            sources.append(source)
    partial = bool(
        errors or invocations - completed or payload.get("stop_reason") not in {None, "end_turn"}
    )
    usage = payload.get("usage")
    metadata = {
        "provider": "deepseek",
        "backend": "deepseek",
        "model": MODEL,
        "query": query,
        "sources": sources[:10],
        "resultCount": min(len(sources), 10),
        "status": "partial" if partial else "complete" if sources else "empty",
        "usage": usage if isinstance(usage, dict) else None,
    }
    if not completed:
        return ToolResult.error_result(
            "WebSearch", "No successful server search record was returned.", metadata=metadata
        )
    if partial and not sources:
        return ToolResult.error_result(
            "WebSearch", "Search did not complete successfully.", metadata=metadata
        )
    lines = [f"Web search results for: {query}"]
    if partial:
        lines.append("Partial results: search did not complete.")
    if not sources:
        lines.append("Search completed with no results.")
    for source in sources[:10]:
        lines.extend([source["title"], source["url"]])
        if source.get("snippet"):
            lines.append(source["snippet"])
    return ToolResult.ok_result("WebSearch", "\n".join(lines), metadata=metadata)


async def search(settings: Settings, query: str) -> ToolResult:
    key = settings.provider_keys.get("deepseek")
    if not key and settings.model.provider == "deepseek":
        key = settings.model.api_key
    if not key:
        return ToolResult.error_result(
            "WebSearch",
            "Configure DEEPSEEK_API_KEY or the DeepSeek provider profile to use built-in search.",
        )
    request = {
        "model": MODEL,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": f"Perform a web search for the query: {query}"}],
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
    }
    try:
        async with asyncio.timeout(60), httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                ENDPOINT,
                json=request,
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                },
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Invalid response object")
        return parse_search_response(payload, query)
    except (httpx.HTTPError, TimeoutError, ValueError) as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        return ToolResult.error_result(
            "WebSearch",
            f"DeepSeek search failed ({status or type(exc).__name__}). Please try again.",
        )
