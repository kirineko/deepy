from __future__ import annotations

from argparse import Namespace

from deepy.cli import _doctor, main


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


def test_skills_list_prints_project_skills(tmp_path, capsys, monkeypatch):
    skill_dir = tmp_path / ".deepy" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code = main(["skills", "list"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Project skills:" in out
    assert "demo - Demo skill" in out


def test_skills_show_prints_skill_body(tmp_path, capsys, monkeypatch):
    skill_dir = tmp_path / ".deepy" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Body\nUse this skill.",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code = main(["skills", "show", "demo"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Use this skill." in out
    assert "description:" not in out


def test_doctor_checks_config_permissions(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-test"\n', encoding="utf-8")
    config.chmod(0o644)

    code, report = _doctor(Namespace(config=config))

    assert code == 1
    permissions = next(item for item in report["checks"] if item["name"] == "config_permissions")
    assert permissions["ok"] is False
    assert "expected private permissions" in permissions["detail"]
