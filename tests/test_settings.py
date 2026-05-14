from __future__ import annotations

import pytest

from deepy.config import (
    DEFAULT_WEB_SEARCH_SEARXNG_URL,
    load_settings,
    settings_to_toml_dict,
    update_config_theme,
    ui_theme_from_selection,
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


def test_loads_ui_theme_values(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ntheme = "light"\n', encoding="utf-8")

    settings = load_settings(config, env={})

    assert settings.ui.theme == "light"
    assert settings.ui.theme_configured is True


def test_defaults_ui_theme_to_auto_when_missing_or_invalid(tmp_path):
    missing = tmp_path / "missing-theme.toml"
    missing.write_text("", encoding="utf-8")
    invalid = tmp_path / "invalid-theme.toml"
    invalid.write_text('[ui]\ntheme = "solarized"\n', encoding="utf-8")

    missing_settings = load_settings(missing, env={})
    invalid_settings = load_settings(invalid, env={})

    assert missing_settings.ui.theme == "auto"
    assert missing_settings.ui.theme_configured is False
    assert invalid_settings.ui.theme == "auto"
    assert invalid_settings.ui.theme_configured is False


def test_ui_theme_selection_accepts_numbers_and_names():
    assert ui_theme_from_selection("1", default="light") == "auto"
    assert ui_theme_from_selection("2", default="auto") == "dark"
    assert ui_theme_from_selection("3", default="auto") == "light"
    assert ui_theme_from_selection("dark", default="auto") == "dark"
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
