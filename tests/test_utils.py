from __future__ import annotations

import errno
import json
from pathlib import Path

from deepy.utils import (
    build_notify_env,
    debug_log_path,
    error_log_path,
    format_duration_seconds,
    launch_notify_script,
    log_api_error,
    log_debug_event,
    mask_sensitive,
)


def test_notify_env_injects_duration():
    assert format_duration_seconds(2750) == "2"
    assert format_duration_seconds(-1) == "0"

    env = build_notify_env(2750, {"HOME": "/tmp/home"})

    assert env["HOME"] == "/tmp/home"
    assert env["DURATION"] == "2"


def test_launch_notify_script_uses_fallback_shell_for_non_executable_script(tmp_path):
    calls: list[tuple[list[str], dict]] = []

    def fake_spawn(command, **options):
        calls.append((command, options))
        if len(calls) == 1:
            raise OSError(errno.EACCES, "permission denied")
        return object()

    launch_notify_script(
        "/tmp/notify.sh",
        2750,
        tmp_path,
        spawn_process=fake_spawn,
    )

    assert calls[0][0] == ["/tmp/notify.sh"]
    assert calls[0][1]["cwd"] == str(tmp_path)
    assert calls[0][1]["env"]["DURATION"] == "2"
    assert calls[1][0] == ["/bin/sh", "/tmp/notify.sh"]


def test_log_debug_event_writes_jsonl_and_never_raises(tmp_path):
    circular = {}
    circular["self"] = circular

    log_debug_event({"path": Path("x"), "value": circular}, deepy_home=tmp_path)

    path = debug_log_path(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["path"] == "x"
    assert payload["value"]["self"] == "[Circular]"


def test_log_api_error_masks_sensitive_values_and_trims_log(tmp_path):
    assert (
        mask_sensitive("Authorization: Bearer sk-secret api_key=sk-value")
        == "Authorization: Bearer ***MASKED*** api_key=***MASKED***"
    )

    for index in range(25):
        log_api_error(
            {
                "timestamp": f"t-{index}",
                "location": "runner",
                "requestId": f"r-{index}",
                "error": {
                    "name": "HTTPError",
                    "message": "Authorization: Bearer sk-secret api_key=sk-value",
                },
                "request": {"messages": [{"content": "x" * 120}]},
                "response": "secret=sk-response",
            },
            deepy_home=tmp_path,
        )

    path = error_log_path(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 20
    assert json.loads(lines[0])["requestId"] == "r-5"
    latest = json.loads(lines[-1])
    assert latest["error"]["message"] == (
        "Authorization: Bearer ***MASKED*** api_key=***MASKED***"
    )
    assert latest["request"]["messages"][0]["content"].endswith("(total 120 chars)")
    assert latest["response"] == "secret=***MASKED***"
