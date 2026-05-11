from __future__ import annotations

from deepy.config.settings import ModelConfig, Settings
from deepy.status import build_status_report, format_status_report


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
    assert f"Project: {tmp_path}" in rendered
    assert "Git dirty:" in rendered
