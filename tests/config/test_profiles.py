from __future__ import annotations

import json
import os
import tomllib

import pytest

from deepy.config import (
    Settings,
    load_settings,
    write_config,
    update_config_model_settings,
    settings_to_toml_dict,
)
from deepy.config.providers import PROVIDER_CATALOG
from deepy.llm.multimodal import model_supports_image_input


@pytest.mark.parametrize("info", PROVIDER_CATALOG, ids=lambda p: p.id)
def test_catalog_and_profile_defaults(info):
    settings = Settings.from_mapping({"config_version": 2, "active_provider": info.id})
    assert settings.model.name == info.default_model
    assert settings.model.base_url == info.default_base_url
    assert settings.model.reasoning_mode == info.default_thinking_mode
    assert info.api == "responses"
    for model in info.models:
        assert model_supports_image_input(info.id, model.name) == (model.name != "mimo-v2.5-pro")


def test_switching_and_editing_preserves_every_profile(tmp_path):
    path = tmp_path / "config.toml"
    for info in PROVIDER_CATALOG:
        write_config(
            path,
            provider=info.id,
            model=info.models[-1].name,
            api_key=f"saved-{info.id}",
            base_url=f"https://{info.id}.example/v1",
            theme="dark",
        )
    raw = tomllib.loads(path.read_text())
    raw["mcp"] = {"enabled": False}
    import tomli_w

    path.write_text(tomli_w.dumps(raw))
    for info in reversed(PROVIDER_CATALOG):
        update_config_model_settings(path, provider=info.id)
        current = load_settings(path, env={})
        assert current.model.api_key == f"saved-{info.id}"
        assert current.model.name == info.models[-1].name
        assert current.model.base_url == f"https://{info.id}.example/v1"
        assert current.mcp.enabled is False
    assert os.stat(path).st_mode & 0o777 == 0o600
    before = tomllib.loads(path.read_text())["providers"]
    write_config(path, provider="mimo", model="mimo-v2.5", api_key="", theme="light")
    after = tomllib.loads(path.read_text())["providers"]
    assert after["mimo"]["api_key"] == "saved-mimo"
    assert after["deepseek"] == before["deepseek"]


def test_environment_override_never_saved(tmp_path):
    path = tmp_path / "config.toml"
    write_config(
        path, provider="deepseek", model="deepseek-flash", api_key="saved-secret", theme="dark"
    )
    resolved = load_settings(
        path,
        env={
            "DEEPSEEK_API_KEY": "runtime-secret",
            "MIMO_API_KEY": "mimo-secret",
            "DEEPY_API_KEY": "wrong",
        },
    )
    assert resolved.model.api_key == "runtime-secret"
    assert resolved.provider_keys["mimo"] == "mimo-secret"
    update_config_model_settings(path, reasoning_mode="high")
    assert "runtime-secret" not in path.read_text()
    assert load_settings(path, env={}).model.api_key == "saved-secret"
    displayed = json.dumps(settings_to_toml_dict(resolved))
    assert (
        "runtime-secret" not in displayed
        and "saved-secret" not in displayed
        and "mimo-secret" not in displayed
    )


@pytest.mark.parametrize(
    "env,expected",
    [
        ({"KIMI_API_KEY": "primary", "MOONSHOT_API_KEY": "alias"}, "primary"),
        ({"KIMI_API_KEY": "", "MOONSHOT_API_KEY": "alias"}, "alias"),
        ({"DEEPY_API_KEY": "wrong"}, "saved"),
    ],
)
def test_kimi_key_precedence(env, expected):
    settings = Settings.from_mapping(
        {"active_provider": "kimi", "providers": {"kimi": {"api_key": "saved"}}}, env=env
    )
    assert settings.model.api_key == expected


@pytest.mark.parametrize(
    "raw",
    [
        {"model": {"api_key": "old"}},
        {"config_version": 1},
        {"active_provider": "openrouter"},
        {"providers": {"xiaomi": {}}},
        {"providers": {"deepseek": {"model": "invalid"}}},
        {"providers": {"kimi": {"model": "invalid"}}},
    ],
)
def test_invalid_profiles_rejected(raw):
    with pytest.raises(ValueError):
        Settings.from_mapping(raw)


def test_failed_atomic_write_keeps_original(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    write_config(path, model="deepseek-flash", api_key="saved", theme="dark")
    before = path.read_bytes()

    def fail(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr("deepy.config.config_io.os.replace", fail)
    with pytest.raises(OSError):
        update_config_model_settings(path, provider="mimo")
    assert path.read_bytes() == before
    assert list(tmp_path.glob(".deepy-config-*")) == []
