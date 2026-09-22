"""Both interfaces must reject removed IDs without mutating selections."""

import pytest
from rich.console import Console

from deepy.config import load_settings, write_config
from deepy.ui.classic.slash_commands import _handle_slash_command
from deepy.ui import SlashCommand
from deepy.ui.modern.app import DeepyTuiApp


@pytest.mark.parametrize("model", ["mimo-v2.6-flash", "mimo-v2.6-pro"])
def test_classic_mimo_selection_and_retirement(tmp_path, model):
    path = tmp_path / "config.toml"
    write_config(path, provider="mimo", model="mimo-v2.6-flash", api_key="test", theme="dark")
    console = Console(record=True, width=160)
    _handle_slash_command(SlashCommand("model", f"set mimo {model} enabled"),
                          console, tmp_path, None, settings=load_settings(path))
    assert load_settings(path).model.name == model
    before = path.read_bytes()
    for old, new in (("mimo-v2.5", "mimo-v2.6-flash"), ("mimo-v2.5-pro", "mimo-v2.6-pro")):
        _handle_slash_command(SlashCommand("model", f"set mimo {old} enabled"),
                              console, tmp_path, None, settings=load_settings(path))
        rendered = console.export_text()
        assert new in rendered and "Removed MiMo model" in rendered
        assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_modern_mimo_selection_and_retirement(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    write_config(path, provider="mimo", model="mimo-v2.6-flash", api_key="test", theme="dark")
    async def no_turn(*args, **kwargs):
        raise AssertionError("Model selection must not invoke a model")

    app = DeepyTuiApp(settings=load_settings(path), project_root=tmp_path, run_once=no_turn)
    async with app.run_test(size=(100, 32)):
        for model in ("mimo-v2.6-pro", "mimo-v2.6-flash"):
            await app._model_command(f"set mimo {model} enabled")
            assert app.settings.model.name == model
            assert load_settings(path).model.name == model
        before = path.read_bytes()
        captured = []

        async def capture(block):
            captured.append(block)

        monkeypatch.setattr(app, "_append_block", capture)
        for old in ("mimo-v2.5", "mimo-v2.5-pro"):
            await app._model_command(f"set mimo {old} enabled")
            assert "Removed MiMo model" in captured[-1].body
            assert app.settings.model.name == "mimo-v2.6-flash"
            assert path.read_bytes() == before
