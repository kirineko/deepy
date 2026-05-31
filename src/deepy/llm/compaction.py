from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from deepy.config import Settings
from deepy.prompts.compact import build_compact_prompt, build_compact_summary_message
from deepy.sessions import DeepySession
from deepy.todos import todo_state_prompt_text
from deepy.usage import TokenUsage, usage_from_run_result

from .context import estimate_tokens_for_item, estimate_tokens_for_items
from .cache_context import (
    CachePrefixSnapshot,
)
from .provider import ProviderBundle, build_provider_bundle
from .replay import sanitize_sdk_items_for_replay

CompactionReason = Literal["manual", "auto"]


class ContextCompactionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CompactionResult:
    session_id: str
    compacted: bool
    reason: CompactionReason
    before_tokens: int
    after_tokens: int
    preserved_item_count: int
    archive_id: str | None = None
    usage: TokenUsage | None = None
    message: str = ""


@dataclass(frozen=True)
class ContextReadiness:
    session_id: str
    before_tokens: int
    after_tokens: int
    compacted: bool
    compaction: CompactionResult | None = None


async def compact_session(
    session: DeepySession,
    settings: Settings,
    *,
    provider: ProviderBundle | None = None,
    reason: CompactionReason,
    focus_instruction: str | None = None,
    prefix_snapshot: CachePrefixSnapshot | None = None,
    prefix_tools: list[Any] | None = None,
    prefix_mcp_servers: list[Any] | None = None,
) -> CompactionResult:
    items = await session.get_items()
    before_estimated_tokens = session.context_token_state().active_tokens
    before_context_usage = session.latest_context_window_usage()
    before_tokens = (
        before_context_usage.used_tokens
        if before_context_usage is not None
        else before_estimated_tokens
    )
    prepared = prepare_compaction_items(
        items,
        preserve_recent_messages=settings.context.compact_preserve_recent_messages,
        preserve_recent_tokens=settings.context.compact_preserve_recent_tokens,
    )
    if prepared is None:
        return CompactionResult(
            session_id=session.session_id,
            compacted=False,
            reason=reason,
            before_tokens=before_tokens,
            after_tokens=before_tokens,
            preserved_item_count=len(items),
            message="The context is empty." if not items else "There is no context to compact.",
        )

    to_compact, to_preserve = prepared
    model_kwargs: dict[str, Any] = {}
    if prefix_snapshot is not None:
        model_kwargs["prefix_snapshot"] = prefix_snapshot
    if prefix_tools is not None:
        model_kwargs["prefix_tools"] = prefix_tools
    if prefix_mcp_servers is not None:
        model_kwargs["prefix_mcp_servers"] = prefix_mcp_servers
    summary, usage = await run_compaction_model(
        to_compact,
        settings,
        provider=provider,
        focus_instruction=focus_instruction,
        todo_state=session.todo_state(),
        **model_kwargs,
    )
    replacement = sanitize_sdk_items_for_replay(
        [build_compact_summary_message(summary), *to_preserve]
    )
    after_tokens = _estimate_compacted_tokens(replacement, usage)
    try:
        archive_id = await session.archive_and_replace_items(
            replacement,
            active_tokens=after_tokens,
            reason=reason,
            before_tokens=before_tokens,
            after_tokens=after_tokens,
        )
    except Exception as exc:
        raise ContextCompactionError(f"Failed to write compacted session: {exc}") from exc

    return CompactionResult(
        session_id=session.session_id,
        compacted=True,
        reason=reason,
        before_tokens=before_tokens,
        after_tokens=after_tokens,
        preserved_item_count=len(to_preserve),
        archive_id=archive_id,
        usage=usage,
        message="Context compacted.",
    )


async def ensure_context_ready(
    session: DeepySession,
    settings: Settings,
    *,
    provider: ProviderBundle | None = None,
    prefix_snapshot: CachePrefixSnapshot | None = None,
    prefix_tools: list[Any] | None = None,
    prefix_mcp_servers: list[Any] | None = None,
    additional_input: Any | None = None,
) -> ContextReadiness:
    additional_tokens = estimate_tokens_for_item(additional_input or "")
    state = session.context_token_state()
    before_tokens = state.active_tokens + additional_tokens
    latest_context_usage = session.latest_context_window_usage()
    trigger_tokens = (
        latest_context_usage.used_tokens if latest_context_usage is not None else before_tokens
    )
    compacted: CompactionResult | None = None
    if trigger_tokens >= settings.context.resolved_compact_threshold:
        compaction_kwargs: dict[str, Any] = {}
        if prefix_snapshot is not None:
            compaction_kwargs["prefix_snapshot"] = prefix_snapshot
        if prefix_tools is not None:
            compaction_kwargs["prefix_tools"] = prefix_tools
        if prefix_mcp_servers is not None:
            compaction_kwargs["prefix_mcp_servers"] = prefix_mcp_servers
        compacted = await compact_session(
            session,
            settings,
            provider=provider,
            reason="auto",
            **compaction_kwargs,
        )

    after_state = session.context_token_state()
    after_tokens = after_state.active_tokens + additional_tokens
    if compacted and compacted.compacted:
        fit_tokens = after_tokens
    else:
        after_context_usage = session.latest_context_window_usage()
        fit_tokens = (
            after_context_usage.used_tokens if after_context_usage is not None else after_tokens
        )
    if fit_tokens + settings.context.reserved_context_tokens >= settings.context.window_tokens:
        raise ContextCompactionError(
            "Context exceeds the configured window and could not be compacted enough "
            f"({fit_tokens:,} tokens + {settings.context.reserved_context_tokens:,} reserved "
            f">= {settings.context.window_tokens:,} window)."
        )
    return ContextReadiness(
        session_id=session.session_id,
        before_tokens=before_tokens,
        after_tokens=after_tokens,
        compacted=bool(compacted and compacted.compacted),
        compaction=compacted,
    )


