from __future__ import annotations

import pytest

from deepy.config import (
    DEFAULT_UI_VIEW_MODE,
    load_settings,
    settings_to_toml_dict,
    update_config_textual_theme,
    update_config_ui_interface,
    update_config_view_mode,
    ui_interface_from_selection,
    ui_setup_from_selection,
    ui_theme_from_selection,
)


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


def test_json_config_is_not_supported(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON config is not supported"):
        load_settings(config)


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


def test_loads_tui_specific_textual_theme(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ntheme = "dark"\ntextual_theme = "tokyo-night"\n', encoding="utf-8")

    settings = load_settings(config, env={})

    assert settings.ui.theme == "dark"
    assert settings.ui.textual_theme == "tokyo-night"


def test_loads_ui_interface_values(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ninterface = "modern"\ntheme = "light"\n', encoding="utf-8")
    invalid = tmp_path / "invalid.toml"
    invalid.write_text('[ui]\ninterface = "future"\n', encoding="utf-8")

    settings = load_settings(config, env={})
    invalid_settings = load_settings(invalid, env={})

    assert settings.ui.interface == "modern"
    assert invalid_settings.ui.interface == "classic"


def test_ui_theme_selection_accepts_numbers_and_names():
    assert ui_theme_from_selection("1", default="light") == "dark"
    assert ui_theme_from_selection("2", default="dark") == "light"
    assert ui_theme_from_selection("auto", default="light") == "light"
    assert ui_theme_from_selection("dark", default="light") == "dark"
    assert ui_theme_from_selection("", default="light") == "light"
    assert ui_theme_from_selection("solarized", default="dark") == "dark"


def test_ui_interface_and_setup_selection_accept_numbers_and_names():
    assert ui_interface_from_selection("1", default="modern") == "classic"
    assert ui_interface_from_selection("2", default="classic") == "modern"
    assert ui_interface_from_selection("modern", default="classic") == "modern"
    assert ui_interface_from_selection("", default="modern") == "modern"
    assert ui_setup_from_selection("1") == ("classic", "dark")
    assert ui_setup_from_selection("2") == ("classic", "light")
    assert ui_setup_from_selection("3") == ("modern", "dark")
    assert ui_setup_from_selection("4") == ("modern", "light")
    assert ui_setup_from_selection("modern light") == ("modern", "light")


def test_update_config_ui_interface_preserves_theme(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ntheme = "light"\n', encoding="utf-8")

    update_config_ui_interface(config, "modern")

    text = config.read_text(encoding="utf-8")
    assert 'interface = "modern"' in text
    assert 'theme = "light"' in text


def test_update_config_textual_theme_preserves_shared_theme(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ntheme = "dark"\n', encoding="utf-8")

    update_config_textual_theme(config, "tokyo-night")

    text = config.read_text(encoding="utf-8")
    assert config.stat().st_mode & 0o777 == 0o600
    assert 'theme = "dark"' in text
    assert 'textual_theme = "tokyo-night"' in text


def test_update_config_view_mode_rejects_invalid_without_changing_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\nview_mode = "concise"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="View mode must be one of"):
        update_config_view_mode(config, "thinking")

    assert config.read_text(encoding="utf-8") == '[ui]\nview_mode = "concise"\n'


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
