from __future__ import annotations

import pytest

from deepy.config import DEFAULT_WEB_SEARCH_SEARXNG_URL, load_settings, settings_to_toml_dict


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
    assert settings.context.resolved_compact_threshold == 838861


def test_deepseek_thinking_default_is_case_insensitive(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[model]\nname = "DeepSeek-V4-Pro"\n', encoding="utf-8")

    settings = load_settings(config, env={})

    assert settings.model.thinking_enabled is True


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
