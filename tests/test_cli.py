from __future__ import annotations

import asyncio
import json
import sys
from argparse import Namespace

from deepy.cli import _doctor, main
from deepy.sessions import DeepyJsonlSession


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
    assert "reserved_context_tokens = 50000" in text
    assert "compact_preserve_recent_messages = 2" in text
    assert "compact_prompt_token_threshold" not in text
    assert "[logging]" in text
    assert "[notify]" in text
    assert "[tools.web_search]" in text
    assert 'searxng_url = "https://s.kirineko.tech/"' in text
    assert "[ui]" in text
    assert 'theme = "auto"' in text


def test_config_setup_writes_toml_with_secure_prompt(tmp_path, capsys, monkeypatch):
    config = tmp_path / "config.toml"
    answers = iter(["sk-live", "deepseek-v4-flash", "https://api.deepseek.com", "3"])
    prompts: list[dict[str, object]] = []

    class FakePromptSession:
        def prompt(self, prompt, default="", is_password=False):
            prompts.append({"prompt": prompt, "default": default, "is_password": is_password})
            return next(answers)

    monkeypatch.setattr("prompt_toolkit.PromptSession", FakePromptSession)

    code = main(["--config", str(config), "config", "setup"])

    assert code == 0
    assert "https://platform.deepseek.com/api_keys" in capsys.readouterr().out
    assert prompts[0]["is_password"] is True
    assert config.stat().st_mode & 0o777 == 0o600
    text = config.read_text(encoding="utf-8")
    assert 'api_key = "sk-live"' in text
    assert 'name = "deepseek-v4-flash"' in text
    assert 'theme = "light"' in text


def test_config_reset_removes_existing_config_and_runs_setup(tmp_path, capsys, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "old-key"\n\n[ui]\ntheme = "dark"\n', encoding="utf-8")
    answers = iter(["sk-reset", "deepseek-v4-pro", "https://api.deepseek.com", "3"])

    class FakePromptSession:
        def prompt(self, prompt, default="", is_password=False):
            return next(answers)

    monkeypatch.setattr("prompt_toolkit.PromptSession", FakePromptSession)

    code = main(["--config", str(config), "config", "reset"])

    assert code == 0
    output = capsys.readouterr().out
    assert f"Removed {config}" in output
    assert "Starting Deepy configuration setup..." in output
    assert config.stat().st_mode & 0o777 == 0o600
    text = config.read_text(encoding="utf-8")
    assert "old-key" not in text
    assert 'api_key = "sk-reset"' in text
    assert 'theme = "light"' in text


def test_config_theme_shows_and_updates_theme(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-test"\n', encoding="utf-8")

    show_code = main(["--config", str(config), "config", "theme"])
    update_code = main(["--config", str(config), "config", "theme", "light"])

    output = capsys.readouterr().out
    assert show_code == 0
    assert update_code == 0
    assert "saved: auto" in output
    assert "resolved: dark" in output
    assert "Saved UI theme: light" in output
    assert 'theme = "light"' in config.read_text(encoding="utf-8")


def test_config_theme_rejects_invalid_value_without_changing_config(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ntheme = "dark"\n', encoding="utf-8")

    code = main(["--config", str(config), "config", "theme", "solarized"])

    assert code == 1
    assert "Invalid theme" in capsys.readouterr().err
    assert config.read_text(encoding="utf-8") == '[ui]\ntheme = "dark"\n'


def test_config_init_refuses_to_overwrite_without_force(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text("existing", encoding="utf-8")

    code = main(["--config", str(config), "config", "init"])

    assert code == 1
    assert "Config already exists" in capsys.readouterr().err
    assert config.read_text(encoding="utf-8") == "existing"


def test_interactive_mode_requires_tty(monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    try:
        main([])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("main([]) should exit when stdin is not a TTY")

    assert "interactive mode requires a TTY" in capsys.readouterr().err


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


def test_run_reports_missing_skill_without_traceback(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-test"\n', encoding="utf-8")

    code = main(["--config", str(config), "run", "--skill", "missing", "hello"])

    assert code == 1
    assert "deepy run failed: Skill not found: missing" in capsys.readouterr().err


def test_sessions_show_prints_items(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
    asyncio.run(session.add_items([{"role": "user", "content": "hello"}]))

    code = main(["sessions", "show", "s1"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "session_id": "s1",
        "usage": None,
        "items": [{"role": "user", "content": "hello"}],
    }


def test_status_command_prints_status(tmp_path, capsys, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-test"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = main(["--config", str(config), "status"])

    assert code == 0
    out = capsys.readouterr().out
    assert f"Project: {tmp_path}" in out
    assert "Reasoning: max" in out
    assert "API key: configured" in out


def test_status_command_prints_json(tmp_path, capsys, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-test"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = main(["--config", str(config), "status", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["project_root"] == str(tmp_path)
    assert payload["reasoning_mode"] == "max"
    assert payload["api_key_configured"] is True


def test_doctor_checks_config_permissions(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-test"\n', encoding="utf-8")
    config.chmod(0o644)

    code, report = _doctor(Namespace(config=config))

    assert code == 1
    permissions = next(item for item in report["checks"] if item["name"] == "config_permissions")
    assert permissions["ok"] is False
    assert "expected private permissions" in permissions["detail"]


def test_doctor_json_without_key_fails_with_setup_hint(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    config.chmod(0o600)

    code = main(["--config", str(config), "doctor", "--json"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    api_key = next(item for item in payload["checks"] if item["name"] == "api_key")
    assert api_key["ok"] is False
    assert api_key["detail"] == "missing; run `deepy config setup`"


def test_doctor_live_json_reports_usage(tmp_path, capsys, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-test"\n', encoding="utf-8")
    config.chmod(0o600)

    async def fake_live(settings):
        return {
            "ok": True,
            "model": settings.model.name,
            "base_url": settings.model.base_url,
            "response_summary": "OK",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr("deepy.cli._doctor_live", fake_live)

    code = main(["--config", str(config), "doctor", "--live", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["live"]["response_summary"] == "OK"
    assert payload["live"]["usage"]["total_tokens"] == 2
