"""Opt-in application FunctionTool search and native web-fetch rejection probes."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx
from agents import Agent, Runner

from deepy.config import Settings
from deepy.llm.provider import build_provider_bundle
from deepy.tools.agents import build_function_tools
from deepy.tools.builtin import ToolRuntime
from deepy.tools.web.deepseek_search import ENDPOINT, MODEL


async def main(provider: str) -> None:
    settings = Settings.from_mapping({"active_provider": provider}, env=os.environ)
    if not settings.model.api_key or not settings.provider_keys.get("deepseek"):
        print(json.dumps({"status": "missing_key", "provider": provider}))
        return
    usage = []
    runtime = ToolRuntime(cwd=Path.cwd(), settings=settings, record_search_usage=usage.append)
    bundle = build_provider_bundle(settings)
    try:
        async with asyncio.timeout(120):
            result = await Runner.run(
                Agent(
                    name="search-probe",
                    model=bundle.model,
                    model_settings=bundle.model_settings,
                    tools=build_function_tools(runtime, include_tools={"WebSearch"}),
                ),
                "Call WebSearch exactly once to find the official Python documentation. Return one source URL from the tool result.",
                max_turns=3,
            )
        print(
            json.dumps(
                {
                    "provider": provider,
                    "status": "passed"
                    if usage and usage[0].get("resultCount", 0) > 0
                    else "no_search_evidence",
                    "responses": len(result.raw_responses),
                    "search_provider": usage[0].get("provider") if usage else None,
                    "source_count": usage[0].get("resultCount") if usage else 0,
                    "usage": usage[0].get("usage") if usage else None,
                }
            ),
            flush=True,
        )
    except Exception as exc:
        print(
            json.dumps(
                {"provider": provider, "status": "failed", "error_type": type(exc).__name__}
            ),
            flush=True,
        )
    finally:
        await bundle.client.close()
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            ENDPOINT,
            headers={
                "x-api-key": settings.provider_keys["deepseek"],
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": MODEL,
                "max_tokens": 64,
                "messages": [{"role": "user", "content": "Fetch https://docs.python.org/"}],
                "tools": [{"type": "web_fetch_20250910", "name": "web_fetch"}],
            },
        )
        print(
            json.dumps(
                {
                    "probe": "native_web_fetch",
                    "http_status": response.status_code,
                    "status": "rejected" if response.status_code == 400 else "needs_review",
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument(
        "--provider", choices=["deepseek", "mimo", "kimi", "cli_proxy"], default="mimo"
    )
    args = parser.parse_args()
    asyncio.run(main(args.provider))
