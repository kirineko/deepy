from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

from deepy.config import Settings
from deepy.prompts.compact import build_compact_summary_message
from deepy.sessions import DeepySession
from deepy.todos import todo_state_prompt_text
from deepy.usage import TokenUsage, usage_from_run_result

from .context import estimate_tokens_for_items
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
    before_source: str = "estimated"


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
    announce: Any = None,
    additional_input: Any = None,
) -> CompactionResult:
    from .history_projection import fingerprint, model_identity, history_groups
    from .history_migration import summarize_bounded
    from .request_budget import estimate_request_value

    items = await session.get_items()
    revision = fingerprint(items)
    history_groups(items)
    for_model = focus_instruction == "--for-model"
    from deepy.sessions.history_state import read_history_state
    before_tokens = estimate_request_value(items)
    before_source = "estimated"
    state = read_history_state(session).get("checkpoint", {})
    usage_checkpoint = session.latest_context_window_usage()
    if (usage_checkpoint is not None and state.get("revision") == revision
            and state.get("target") == model_identity(settings.model.provider, settings.model.name, settings.model.base_url)
            and prefix_snapshot is not None and state.get("prefix") == prefix_snapshot.fingerprint):
        before_tokens = usage_checkpoint.used_tokens
        before_source = "reported"
    prepared = prepare_compaction_items(
        items,
        preserve_recent_messages=settings.context.compact_preserve_recent_messages,
        preserve_recent_tokens=settings.context.compact_preserve_recent_tokens,
    )
    if for_model and items:
        prepared = (items, [])
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
    summary, usage = await summarize_bounded(
        to_compact,
        settings,
        session=session, summarize=run_compaction_model,
        allow_image_reduction=for_model, announce=announce,
        provider=provider,
        focus=None if for_model else focus_instruction,
        **model_kwargs,
    )
    replacement = sanitize_sdk_items_for_replay(
        [build_compact_summary_message(summary), *to_preserve]
    )
    if for_model:
        replacement[0]["content"] = "Potentially lossy text summary; original images and messages remain archived.\n" + replacement[0]["content"]
    after_tokens = estimate_request_value(replacement)
    limits = settings.model_limits
    overhead = estimate_request_value(getattr(prefix_snapshot, "system_instructions", ""))
    overhead += estimate_request_value(getattr(prefix_snapshot, "tools", ()))
    overhead += estimate_request_value(getattr(prefix_snapshot, "mcp_tools", ()))
    overhead += estimate_request_value(additional_input or "")
    if after_tokens + overhead + limits.reserve_tokens >= limits.window_tokens:
        raise ContextCompactionError("Summary and recent history still exceed target budget; original history preserved.")
    try:
        archive_id = await session.archive_and_replace_items(
            replacement,
            active_tokens=after_tokens,
            reason=reason,
            before_tokens=before_tokens,
            after_tokens=after_tokens,
            expected_revision=revision,
            projection={"source_revision": revision, "target": model_identity(settings.model.provider, settings.model.name, settings.model.base_url),
                        "adapter_version": 1, "covered_items": len(to_compact),
                        "preserved_items": len(to_preserve), "lossy_images": for_model,
                        "tool_group_sizes": [len(group) for group in history_groups(to_compact)],
                        "summary_requests": read_history_state(session).get("summary_requests", [])},
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
        before_source=before_source,
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
    announce: Any = None,
) -> ContextReadiness:
    from .history_projection import model_identity, project_history, history_groups
    from .request_budget import request_budget
    from .response_images import normalize_response_images
    from .multimodal import items_contain_image_content, supports_image_input

    limits = settings.model_limits
    target = model_identity(settings.model.provider, settings.model.name, settings.model.base_url)

    async def budget():
        items = project_history(await session.get_items(), target)
        history_groups(items)
        combined = normalize_response_images([*items, *(
            additional_input if isinstance(additional_input, list)
            else [{"role": "user", "content": additional_input}] if additional_input else []
        )])
        if items_contain_image_content(combined) and not supports_image_input(settings):
            raise ContextCompactionError("Image history is preserved. Switch back, start a text session, or explicitly use /compact --for-model.")
        estimated = request_budget({"input": combined,
            "instructions": getattr(prefix_snapshot, "system_instructions", ""),
            "tools": [*getattr(prefix_snapshot, "tools", ()), *getattr(prefix_snapshot, "mcp_tools", ())],
        }, limits)
        from deepy.sessions.history_state import read_history_state
        from .history_projection import fingerprint
        state = read_history_state(session).get("checkpoint", {})
        count = state.get("count", 0)
        originals = await session.get_items()
        usage = session.latest_context_window_usage()
        if (usage is not None and state.get("target") == target
                and prefix_snapshot is not None and state.get("prefix") == prefix_snapshot.fingerprint
                and count <= len(originals) and state.get("revision") == fingerprint(originals[:count])):
            from .request_budget import estimate_request_value
            pending = estimate_request_value(normalize_response_images(originals[count:]))
            pending += estimate_request_value(additional_input or "")
            estimated = replace(estimated, input_tokens=max(estimated.input_tokens, usage.used_tokens + pending))
        return estimated

    before = await budget()
    before_tokens = before.input_tokens
    compacted = None
    if before.needs_compaction(settings.context.compact_trigger_ratio):
        compacted = await compact_session(session, settings, provider=provider, reason="auto",
            prefix_snapshot=prefix_snapshot, prefix_tools=prefix_tools,
            prefix_mcp_servers=prefix_mcp_servers, additional_input=additional_input, announce=announce)
    after = await budget()
    after_tokens = after.input_tokens
    if not after.fits:
        raise ContextCompactionError("Context still exceeds the target request budget. Original history is retained; reduce input or switch models.")
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
        from .history_projection import history_groups

        groups = history_groups(to_preserve)
        while groups and estimate_tokens_for_items(to_preserve) > preserve_recent_tokens:
            to_compact.extend(groups.pop(0))
            to_preserve = [item for group in groups for item in group]
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
    from .provider import DeepyResponsesModel
    if isinstance(resolved_provider.model, DeepyResponsesModel):
        client = resolved_provider.model._client.with_options(max_retries=0)
        resolved_provider = replace(resolved_provider, model=DeepyResponsesModel(
            provider=settings.model.provider, model=settings.model.name,
            openai_client=client, limits=settings.model_limits))
    from .history_migration import summary_input
    prompt = summary_input(items, focus_instruction, todo_state_prompt_text(todo_state or []))
    from .summary_size import summary_instructions
    instructions = summary_instructions(prefix_snapshot)
    agent = Agent(
        name="Deepy Context Compactor",
        instructions=instructions,
        model=resolved_provider.model,
        model_settings=replace(resolved_provider.model_settings, max_tokens=min(8192, settings.model_limits.output_tokens), tool_choice="auto" if settings.model.provider == "kimi" else "none"),
        tools=[] if settings.model.provider == "kimi" else list(prefix_tools or []),
        mcp_servers=[] if settings.model.provider == "kimi" else list(prefix_mcp_servers or []),
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
