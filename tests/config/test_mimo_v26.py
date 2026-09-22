"""Catalog retirement must remain actionable without rewriting user state."""

import pytest
import tomli_w

from deepy.config import Settings, load_settings, update_config_model_settings, write_config
from deepy.config.model_limits import resolve_model_limits
from deepy.config.providers import provider_info_for
from deepy.input_suggestions import input_suggestion_model_name, input_suggestion_model_settings
from deepy.llm.thinking import build_model_settings

REPLACEMENTS = [("mimo-v2.5", "mimo-v2.6-flash"), ("mimo-v2.5-pro", "mimo-v2.6-pro")]


@pytest.mark.parametrize("old,new", REPLACEMENTS)
@pytest.mark.parametrize("active", ["mimo", "deepseek"])
@pytest.mark.parametrize("limits_only", [False, True])
def test_retired_profile_guidance_and_explicit_recovery(tmp_path, old, new, active, limits_only):
    path = tmp_path / "config.toml"
    profile = {
        "model": new if limits_only else old,
        "api_key": "saved-secret",
        "base_url": "https://example.test/v1",
        "reasoning": "disabled",
        "model_limits": {old: {"max_output_tokens": 4096}},
    }
    raw = {"config_version": 2, "active_provider": active, "providers": {"mimo": profile}}
    path.write_text(tomli_w.dumps(raw))
    before = path.read_bytes()
    with pytest.raises(ValueError) as error:
        load_settings(path, env={"MIMO_API_KEY": "runtime-secret"})
    message = str(error.value)
    assert old in message and new in message
    assert "providers.mimo.model" in message
    if limits_only:
        assert "model_limits" in message and "remove" in message
    assert "saved-secret" not in message and "runtime-secret" not in message
    assert path.read_bytes() == before
    profile["model"] = new
    profile["model_limits"] = {new: {"max_output_tokens": 4096}}
    path.write_text(tomli_w.dumps(raw))
    corrected = path.read_bytes()
    settings = load_settings(path, env={})
    model = settings.model_for_provider("mimo")
    assert (model.name, model.api_key, model.base_url, model.reasoning_mode) == (
        new, "saved-secret", "https://example.test/v1", "disabled"
    )
    assert settings.profiles["mimo"]["model_limits"][new]["max_output_tokens"] == 4096
    assert path.read_bytes() == corrected


@pytest.mark.parametrize("old,new", REPLACEMENTS)
def test_removed_selection_does_not_write(tmp_path, old, new):
    path = tmp_path / "config.toml"
    write_config(path, provider="mimo", model=new, api_key="saved", theme="dark")
    before = path.read_bytes()
    with pytest.raises(ValueError, match=new):
        update_config_model_settings(path, provider="mimo", model=old)
    assert path.read_bytes() == before


@pytest.mark.parametrize("model", [new for _, new in REPLACEMENTS])
@pytest.mark.parametrize("mode,effort", [("disabled", "none"), ("enabled", "high")])
def test_v26_catalog_reasoning_suggestions_and_limits(model, mode, effort):
    info = provider_info_for("mimo")
    assert [m.name for m in info.models] == [new for _, new in REPLACEMENTS]
    assert all(m.supports_image_input for m in info.models)
    assert info.default_model == "mimo-v2.6-flash"
    settings = Settings.from_mapping({"active_provider": "mimo", "providers": {
        "mimo": {"model": model, "reasoning": mode}}}, env={"MIMO_API_KEY": "test"})
    assert build_model_settings(settings).reasoning.effort == effort
    assert input_suggestion_model_name(settings) == "mimo-v2.6-flash"
    suggestion = input_suggestion_model_settings(settings)
    assert suggestion.reasoning.effort == "none"
    assert suggestion.store is False and suggestion.include_usage is True
    assert settings.model.api_key == "test"
    limits = resolve_model_limits("mimo", model)
    assert limits.window_tokens == 1_000_000 and limits.output_tokens == 32768
    assert limits.catalog.exact_window_tokens is None
    assert limits.catalog.checked_date == "2026-09-22"
    assert limits.catalog.max_output_tokens == 131072
    assert "mimo.mi.com" in limits.catalog.url
    assert resolve_model_limits("mimo", model, overrides={"max_output_tokens": 131072}).output_tokens == 131072
    with pytest.raises(ValueError, match="output limit"):
        resolve_model_limits("mimo", model, overrides={"max_output_tokens": 131073})
    assert resolve_model_limits("mimo", model, global_cap=60000).window_tokens == 60000
    with pytest.raises(ValueError, match="safety reserve"):
        resolve_model_limits("mimo", model, global_cap=60000, overrides={"max_output_tokens": 131072})
