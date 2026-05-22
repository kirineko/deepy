from __future__ import annotations

import sys
import time

from deepy.background_tasks import BackgroundTaskLimitError, BackgroundTaskManager


def _python_command(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_background_task_completes_and_captures_output(tmp_path):
    manager = BackgroundTaskManager(base_dir=tmp_path)

    task = manager.start(
        command="print ok",
        argv=_python_command("print('ok')"),
        cwd=tmp_path,
    )
    settled = manager.wait(task.id, timeout_seconds=5)
    output = manager.read_output(task.id)

    assert settled is not None
    assert settled.status == "completed"
    assert settled.exit_code == 0
    assert settled.end_time is not None
    assert output is not None
    assert output.output.strip() == "ok"
    assert output.output_size_bytes >= 3
    assert output.more_available is False


def test_background_task_failure_records_exit_code(tmp_path):
    manager = BackgroundTaskManager(base_dir=tmp_path)

    task = manager.start(
        command="fail",
        argv=_python_command("import sys; print('bad'); sys.exit(7)"),
        cwd=tmp_path,
    )
    settled = manager.wait(task.id, timeout_seconds=5)

    assert settled is not None
    assert settled.status == "failed"
    assert settled.exit_code == 7
    assert "code 7" in (settled.error or "")


def test_background_task_output_tail_reports_truncation(tmp_path):
    manager = BackgroundTaskManager(base_dir=tmp_path)

    task = manager.start(
        command="write lines",
        argv=_python_command("import sys; sys.stdout.write('abcdef')"),
        cwd=tmp_path,
    )
    manager.wait(task.id, timeout_seconds=5)
    output = manager.read_output(task.id, max_bytes=3)

    assert output is not None
    assert output.output == "def"
    assert output.output_size_bytes == 6
    assert output.output_preview_bytes == 3
    assert output.output_truncated is True
    assert output.more_available is True


def test_background_task_wait_for_output_returns_when_output_arrives(tmp_path):
    manager = BackgroundTaskManager(base_dir=tmp_path)
    task = manager.start(
        command="delayed output",
        argv=[
            sys.executable,
            "-c",
            "import time; time.sleep(.1); print('ready', flush=True); time.sleep(1)",
        ],
        cwd=tmp_path,
    )

    snapshot = manager.wait_for_output(task.id, timeout_seconds=1)
    output = manager.read_output(task.id)
    manager.stop_all(force_after_grace=True)

    assert snapshot is not None
    assert output is not None
    assert "ready" in output.output


def test_background_task_wait_for_output_does_not_wait_for_long_running_completion(tmp_path):
    manager = BackgroundTaskManager(base_dir=tmp_path)
    task = manager.start(
        command="quiet server",
        argv=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
    )
    started = time.monotonic()

    snapshot = manager.wait_for_output(task.id, timeout_seconds=0.1)
    elapsed = time.monotonic() - started
    manager.stop_all(force_after_grace=True)

    assert snapshot is not None
    assert snapshot.status == "running"
    assert elapsed < 0.5


def test_background_task_stop_is_idempotent(tmp_path):
    manager = BackgroundTaskManager(base_dir=tmp_path, stop_grace_seconds=0.1)

    task = manager.start(
        command="sleep",
        argv=_python_command("import time; time.sleep(30)"),
        cwd=tmp_path,
    )
    first = manager.stop(task.id, force_after_grace=True)
    second = manager.stop(task.id, force_after_grace=True)

    assert first is not None
    assert first.stop_requested is True
    assert second is not None
    assert second.status == "stopped"
    assert manager.wait(task.id, timeout_seconds=1).status == "stopped"  # type: ignore[union-attr]


def test_background_task_limit_rejects_new_launch(tmp_path):
    manager = BackgroundTaskManager(base_dir=tmp_path, max_running_tasks=1)
    task = manager.start(
        command="sleep",
        argv=_python_command("import time; time.sleep(30)"),
        cwd=tmp_path,
    )

    try:
        try:
            manager.start(
                command="second",
                argv=_python_command("print('second')"),
                cwd=tmp_path,
            )
        except BackgroundTaskLimitError as exc:
            assert "limit reached" in str(exc)
        else:
            raise AssertionError("expected task limit failure")
    finally:
        manager.stop(task.id, force_after_grace=True)


def test_background_task_retention_keeps_running_and_prunes_terminal(tmp_path):
    manager = BackgroundTaskManager(base_dir=tmp_path, max_terminal_tasks=1)
    first = manager.start(command="first", argv=_python_command("print('first')"), cwd=tmp_path)
    manager.wait(first.id, timeout_seconds=5)
    time.sleep(0.02)
    second = manager.start(command="second", argv=_python_command("print('second')"), cwd=tmp_path)
    manager.wait(second.id, timeout_seconds=5)
    running = manager.start(
        command="running",
        argv=_python_command("import time; time.sleep(30)"),
        cwd=tmp_path,
    )

    try:
        ids = {task.id for task in manager.list()}
        assert first.id not in ids
        assert second.id in ids
        assert running.id in ids
    finally:
        manager.stop(running.id, force_after_grace=True)
