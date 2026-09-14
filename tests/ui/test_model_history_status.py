import asyncio
from dataclasses import replace

import pytest
from rich.console import Console

from deepy.config import Settings
from deepy.llm.cache_context import build_cache_prefix_snapshot
from deepy.llm.work_boundary import generation_boundary, switch_error, interrupt_check
from deepy.llm.history_migration import summarize_bounded
from deepy.sessions import DeepySession, list_session_entries
from deepy.sessions.history_state import record_checkpoint
from deepy.ui.shared.context_status import context_label
from deepy.ui.classic.slash_commands import _handle_slash_command
from deepy.ui.shared.input.commands import SlashCommand
from deepy.ui.modern.app import DeepyTuiApp
from deepy.ui.modern.widgets import ErrorBlock
from deepy.usage import TokenUsage


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    from pathlib import Path
    home = tmp_path / "isolated-home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))


@pytest.mark.asyncio
async def test_reported_checkpoint_switch_and_resume_display(tmp_path):
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    settings = Settings()
    prefix = build_cache_prefix_snapshot(settings, system_instructions="system")
    await session.add_items([{"role": "user", "content": "hello"}])
    session.record_cache_prefix_snapshot(prefix)
    session.record_usage({"input_tokens": 5000, "output_tokens": 100})
    record_checkpoint(session, settings, prefix.fingerprint)
    entry = list_session_entries(tmp_path, deepy_home=tmp_path / "home")[0]
    assert "5.1K/1M~" in context_label(entry, settings)
    assert context_label(entry, settings) == "ctx 5.1K/1M~ (0.5%)"
    proxy = Settings.from_mapping({"active_provider": "cli_proxy"})
    assert "1.05M?" in context_label(entry, proxy)
    assert "ctx ~" in context_label(entry, proxy)
    assert "proxy-unverified" not in context_label(entry, proxy)
    assert context_label(entry, settings) == "ctx 5.1K/1M~ (0.5%)"
    changed = replace(entry, cache_prefix_fingerprint="changed")
    assert "ctx ~" in context_label(changed, settings)


@pytest.mark.asyncio
async def test_classic_rejects_switch_under_generation_lease(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('config_version = 2\n')
    settings = Settings.from_mapping({}, path=path)
    console = Console(record=True)
    @generation_boundary
    async def active(*, project_root):
        assert switch_error(project_root)
        _handle_slash_command(SlashCommand("model", "provider mimo"), console,
                              project_root, None, settings=settings)
    await active(project_root=tmp_path)
    assert "Model unchanged" in console.export_text()
    assert path.read_text() == 'config_version = 2\n'
    assert switch_error(tmp_path) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("busy,pending", [(True, False), (False, True)])
async def test_modern_rejects_busy_or_unresolved_tool_switch(tmp_path, busy, pending):
    path = tmp_path / "config.toml"
    path.write_text('config_version = 2\n')
    settings = Settings.from_mapping({}, path=path)
    async def unused(*args, **kwargs):
        raise AssertionError("No model call on selection")
    app = DeepyTuiApp(settings=settings, project_root=tmp_path, run_once=unused)
    async with app.run_test(size=(100, 32)):
        app.state = replace(app.state, busy=busy, pending_tool_calls={"call": "Read"} if pending else {})
        await app._model_command("provider mimo")
        assert app.settings is settings
        assert any("Model unchanged" in block.body for block in app.query(ErrorBlock))
        assert path.read_text() == 'config_version = 2\n'
        app.state = replace(app.state, busy=False, pending_tool_calls={})
        app.exit()


@pytest.mark.asyncio
async def test_summary_cancellation_interrupts_running_call(tmp_path):
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    started = asyncio.Event()
    cancelled = asyncio.Event()
    interrupt = False
    async def summarize(*args, **kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        return "never", TokenUsage()
    token = interrupt_check.set(lambda: interrupt)
    try:
        task = asyncio.create_task(summarize_bounded([{"role": "user", "content": "hello"}],
                                                    Settings(), session=session, summarize=summarize))
        await started.wait()
        interrupt = True
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)
        assert cancelled.is_set()
        assert await session.get_items() == []
    finally:
        interrupt_check.reset(token)


@pytest.mark.asyncio
async def test_modern_preparation_failure_restores_text_and_images(tmp_path):
    from deepy.llm.runner import RunSummary
    from deepy.ui.modern.widgets import PromptTextArea
    async def fail(*args, **kwargs):
        return RunSummary(output="History blocked; use /compact --for-model.", session_id="blocked",
                          complete=False, status="context_compaction_failed")
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fail)
    async with app.run_test(size=(100, 32)) as pilot:
        image = app.image_attachments.attach_image(b"image", "image/png")
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = f"continue {image.display_label}"
        await pilot.press("enter")
        for _ in range(30):
            await pilot.pause(0.02)
            if "History not ready" in app.state.status:
                break
        assert "continue" in prompt.text
        assert image.display_label in prompt.text
        assert app.image_attachments.attachments == [image]
        assert any("History blocked" in block.body for block in app.query(ErrorBlock))
        app.exit()


@pytest.mark.asyncio
async def test_modern_exact_for_model_option_keeps_unsubmitted_attachments(tmp_path, monkeypatch):
    from deepy.ui.modern.widgets import PromptTextArea
    from deepy.llm.compaction import CompactionResult
    calls = []
    async def compact(self, session_id, *, focus_instruction=None, **kwargs):
        calls.append(focus_instruction)
        return CompactionResult(session_id=session_id, compacted=False, reason="manual",
                                before_tokens=0, after_tokens=0, preserved_item_count=0)
    monkeypatch.setattr("deepy.ui.modern.app.DeepySessionManager.compact_session", compact)
    async def unused(*args, **kwargs):
        raise AssertionError("Commands must not send a model request")
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=unused)
    async with app.run_test(size=(100, 32)) as pilot:
        app.state = replace(app.state, session_id="s1")
        image = app.image_attachments.attach_image(b"image", "image/png")
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = f"/compact --for-model {image.display_label}"
        await pilot.press("enter")
        for _ in range(30):
            await pilot.pause(0.02)
            if calls:
                break
        assert calls == ["--for-model"]
        assert app.image_attachments.attachments == [image]
        app.exit()


@pytest.mark.parametrize("value,expected", [(0, "0"), (999, "999"), (1000, "1K"),
    (12521, "12.5K"), (999950, "1M"), (1000000, "1M"), (1050000, "1.05M")])
def test_context_token_units(value, expected):
    from deepy.ui.shared.context_status import compact_tokens
    assert compact_tokens(value) == expected


def test_context_footer_is_compact_but_diagnostics_keep_details():
    from types import SimpleNamespace
    from deepy.llm.history_projection import model_identity
    from deepy.ui.shared.context_status import context_display
    settings = Settings()
    entry = SimpleNamespace(history_state={"checkpoint": {
        "target": model_identity(settings.model.provider, settings.model.name, settings.model.base_url),
        "prefix": "prefix"}}, cache_prefix_fingerprint="prefix", latest_context_window_tokens=12521,
        pending_tokens=0, active_tokens=12521)
    assert context_label(entry, settings) == "ctx 12.5K/1M~ (1.3%)"
    assert context_display(entry, settings) == (12521, "reported")
    entry.latest_context_window_tokens = 800000
    assert context_label(entry, settings) == "ctx 800K/1M~ (80.0%) !"
    assert context_label(None, settings) == "ctx -/1M~"
    assert len(context_label(entry, settings)) < 30
