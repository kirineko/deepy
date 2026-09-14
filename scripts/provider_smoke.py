"""Opt-in live Responses probe. Credentials are read only from provider environments."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import replace

from agents import Agent, Runner, function_tool

from deepy.config import Settings
from deepy.config.providers import PROVIDER_CATALOG
from deepy.llm.provider import build_provider_bundle


@function_tool
def echo_probe(value: str) -> str:
    """Echo a probe value without side effects."""
    return "verified-" + value


async def probe(
    provider: str, model: str, reasoning: str | None = None, stream: bool = False
) -> None:
    settings = Settings.from_mapping(
        {"active_provider": provider, "providers": {provider: {"model": model}}}, env=os.environ
    )
    if not settings.model.api_key:
        print(
            json.dumps({"provider": provider, "model": model, "status": "missing_key"}), flush=True
        )
        return
    effort = reasoning or ("low" if provider == "kimi" else "none")
    settings = replace(
        settings,
        model=replace(settings.model, thinking=effort != "none", reasoning_effort=effort),
    )
    bundle = build_provider_bundle(settings)
    try:
        async with asyncio.timeout(60):
            result = (Runner.run_streamed if stream else Runner.run)(
                Agent(
                    name="probe",
                    model=bundle.model,
                    model_settings=bundle.model_settings,
                    tools=[echo_probe],
                ),
                'You MUST call echo_probe with value "probe-ok". Its result is not known until you call it. Return exactly the tool result; do not answer from your own knowledge.',
                max_turns=3,
            )
            if stream:
                async for _ in result.stream_events():
                    pass
            else:
                result = await result
        executed = any(item.type == "tool_call_output_item" for item in result.new_items)
        print(
            json.dumps(
                {
                    "provider": provider,
                    "model": model,
                    "status": "passed"
                    if executed and "verified-probe-ok" in result.final_output
                    else "no_tool_evidence",
                    "responses": len(result.raw_responses),
                    "item_types": [item.type for item in result.new_items],
                    "preview": str(result.final_output)[:400],
                }
            ),
            flush=True,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "provider": provider,
                    "model": model,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "http_status": getattr(exc, "status_code", None),
                    "message": str(exc).replace(settings.model.api_key, "[redacted]")[:600],
                }
            ),
            flush=True,
        )
    finally:
        await bundle.client.close()


async def main(
    provider_filter: str | None,
    model_filter: str | None = None,
    reasoning: str | None = None,
    stream: bool = False,
) -> None:
    for info in PROVIDER_CATALOG:
        if provider_filter and provider_filter != info.id:
            continue
        for model in info.models:
            if model_filter and model.name != model_filter:
                continue
            await probe(info.id, model.name, reasoning, stream)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=[info.id for info in PROVIDER_CATALOG])
    parser.add_argument("--model")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--reasoning", choices=["none", "low", "medium", "high", "max", "xhigh"])
    parser.add_argument(
        "--live", action="store_true", required=True, help="Authorize live paid model calls"
    )
    args = parser.parse_args()
    asyncio.run(main(args.provider, args.model, args.reasoning, args.stream))
