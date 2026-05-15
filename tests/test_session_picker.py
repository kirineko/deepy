from __future__ import annotations

from deepy.ui.session_picker import ResumeSessionPreview
from deepy.ui.session_picker import format_resume_session_choices
from deepy.ui.session_picker import format_resume_session_label
from deepy.ui.session_picker import format_session_time


def test_format_session_time_formats_millisecond_timestamp():
    rendered = format_session_time(1_778_561_349_157)

    assert rendered.startswith("2026-")
    assert ":" in rendered


def test_format_resume_session_label_includes_title_status_time_and_history_estimate():
    label = format_resume_session_label(
        ResumeSessionPreview(
            id="abc123456789",
            title="当前项目有哪些核心文件？",
            status="completed",
            updated_at=1_778_561_349_157,
            active_tokens=1559,
        )
    )

    assert "当前项目有哪些核心文件？" in label
    assert "completed" in label
    assert "history estimate 1,559" in label
    assert "abc12345" in label


def test_format_resume_session_choices_shows_total_and_numbered_previews():
    rendered = format_resume_session_choices(
        [
            ResumeSessionPreview("s1", "你好", "completed", 1000, 10),
            ResumeSessionPreview("s2", "hi", "failed", 2000, 20),
        ]
    )

    assert "Resume a session (2 total)" in rendered
    assert "1. 你好" in rendered
    assert "2. hi" in rendered
    assert "failed" in rendered
