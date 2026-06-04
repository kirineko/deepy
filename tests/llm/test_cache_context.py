from __future__ import annotations

from types import SimpleNamespace

from agents import ModelSettings

from deepy.config.settings import ModelConfig, Settings
from deepy.llm.cache_context import (
    build_cache_prefix_snapshot,
    build_cache_usage_update,
    cache_break_reason_for_snapshot_change,
    capture_cache_prefix_diagnostics,
    capture_sdk_request_shape,
    format_cache_usage,
    set_current_cache_prefix_snapshot,
    reset_current_cache_prefix_snapshot,
)


def test_cache_prefix_snapshot_is_deterministic_and_changes_by_component():
    settings = Settings(model=ModelConfig(api_key="sk-test"))
    tool = SimpleNamespace(
        name="Read",
        description="Read files",
        params_json_schema={"type": "object", "properties": {"path": {"type": "string"}}},
    )

    first = build_cache_prefix_snapshot(
        settings,
        system_instructions="system",
        tools=[tool],
        model_settings=ModelSettings(include_usage=True, store=False),
        skill_names=["demo"],
        runtime_context_key="/repo",
    )
    second = build_cache_prefix_snapshot(
        settings,
        system_instructions="system",
        tools=[tool],
        model_settings=ModelSettings(include_usage=True, store=False),
        skill_names=["demo"],
        runtime_context_key="/repo",
    )
    changed = build_cache_prefix_snapshot(
        Settings(model=ModelConfig(api_key="sk-test", name="deepseek-v4-flash")),
        system_instructions="system",
        tools=[tool],
        model_settings=ModelSettings(include_usage=True, store=False),
        skill_names=["demo"],
        runtime_context_key="/repo",
    )

    assert first.fingerprint == second.fingerprint
    assert first.fingerprint != changed.fingerprint
    assert cache_break_reason_for_snapshot_change(first, changed) == "prefix changed: model"


def test_cache_usage_update_tracks_known_and_unknown_turns():
    previous = build_cache_usage_update(
        None,
        {
            "prompt_tokens": 100,
            "completion_tokens": 5,
            "total_tokens": 105,
            "prompt_cache_hit_tokens": 80,
            "prompt_cache_miss_tokens": 20,
        },
    )
    updated = build_cache_usage_update(
        previous,
        {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
    )

    assert updated["hit_tokens"] == 80
    assert updated["miss_tokens"] == 20
    assert updated["known_turns"] == 1
    assert updated["unknown_turns"] == 1
    assert format_cache_usage(updated) == "fresh input 20 · cached input 80 (80.0% hit)"


def test_cache_prefix_diagnostics_capture_shape_without_secrets():
    diagnostics = []
    snapshot = build_cache_prefix_snapshot(
        Settings(model=ModelConfig(api_key="sk-test")),
        system_instructions="system",
        model_settings=ModelSettings(include_usage=True, store=False),
    )

    with capture_cache_prefix_diagnostics(diagnostics.append):
        token = set_current_cache_prefix_snapshot(snapshot)
        try:
            capture_sdk_request_shape(
                system_instructions="system",
                input=[{"role": "user", "content": "hi"}],
                model="deepseek-v4-pro",
                model_settings=ModelSettings(
                    include_usage=True,
                    store=False,
                    extra_headers={"Authorization": "Bearer sk-secret"},
                ),
                tools=[],
                mcp_servers=[],
            )
        finally:
            reset_current_cache_prefix_snapshot(token)

    assert diagnostics
    payload = diagnostics[0]
    assert payload.prefix_snapshot is not None
    assert payload.sdk_request_shape["model"] == "deepseek-v4-pro"
    assert "sk-secret" not in str(payload.sdk_request_shape)
    assert "Authorization" not in str(payload.sdk_request_shape)
