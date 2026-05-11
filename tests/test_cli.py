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


def test_config_init_writes_toml_with_private_permissions(tmp_path, capsys):
    config = tmp_path / "config.toml"

    code = main(["--config", str(config), "config", "init", "--api-key", "sk-test"])

    assert code == 0
    assert "Wrote" in capsys.readouterr().out
    assert config.stat().st_mode & 0o777 == 0o600
    text = config.read_text(encoding="utf-8")
    assert 'api_key = "sk-test"' in text
    assert "compact_prompt_token_threshold = 838861" in text


def test_config_init_refuses_to_overwrite_without_force(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text("existing", encoding="utf-8")

    code = main(["--config", str(config), "config", "init"])

    assert code == 1
    assert "Config already exists" in capsys.readouterr().err
    assert config.read_text(encoding="utf-8") == "existing"