def prepare_compaction_items(
    items: list[dict[str, Any]],
    *,
    preserve_recent_messages: int,
    preserve_recent_tokens: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    if not items or preserve_recent_messages <= 0:
        return None
    preserve_start = len(items)
    seen_messages = 0
    for index in range(len(items) - 1, -1, -1):
        if _is_conversation_message(items[index]):
            seen_messages += 1
            if seen_messages >= preserve_recent_messages:
                preserve_start = index
                break
    if seen_messages < preserve_recent_messages:
        return None
    preserve_start = _expand_preserve_start_for_tool_group(items, preserve_start)
    to_compact = items[:preserve_start]
    to_preserve = items[preserve_start:]
    if preserve_recent_tokens is not None:
        while to_preserve and estimate_tokens_for_items(to_preserve) > preserve_recent_tokens:
            to_compact.append(to_preserve.pop(0))
    if not to_compact:
        return None
    return sanitize_sdk_items_for_replay(to_compact), sanitize_sdk_items_for_replay(to_preserve)


async def run_compaction_model(
    items: list[dict[str, Any]],
    settings: Settings,
    *,
    provider: ProviderBundle | None = None,
    focus_instruction: str | None = None,
    todo_state: list[dict[str, str]] | None = None,
    prefix_snapshot: CachePrefixSnapshot | None = None,
    prefix_tools: list[Any] | None = None,
    prefix_mcp_servers: list[Any] | None = None,
) -> tuple[str, TokenUsage]:
    from agents import Agent, RunConfig, Runner

    resolved_provider = provider or build_provider_bundle(settings)
    prompt = build_compact_prompt(
        items,
        focus_instruction=focus_instruction,
        todo_context=todo_state_prompt_text(todo_state or []),
    )
    instructions = "Create a compact continuation summary. Do not call tools."
    if prefix_snapshot is not None and prefix_snapshot.system_instructions:
        instructions = (
            f"{prefix_snapshot.system_instructions}\n\n"
            "Deepy context compaction task: create a compact continuation summary. "
            "Do not call tools."
        )
    agent = Agent(
        name="Deepy Context Compactor",
        instructions=instructions,
        model=resolved_provider.model,
        model_settings=resolved_provider.model_settings,
        tools=list(prefix_tools or []),
        mcp_servers=list(prefix_mcp_servers or []),
        mcp_config={"include_server_in_tool_names": True},
    )
    result = await Runner.run(
        agent,
        prompt,
        max_turns=1,
        run_config=RunConfig(
            workflow_name="Deepy Context Compaction",
            trace_include_sensitive_data=False,
            reasoning_item_id_policy="omit",
        ),
    )
    output = getattr(result, "final_output", "")
    summary = str(output).strip()
    if not summary:
        raise ContextCompactionError("Compaction produced an empty summary.")
    return summary, usage_from_run_result(result)


def _estimate_compacted_tokens(items: list[dict[str, Any]], usage: TokenUsage | None) -> int:
    if usage is not None and usage.known and items:
        return usage.completion_tokens + estimate_tokens_for_items(items[1:])
    return estimate_tokens_for_items(items)


def _is_conversation_message(item: dict[str, Any]) -> bool:
    role = item.get("role")
    if role in {"user", "assistant"}:
        return True
    return item.get("type") == "message" and item.get("role") in {"user", "assistant"}


def _expand_preserve_start_for_tool_group(items: list[dict[str, Any]], preserve_start: int) -> int:
    while preserve_start > 0 and items[preserve_start - 1].get("type") in {
        "function_call",
        "function_call_output",
    }:
        preserve_start -= 1
    needed_call_ids = {
        call_id
        for item in items[preserve_start:]
        if (item.get("type") == "function_call_output" and (call_id := _call_id(item)))
    }
    if not needed_call_ids:
        return preserve_start
    for index in range(preserve_start - 1, -1, -1):
        if (
            items[index].get("type") == "function_call"
            and _call_id(items[index]) in needed_call_ids
        ):
            preserve_start = index
            needed_call_ids.discard(_call_id(items[index]))
            if not needed_call_ids:
                break
    return preserve_start


def _call_id(item: dict[str, Any]) -> str:
    value = item.get("call_id") or item.get("id")
    return value if isinstance(value, str) else ""
