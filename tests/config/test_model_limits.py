from copy import deepcopy
from dataclasses import replace

import pytest

from deepy.config import Settings, load_settings, settings_to_toml_dict
from deepy.config.config_io import update_config_model_settings
from deepy.config.model_limits import MODEL_LIMITS, resolve_model_limits


@pytest.mark.parametrize("key", MODEL_LIMITS)
def test_catalog_limits_are_explicit_and_conservative(key):
    resolved = resolve_model_limits(*key)
    assert resolved.window_tokens == (1_050_000 if key[0] == "cli_proxy" else 1_000_000)
    assert resolved.output_tokens == 32_768
    assert resolved.reserve_tokens == 50_000
    assert resolved.catalog.checked_date == ("2026-09-22" if key[0] == "mimo" else "2026-09-15")
    assert resolved.catalog.url.startswith("https://")
    assert resolved.catalog.exact_window_tokens == (1_050_000 if key[0] == "cli_proxy" else None)
    assert resolved.source == ("proxy-unverified" if key[0] == "cli_proxy" else "conservative")


def test_caps_resolve_minimum_and_switch_restores_model_defaults():
    raw = {"active_provider": "cli_proxy", "context": {"window_tokens": 900_000},
           "providers": {"cli_proxy": {"model_limits": {"gpt-5.6-terra": {
               "context_window_tokens": 700_000, "max_output_tokens": 12_000}}}}}
    original = deepcopy(raw)
    settings = Settings.from_mapping(raw)
    assert settings.context.window_tokens == 700_000
    assert settings.model_limits.output_tokens == 12_000
    child = replace(settings, model=replace(settings.model, name="gpt-5.5"))
    assert child.model_limits.window_tokens == 900_000
    assert child.model_limits.output_tokens == 32_768
    assert raw == original
    assert Settings.from_mapping({"active_provider": "cli_proxy"}).context.window_tokens == 1_050_000
    assert Settings.from_mapping({}).context.window_tokens == 1_000_000


@pytest.mark.parametrize("field,value", [("context_window_tokens", 0), ("context_window_tokens", True),
    ("context_window_tokens", "100000"), ("context_window_tokens", 2_000_000),
    ("max_output_tokens", -1), ("max_output_tokens", 400_000), ("unknown", 1),
    ("context_window_tokens", 40_000)])
def test_invalid_caps_rejected(field, value):
    with pytest.raises(ValueError):
        Settings.from_mapping({"providers": {"deepseek": {"model_limits": {
            "deepseek-flash": {field: value}}}}})


def test_unknown_inactive_model_rejected():
    with pytest.raises(ValueError, match="Unknown model"):
        Settings.from_mapping({"providers": {"mimo": {"model_limits": {"oops": {}}}}})


def test_show_is_read_only_redacted_and_reports_sources(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('config_version = 2\nactive_provider = "cli_proxy"\n[providers.cli_proxy]\napi_key = "secret-value-hidden"\n')
    before = path.read_bytes()
    shown = settings_to_toml_dict(load_settings(path, env={}))
    assert shown["resolved_model_limits"]["source"] == "proxy-unverified"
    assert shown["resolved_model_limits"].get("global_cap") is None
    assert "secret-value-hidden" not in str(shown)
    assert path.read_bytes() == before


def test_failed_write_preserves_profiles(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text('config_version = 2\n[providers.deepseek]\napi_key = "keep-me"\n')
    before = path.read_bytes()
    def fail(*args):
        raise OSError("injected failure")
    monkeypatch.setattr("deepy.config.config_io.os.replace", fail)
    with pytest.raises(OSError):
        update_config_model_settings(path, provider="mimo")
    assert path.read_bytes() == before
