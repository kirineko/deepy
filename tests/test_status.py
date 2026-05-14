from __future__ import annotations

from deepy.config.settings import ModelConfig, Settings
from deepy.status import build_status_report, format_status_report, status_report_to_dict


def test_status_report_includes_counts_and_context(tmp_path):
    skill_dir = tmp_path / ".deepy" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo\n---\n",
        encoding="utf-8",
    )
    settings = Settings(model=ModelConfig(api_key="sk-test"))

    report = build_status_report(tmp_path, settings)
    rendered = format_status_report(report)

    assert report.skill_count == 1
    assert "API key: configured" in rendered
    assert "Reasoning: max" in rendered
    assert f"Project: {tmp_path}" in rendered
    assert "Git dirty:" in rendered


def test_status_report_to_dict_is_json_ready(tmp_path):
    report = build_status_report(tmp_path, Settings())

    payload = status_report_to_dict(report)

    assert payload["project_root"] == str(tmp_path)
    assert payload["model"] == "deepseek-v4-pro"
    assert payload["reasoning_mode"] == "max"
