"""Bounded summary planning; no history writes until the caller commits."""
from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any, Callable, Awaitable

from deepy.config import Settings
from deepy.prompts.compact import build_compact_prompt, build_compact_summary_message
from deepy.sessions.history_state import read_history_state, record_summary_usage
from deepy.usage import TokenUsage, merge_usage
from deepy.todos import todo_state_prompt_text
from .history_projection import history_groups, model_identity
from .multimodal import items_contain_image_content, model_supports_image_input
from .request_budget import estimate_request_value
from .response_images import normalize_response_images

MAX_SUMMARY_CALLS = 32
SUMMARY_TIMEOUT_SECONDS = 60


def summary_input(items: list[dict[str, Any]], focus: str | None = None,
                  todo_context: str | None = None) -> Any:
    normalized = normalize_response_images(items)
    images: list[dict[str, Any]] = []

    def redact(value: Any) -> Any:
        if isinstance(value, dict):
            if value.get("type") == "input_image":
                images.append(value)
                return {"type": "image_reference", "index": len(images)}
            return {key: redact(part) for key, part in value.items()}
        if isinstance(value, list):
            return [redact(part) for part in value]
        return value

    prompt = build_compact_prompt(redact(normalized), focus_instruction=focus,
                                  todo_context=todo_context)
    if not images:
        return prompt
    return [{"role": "user", "content": [{"type": "input_text", "text": prompt}, *images]}]


async def summarize_bounded(
    items: list[dict[str, Any]], settings: Settings, *, session: Any,
    summarize: Callable[..., Awaitable[tuple[str, TokenUsage]]],
    provider: Any = None, focus: str | None = None, allow_image_reduction: bool = False,
    announce: Callable[[str], None] | None = None,
    **kwargs: Any,
) -> tuple[str, TokenUsage]:
    from .compaction import ContextCompactionError

    candidates = [settings]
    source = read_history_state(session).get("last_successful_model", {})
    if source:
        model = settings.model_for_provider(source["provider"])
        model = replace(model, name=source["model"])
        if model.api_key and model.base_url.rstrip("/") == source.get("endpoint"):
            candidates.append(replace(settings, model=model))
    has_images = items_contain_image_content(normalize_response_images(items))
    target_images = model_supports_image_input(settings.model.provider, settings.model.name)
    if has_images and not target_images and not allow_image_reduction:
        raise ContextCompactionError("Image history is preserved. Switch back or explicitly use /compact --for-model for a potentially lossy text summary.")
    async def cancellable_call(group: Any, candidate: Any) -> tuple[str, TokenUsage]:
        from .work_boundary import interrupt_check
        check = interrupt_check.get()
        if check and check():
            raise asyncio.CancelledError
        task = asyncio.ensure_future(summarize(
            group, candidate, provider=provider if candidate is settings else None,
            focus_instruction=focus, todo_state=session.todo_state(), **kwargs))
        try:
            if not check:
                return await task
            while not task.done():
                if check():
                    raise asyncio.CancelledError
                await asyncio.wait({task}, timeout=0.05)
            return task.result()
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    calls = 0
    total = TokenUsage()

    def fits(group: list[dict[str, Any]], candidate: Settings) -> bool:
        from .multimodal import ImageAttachmentError
        from .summary_size import summary_body_fits
        try:
            request_input = normalize_response_images(
                summary_input(group, focus, todo_state_prompt_text(session.todo_state()))
            )
        except ImageAttachmentError:
            return False
        if not summary_body_fits(
            request_input, prefix=kwargs.get("prefix_snapshot"),
            tools=kwargs.get("prefix_tools"), mcp_servers=kwargs.get("prefix_mcp_servers"),
        ):
            return False
        if items_contain_image_content(normalize_response_images(group)) and not model_supports_image_input(candidate.model.provider, candidate.model.name):
            return False
        limits = candidate.model_limits
        # Include focus/todo and the actual compactor prefix. Tools remain disabled.
        prefix = kwargs.get("prefix_snapshot")
        overhead = estimate_request_value(getattr(prefix, "system_instructions", "")) + 1024
        overhead += estimate_request_value(getattr(prefix, "tools", ()))
        overhead += estimate_request_value(getattr(prefix, "mcp_tools", ()))
        summary_reserve = max(limits.reserve_floor, min(8192, limits.output_tokens) + 4096)
        return estimate_request_value(request_input) + overhead + summary_reserve < limits.window_tokens

    async def call(group: list[dict[str, Any]], candidate: Settings) -> str:
        nonlocal calls, total
        if calls >= MAX_SUMMARY_CALLS:
            raise ContextCompactionError("History preparation reached its 32-request limit; original history is intact.")
        calls += 1
        if announce:
            announce(f"Summarizing with {candidate.model.provider}/{candidate.model.name} ({calls}/32).")
        summary, usage = await asyncio.wait_for(cancellable_call(group, candidate), timeout=SUMMARY_TIMEOUT_SECONDS)
        record_summary_usage(session, usage, model_identity(candidate.model.provider, candidate.model.name, candidate.model.base_url))
        total = merge_usage(total, usage)
        return summary

    async def reduce(groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        summaries = []
        pending: list[dict[str, Any]] = []
        for group in groups:
            if fits([*pending, *group], settings):
                pending.extend(group)
                continue
            if pending:
                summaries.append(build_compact_summary_message(await call(pending, settings)))
                pending = []
            candidate = next((candidate for candidate in candidates if fits(group, candidate)), None)
            if candidate is None:
                raise ContextCompactionError("An indivisible history/tool group cannot fit any eligible summarizer. Originals are intact; switch back or start a new session.")
            if candidate is settings:
                pending = list(group)
            else:
                summaries.append(build_compact_summary_message(await call(group, candidate)))
        if pending:
            summaries.append(build_compact_summary_message(await call(pending, settings)))
        return summaries

    current = items
    try:
        while True:
            if fits(current, settings):
                return await call(current, settings), total
            reduced = await reduce(history_groups(current))
            if len(reduced) == 1:
                return str(reduced[0]["content"]), total
            if not fits(reduced, settings) and estimate_request_value(reduced) >= estimate_request_value(current):
                raise ContextCompactionError("Summaries did not reduce context; stopping without retrying paid requests.")
            current = reduced
    except (TimeoutError, ValueError) as exc:
        raise ContextCompactionError(f"History preparation failed; originals preserved: {exc}") from exc
