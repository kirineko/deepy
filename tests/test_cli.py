from __future__ import annotations

from deepy.cli import main


def test_config_show_json_masks_secret(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-1234567890"\n', encoding="utf-8")

    code = main(["--config", str(config), "config", "show", "--json"])

    assert code == 0
    out = capsys.readouterr().out
    assert "sk-1...7890" in out
    assert "sk-1234567890" not in out


def test_config_show_toml_omits_none_values(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text("[model]\nname = \"deepseek-v4-flash\"\n", encoding="utf-8")

    code = main(["--config", str(config), "config", "show"])

    assert code == 0
    out = capsys.readouterr().out
    assert "[model]" in out
    assert "None" not in out
