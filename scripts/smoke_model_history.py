"""Opt-in, small Responses replay smoke. No maximum-context or web claims.

DEEPY_LIVE_CONTEXT=1 uv run python scripts/smoke_model_history.py
Uses standard provider key environment variables; never reads/writes user config.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from tempfile import TemporaryDirectory
from pathlib import Path

from agents import Agent, Runner, function_tool

from deepy.config import Settings
from deepy.config.model_limits import MODEL_LIMITS
from deepy.llm.provider import build_provider_bundle
from deepy.llm.multimodal import model_supports_image_input
from deepy.sessions import DeepySession
from deepy.utils import json

PIXEL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKElEQVR4nO3NsQ0AAAzCMP5/un0CNkuZ41wybXsHAAAAAAAAAAAAxR4yw/wuPL6QkAAAAABJRU5ErkJggg=="


def safe_error(exc: Exception, key: str) -> str:
    detail = str(getattr(exc, "message", type(exc).__name__))
    return detail.replace(key, "[redacted]")[:500]


async def main() -> None:
    if os.environ.get("DEEPY_LIVE_CONTEXT") != "1":
        raise SystemExit("Opt in with DEEPY_LIVE_CONTEXT=1; this makes small paid API requests.")
    with TemporaryDirectory(prefix="deepy-history-smoke-") as directory:
        root = Path(directory)
        session = DeepySession.create(root, deepy_home=root / "home")
        await session.add_items([
            {"role": "user", "content": "Remember the marker: blue-17."},
            {"type": "function_call", "call_id": "call_smoke", "name": "echo", "arguments": '{"value":"blue-17"}'},
            {"type": "function_call_output", "call_id": "call_smoke", "output": "blue-17"},
        ])
        @function_tool
        def echo(value: str) -> str:
            return value

        for provider, model in MODEL_LIMITS:
            selected = os.environ.get("DEEPY_LIVE_MODELS", "").split(",")
            if selected != [""] and model not in selected:
                continue
            mode = "disabled" if provider == "mimo" else "low" if provider in {"kimi", "cli_proxy"} else "none"
            settings = Settings.from_mapping({"active_provider": provider, "providers": {
                provider: {"model": model, "reasoning": mode}}}, env=os.environ)
            if not settings.model.api_key:
                print(json.dumps({"provider": provider, "model": model, "status": "skipped-missing-key"}), flush=True)
                continue
            bundle = build_provider_bundle(settings)
            try:
                agent = Agent(name="Replay smoke", instructions="Reply briefly. Do not call tools; the previous results are already complete.",
                              model=bundle.model, tools=[echo],
                              model_settings=replace(bundle.model_settings, max_tokens=2048,
                                                     tool_choice="auto" if provider == "kimi" else "none"))
                # Same durable text/tool history is replayed through successive targets.
                result = await asyncio.wait_for(Runner.run(agent, "What marker did echo return?", session=session, max_turns=2), timeout=60)
                text_ok = "blue-17" in str(result.final_output)
                image_ok = None
                if model_supports_image_input(provider, model):
                    image_result = await asyncio.wait_for(Runner.run(agent, [{"role": "user", "content": [
                        {"type": "input_text", "text": "Confirm you received this image in a short sentence."},
                        {"type": "input_image", "image_url": PIXEL},
                    ]}], max_turns=2), timeout=60)
                    image_ok = bool(str(image_result.final_output).strip())
                print(json.dumps({"provider": provider, "model": model, "history_tool_replay": text_ok,
                                  "image_response": image_ok, "status": "passed" if text_ok else "failed"}), flush=True)
            except Exception as exc:
                # Avoid logging SDK request bodies, endpoints or credentials.
                print(json.dumps({"provider": provider, "model": model, "status": "failed", "error_type": type(exc).__name__, "detail": safe_error(exc, settings.model.api_key)}), flush=True)
            finally:
                await bundle.client.close()


if __name__ == "__main__":
    asyncio.run(main())
