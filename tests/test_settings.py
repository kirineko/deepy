from __future__ import annotations

import pytest

from deepy.config import (
    DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES,
    DEFAULT_OPENROUTER_BASE_URL,
    DEFAULT_RESERVED_CONTEXT_TOKENS,
    DEFAULT_XIAOMI_BASE_URL,
    DEFAULT_UI_VIEW_MODE,
    DEFAULT_WEB_SEARCH_SEARXNG_URL,
    load_settings,
    settings_to_toml_dict,
    update_config_model_settings,
    update_config_input_suggestions_enabled,
    update_config_theme,
    update_config_view_mode,
    provider_info_for,
    ui_theme_from_selection,
    write_config,
)


def test_loads_toml_config_and_resolves_context_threshold(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[model]
name = "deepseek-v4-pro"
base_url = "https://api.deepseek.com"
api_key = "sk-test"
reasoning_effort = "invalid"

[context]
window_tokens = 1048576
compact_trigger_ratio = 0.8
""",
        encoding="utf-8",
    )

    settings = load_settings(config, env={})

    assert settings.model.name == "deepseek-v4-pro"
    assert settings.model.thinking_enabled is True
    assert settings.model.reasoning_effort == "max"
    assert settings.model.reasoning_mode == "max"
    assert settings.context.resolved_compact_threshold == 838861
    assert settings.context.reserved_context_tokens == DEFAULT_RESERVED_CONTEXT_TOKENS
    assert settings.context.compact_preserve_recent_messages == DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES


def test_context_compaction_policy_values_ignore_unknown_legacy_threshold(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[context]
window_tokens = 200000
compact_trigger_ratio = 0.75
reserved_context_tokens = 40000
compact_preserve_recent_messages = 4
compact_preserve_recent_tokens = 12000
compact_prompt_token_threshold = 1
""",
        encoding="utf-8",
    )

    settings = load_settings(config, env={})

    assert settings.context.resolved_compact_threshold == 150000
    assert settings.context.reserved_context_tokens == 40000
    assert settings.context.compact_preserve_recent_messages == 4
    assert settings.context.compact_preserve_recent_tokens == 12000
    assert not hasattr(settings.context, "compact_prompt_token_threshold")


