import pytest
from deepy.config import Settings
from deepy.llm.thinking import build_model_settings
from deepy.input_suggestions import input_suggestion_model_name, input_suggestion_model_settings


@pytest.mark.parametrize(
    "provider,mode,effort",
    [
        ("deepseek", "none", "none"),
        ("deepseek", "high", "high"),
        ("deepseek", "max", "max"),
        ("mimo", "disabled", "none"),
        ("mimo", "enabled", "high"),
        ("kimi", "low", "low"),
        ("kimi", "max", "max"),
        ("cli_proxy", "medium", "medium"),
    ],
)
def test_responses_reasoning(provider, mode, effort):
    settings = Settings.from_mapping(
        {"active_provider": provider, "providers": {provider: {"reasoning": mode}}}
    )
    payload = build_model_settings(settings)
    assert payload.reasoning.effort == effort
    assert payload.store is False and payload.include_usage is True
    assert payload.extra_body is None


@pytest.mark.parametrize(
    "provider,model,effort",
    [
        ("deepseek", "deepseek-flash", "none"),
        ("mimo", "mimo-v2.6-flash", "none"),
        ("kimi", "kimi-k3", "low"),
        ("cli_proxy", "gpt-5.6-luna", "none"),
    ],
)
def test_suggestions_fixed_within_provider(provider, model, effort):
    settings = Settings.from_mapping({"active_provider": provider})
    assert input_suggestion_model_name(settings) == model
    assert input_suggestion_model_settings(settings).reasoning.effort == effort
