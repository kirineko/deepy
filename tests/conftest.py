"""Keep offline tests independent from the developer's configured provider accounts."""

import pytest


@pytest.fixture(autouse=True)
def isolate_provider_credentials(monkeypatch, tmp_path):
    for name in (
        "DEEPSEEK_API_KEY",
        "MIMO_API_KEY",
        "KIMI_API_KEY",
        "MOONSHOT_API_KEY",
        "CLI_PROXY_API_KEY",
        "DEEPY_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "deepy.config.config_io.default_config_path", lambda: tmp_path / "default-config.toml"
    )


@pytest.fixture
def text_only_mimo_pro(monkeypatch):
    """Synthetic capability override; both production V2.6 models accept images."""
    from dataclasses import replace
    from deepy.config.providers import PROVIDER_BY_ID

    info = PROVIDER_BY_ID["mimo"]
    monkeypatch.setitem(PROVIDER_BY_ID, "mimo", replace(
        info, models=tuple(replace(model, supports_image_input=False)
                           if model.name == "mimo-v2.6-pro" else model
                           for model in info.models)))