def test_deepseek_thinking_default_is_case_insensitive(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[model]\nname = "DeepSeek-V4-Pro"\n', encoding="utf-8")

    settings = load_settings(config, env={})

    assert settings.model.thinking_enabled is True
    assert settings.model.reasoning_mode == "max"


def test_supported_deepseek_model_loads_from_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[model]\nname = "deepseek-v4-flash"\n', encoding="utf-8")

    settings = load_settings(config, env={})

    assert settings.model.name == "deepseek-v4-flash"
    assert settings.model.thinking_enabled is True
    assert settings.model.reasoning_mode == "max"


def test_loads_explicit_openrouter_provider_and_switch_thinking(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[model]
provider = "openrouter"
name = "xiaomi/mimo-v2.5"
base_url = "https://openrouter.ai/api/v1"
thinking = false
reasoning_effort = "max"
""",
        encoding="utf-8",
    )

    settings = load_settings(config, env={})

    assert settings.model.provider == "openrouter"
    assert settings.model.name == "xiaomi/mimo-v2.5"
    assert settings.model.base_url == DEFAULT_OPENROUTER_BASE_URL
    assert settings.model.reasoning_mode == "none"
    assert settings.model.reasoning_effort == "none"


def test_loads_openrouter_custom_model_and_reasoning_effort(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[model]
provider = "openrouter"
name = "anthropic/claude-sonnet-4.5"
base_url = "https://openrouter.ai/api/v1"
thinking = true
reasoning_effort = "minimal"
""",
        encoding="utf-8",
    )

    settings = load_settings(config, env={})

    assert settings.model.provider == "openrouter"
    assert settings.model.name == "anthropic/claude-sonnet-4.5"
    assert settings.model.reasoning_mode == "minimal"
    assert settings.model.reasoning_effort == "minimal"


def test_loads_openrouter_custom_model_with_boolean_reasoning(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[model]
provider = "openrouter"
name = "google/gemini-3.5-flash"
base_url = "https://openrouter.ai/api/v1"
thinking = true
reasoning_effort = "enabled"
""",
        encoding="utf-8",
    )

    settings = load_settings(config, env={})

    assert settings.model.provider == "openrouter"
    assert settings.model.name == "google/gemini-3.5-flash"
    assert settings.model.reasoning_mode == "enabled"
    assert settings.model.reasoning_effort == "enabled"


def test_provider_catalog_exposes_api_key_guidance_urls():
    assert provider_info_for("deepseek").api_key_url == "https://platform.deepseek.com/api_keys"
    assert provider_info_for("openrouter").api_key_url == "https://openrouter.ai/workspaces/default/keys"
    assert provider_info_for("xiaomi").api_key_url == "https://platform.xiaomimimo.com/console/api-keys"


def test_infers_xiaomi_provider_from_base_url(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[model]
name = "mimo-v2.5-pro"
base_url = "https://api.xiaomimimo.com/v1"
""",
        encoding="utf-8",
    )

    settings = load_settings(config, env={})

    assert settings.model.provider == "xiaomi"
    assert settings.model.name == "mimo-v2.5-pro"
    assert settings.model.base_url == DEFAULT_XIAOMI_BASE_URL
    assert settings.model.reasoning_mode == "enabled"


def test_unknown_base_url_without_provider_preserves_custom_model(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[model]
name = "custom-model"
base_url = "https://llm.example/v1"
thinking = true
reasoning_effort = "high"
""",
        encoding="utf-8",
    )

    settings = load_settings(config, env={})

    assert settings.model.provider == "deepseek"
    assert settings.model.name == "custom-model"
    assert settings.model.base_url == "https://llm.example/v1"
    assert settings.model.reasoning_mode == "high"


def test_existing_thinking_fields_resolve_reasoning_mode(tmp_path):
    disabled = tmp_path / "disabled.toml"
    disabled.write_text('[model]\nthinking = false\nreasoning_effort = "high"\n', encoding="utf-8")
    high = tmp_path / "high.toml"
    high.write_text('[model]\nthinking = true\nreasoning_effort = "high"\n', encoding="utf-8")
    max_config = tmp_path / "max.toml"
    max_config.write_text('[model]\nthinking = true\nreasoning_effort = "max"\n', encoding="utf-8")

    assert load_settings(disabled, env={}).model.reasoning_mode == "none"
    assert load_settings(high, env={}).model.reasoning_mode == "high"
    assert load_settings(max_config, env={}).model.reasoning_mode == "max"


def test_json_config_is_not_supported(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON config is not supported"):
        load_settings(config)


def test_environment_overrides_toml_model_settings(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[model]
name = "deepseek-v4-pro"
base_url = "https://api.deepseek.com"
api_key = "sk-config"
""",
        encoding="utf-8",
    )

    settings = load_settings(
        config,
        env={
            "DEEPY_MODEL": "deepseek-v4-flash",
            "DEEPY_BASE_URL": "https://proxy.example/v1",
            "DEEPY_API_KEY": "sk-env",
        },
    )

    assert settings.model.name == "deepseek-v4-flash"
    assert settings.model.base_url == "https://proxy.example/v1"
    assert settings.model.api_key == "sk-env"


def test_loads_web_search_searxng_fallback_url(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[tools.web_search]
searxng_url = "https://search.example"
""",
        encoding="utf-8",
    )

    settings = load_settings(config, env={})

    assert settings.tools.web_search.searxng_url == "https://search.example"


def test_defaults_web_search_to_deepy_searxng_when_unconfigured(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")

    settings = load_settings(config, env={})

    assert settings.tools.web_search.searxng_url == DEFAULT_WEB_SEARCH_SEARXNG_URL


def test_settings_to_toml_masks_api_key(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-1234567890"\n', encoding="utf-8")

    data = settings_to_toml_dict(load_settings(config, env={}))

    assert data["model"]["api_key"] == "sk-1...7890"
    assert "reserved_context_tokens" in data["context"]
    assert "compact_prompt_token_threshold" not in data["context"]


def test_loads_mcp_policy_from_toml(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[mcp]
enabled = false
connect_timeout_seconds = 3
cleanup_timeout_seconds = 4
client_session_timeout_seconds = 20
cache_tools_list = false
allow_project_config = true
prefer_mcp_web_search = false

[mcp.web_search]
prefer_mcp = false
preferred_server = "tavily"
preferred_tools = ["tavily_search"]
fallback_to_builtin = false
""",
        encoding="utf-8",
    )

    settings = load_settings(config, env={})

    assert settings.mcp.enabled is False
    assert settings.mcp.connect_timeout_seconds == 3
    assert settings.mcp.cleanup_timeout_seconds == 4
    assert settings.mcp.client_session_timeout_seconds == 20
    assert settings.mcp.cache_tools_list is False
    assert settings.mcp.allow_project_config is True
    assert settings.mcp.prefer_mcp_web_search is False
    assert settings.mcp.web_search.prefer_mcp is False
    assert settings.mcp.web_search.preferred_server == "tavily"
    assert settings.mcp.web_search.preferred_tools == ("tavily_search",)
    assert settings.mcp.web_search.fallback_to_builtin is False


def test_settings_to_toml_includes_mcp_policy_without_server_secrets(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[mcp.web_search]\npreferred_server = \"tavily\"\n", encoding="utf-8")

    data = settings_to_toml_dict(load_settings(config, env={}))

    assert data["mcp"]["enabled"] is True
    assert data["mcp"]["web_search"]["preferred_server"] == "tavily"
    assert "env" not in data["mcp"]
    assert "headers" not in data["mcp"]


def test_loads_ui_theme_values(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ntheme = "light"\n', encoding="utf-8")

    settings = load_settings(config, env={})

    assert settings.ui.theme == "light"
    assert settings.ui.theme_configured is True


def test_input_suggestions_default_enabled_and_can_be_disabled(tmp_path):
    missing = tmp_path / "missing.toml"
    missing.write_text("", encoding="utf-8")
    disabled = tmp_path / "disabled.toml"
    disabled.write_text("[ui]\ninput_suggestions_enabled = false\n", encoding="utf-8")

    assert load_settings(missing, env={}).ui.input_suggestions_enabled is True
    assert load_settings(disabled, env={}).ui.input_suggestions_enabled is False


def test_ui_view_mode_defaults_and_can_be_configured(tmp_path):
    missing = tmp_path / "missing.toml"
    missing.write_text("", encoding="utf-8")
    full = tmp_path / "full.toml"
    full.write_text('[ui]\nview_mode = "full"\n', encoding="utf-8")
    concise = tmp_path / "concise.toml"
    concise.write_text('[ui]\nview_mode = "concise"\n', encoding="utf-8")
    invalid = tmp_path / "invalid.toml"
    invalid.write_text('[ui]\nview_mode = "thinking"\n', encoding="utf-8")

    assert load_settings(missing, env={}).ui.view_mode == DEFAULT_UI_VIEW_MODE
    assert load_settings(full, env={}).ui.view_mode == "full"
    assert load_settings(concise, env={}).ui.view_mode == "concise"
    assert load_settings(invalid, env={}).ui.view_mode == DEFAULT_UI_VIEW_MODE


def test_settings_to_toml_includes_input_suggestions_without_model_customization(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[ui]\ninput_suggestions_enabled = false\n", encoding="utf-8")

    data = settings_to_toml_dict(load_settings(config, env={}))

    assert data["ui"]["input_suggestions_enabled"] is False
    assert "input_suggestion_model" not in data["ui"]


def test_settings_to_toml_includes_view_mode(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[ui]\nview_mode = \"full\"\n", encoding="utf-8")

    data = settings_to_toml_dict(load_settings(config, env={}))

    assert data["ui"]["view_mode"] == "full"


def test_defaults_ui_theme_to_dark_when_missing_or_invalid(tmp_path):
    missing = tmp_path / "missing-theme.toml"
    missing.write_text("", encoding="utf-8")
    invalid = tmp_path / "invalid-theme.toml"
    invalid.write_text('[ui]\ntheme = "solarized"\n', encoding="utf-8")

    missing_settings = load_settings(missing, env={})
    invalid_settings = load_settings(invalid, env={})

    assert missing_settings.ui.theme == "dark"
    assert missing_settings.ui.theme_configured is False
    assert invalid_settings.ui.theme == "dark"
    assert invalid_settings.ui.theme_configured is False


def test_legacy_auto_ui_theme_loads_as_configured_dark(tmp_path):
    config = tmp_path / "auto-theme.toml"
    config.write_text('[ui]\ntheme = "auto"\n', encoding="utf-8")

    settings = load_settings(config, env={})

    assert settings.ui.theme == "dark"
    assert settings.ui.theme_configured is True


def test_ui_theme_selection_accepts_numbers_and_names():
    assert ui_theme_from_selection("1", default="light") == "dark"
    assert ui_theme_from_selection("2", default="dark") == "light"
    assert ui_theme_from_selection("auto", default="light") == "light"
    assert ui_theme_from_selection("dark", default="light") == "dark"
    assert ui_theme_from_selection("", default="light") == "light"
    assert ui_theme_from_selection("solarized", default="dark") == "dark"


def test_update_config_theme_preserves_existing_values_and_permissions(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[model]\napi_key = "sk-test"\n\n[tools.web_search]\nsearxng_url = "https://search.example"\n',
        encoding="utf-8",
    )

    update_config_theme(config, "light")

    text = config.read_text(encoding="utf-8")
    assert config.stat().st_mode & 0o777 == 0o600
    assert 'api_key = "sk-test"' in text
    assert 'searxng_url = "https://search.example"' in text
    assert '[ui]' in text
    assert 'theme = "light"' in text


def test_update_config_input_suggestions_preserves_existing_values_and_permissions(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[model]\napi_key = "sk-test"\n\n[ui]\ntheme = "dark"\n',
        encoding="utf-8",
    )

    update_config_input_suggestions_enabled(config, False)

    text = config.read_text(encoding="utf-8")
    assert config.stat().st_mode & 0o777 == 0o600
    assert 'api_key = "sk-test"' in text
    assert 'theme = "dark"' in text
    assert "input_suggestions_enabled = false" in text


def test_update_config_view_mode_preserves_existing_values_and_permissions(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[model]\napi_key = "sk-test"\n\n[ui]\ntheme = "dark"\ninput_suggestions_enabled = false\n',
        encoding="utf-8",
    )

    update_config_view_mode(config, "full")

    text = config.read_text(encoding="utf-8")
    assert config.stat().st_mode & 0o777 == 0o600
    assert 'api_key = "sk-test"' in text
    assert 'theme = "dark"' in text
    assert "input_suggestions_enabled = false" in text
    assert 'view_mode = "full"' in text


def test_update_config_view_mode_rejects_invalid_without_changing_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\nview_mode = "concise"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="View mode must be one of"):
        update_config_view_mode(config, "thinking")

    assert config.read_text(encoding="utf-8") == '[ui]\nview_mode = "concise"\n'


def test_update_config_model_settings_preserves_existing_values_and_permissions(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        (
            '[model]\napi_key = "sk-test"\nbase_url = "https://api.deepseek.com"\n\n'
            '[context]\nwindow_tokens = 1048576\n\n'
            '[ui]\ntheme = "dark"\n'
        ),
        encoding="utf-8",
    )

    update_config_model_settings(config, model="deepseek-v4-flash", reasoning_mode="high")

    text = config.read_text(encoding="utf-8")
    assert config.stat().st_mode & 0o777 == 0o600
    assert 'api_key = "sk-test"' in text
    assert 'base_url = "https://api.deepseek.com"' in text
    assert 'window_tokens = 1048576' in text
    assert 'theme = "dark"' in text
    assert 'name = "deepseek-v4-flash"' in text
    assert 'thinking = true' in text
    assert 'reasoning_effort = "high"' in text


def test_write_config_uses_provider_default_base_urls_and_switch_thinking(tmp_path):
    config = tmp_path / "config.toml"

    write_config(
        config,
        api_key="sk-test",
        provider="xiaomi",
        model="mimo-v2.5",
        theme="dark",
        thinking_mode="disabled",
    )

    text = config.read_text(encoding="utf-8")
    assert 'provider = "xiaomi"' in text
    assert 'name = "mimo-v2.5"' in text
    assert f'base_url = "{DEFAULT_XIAOMI_BASE_URL}"' in text
    assert 'thinking = false' in text
    assert 'reasoning_effort = "none"' in text
    assert 'view_mode = "concise"' in text


def test_write_config_saves_xiaomi_enabled_as_switch_only_mode(tmp_path):
    config = tmp_path / "config.toml"

    write_config(
        config,
        api_key="sk-test",
        provider="xiaomi",
        model="mimo-v2.5-pro",
        theme="dark",
        thinking_mode="enabled",
    )

    text = config.read_text(encoding="utf-8")
    assert 'provider = "xiaomi"' in text
    assert 'thinking = true' in text
    assert 'reasoning_effort = "enabled"' in text

    settings = load_settings(config, env={})
    assert settings.model.reasoning_mode == "enabled"
    assert settings.model.reasoning_effort == "enabled"


def test_update_config_model_settings_switches_provider_with_defaults_and_preserves_unrelated(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        (
            '[model]\napi_key = "sk-test"\nname = "deepseek-v4-pro"\n'
            'base_url = "https://api.deepseek.com"\nreasoning_effort = "max"\n\n'
            '[ui]\ntheme = "dark"\n'
        ),
        encoding="utf-8",
    )

    update_config_model_settings(config, provider="openrouter")

    text = config.read_text(encoding="utf-8")
    assert 'api_key = "sk-test"' in text
    assert 'theme = "dark"' in text
    assert 'provider = "openrouter"' in text
    assert 'name = "xiaomi/mimo-v2.5-pro"' in text
    assert f'base_url = "{DEFAULT_OPENROUTER_BASE_URL}"' in text
    assert 'thinking = true' in text
    assert 'reasoning_effort = "enabled"' in text


def test_update_config_model_settings_saves_none_with_existing_fields(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[model]\nname = "deepseek-v4-pro"\nthinking = true\nreasoning_effort = "max"\n',
        encoding="utf-8",
    )

    update_config_model_settings(config, reasoning_mode="none")

    text = config.read_text(encoding="utf-8")
    assert 'name = "deepseek-v4-pro"' in text
    assert 'thinking = false' in text


def test_update_config_model_settings_rejects_invalid_values_without_changing_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[model]\nname = "deepseek-v4-pro"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Model must be one of"):
        update_config_model_settings(config, model="deepseek-chat")
    with pytest.raises(ValueError, match="Reasoning mode must be one of"):
        update_config_model_settings(config, reasoning_mode="medium")
    with pytest.raises(ValueError, match="Provider must be one of"):
        update_config_model_settings(config, provider="kimi")
    write_config(
        tmp_path / "custom-openrouter.toml",
        api_key="sk-test",
        provider="openrouter",
        model="deepseek/deepseek-r1",
        theme="dark",
        thinking_mode="xhigh",
    )

    assert config.read_text(encoding="utf-8") == '[model]\nname = "deepseek-v4-pro"\n'


def test_load_settings_reads_test_shell_policy_patterns(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[tools.test_shell]
allow_patterns = ["custom-test *"]
approval_required_patterns = ["seed-db *"]
""",
        encoding="utf-8",
    )

    settings = load_settings(config, env={})

    assert settings.tools.test_shell.allow_patterns == ("custom-test *",)
    assert settings.tools.test_shell.approval_required_patterns == ("seed-db *",)
