from __future__ import annotations

import asyncio
import json

import pytest

from deepy.config import Settings
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary
from deepy.tui.app import DeepyTuiApp
from deepy.tui.widgets import (
    AssistantBlock,
    DiffBlock,
    ErrorBlock,
    InfoBlock,
    PromptPanel,
    PromptTextArea,
    ThinkingBlock,
    ToolBlock,
    UsageLine,
    UserBlock,
)
from deepy.usage import TokenUsage


async def _idle_run_once(prompt: str, **kwargs) -> RunSummary:
    return RunSummary(output=f"answer: {prompt}", session_id="s1", complete=True)


@pytest.mark.asyncio
async def test_tui_starts_and_exits_headless(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        assert app.query_one("#prompt-input", PromptTextArea).has_focus
        assert app.query_one(InfoBlock).body.startswith("Experimental Textual TUI.")
        assert app.query(InfoBlock).first() is not None
        await pilot.press("ctrl+o")
        assert app.query_one("#side-panel").has_class("-visible")
        app.exit()


@pytest.mark.asyncio
async def test_tui_exit_slash_command_exits_without_model_turn(tmp_path, monkeypatch) -> None:
    calls: list[str] = []
    exited: list[bool] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        calls.append(prompt)
        return RunSummary(output="unexpected", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: exited.append(True))

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/exit"
        await pilot.press("enter")
        await pilot.pause(0.1)

        assert exited == [True]
        assert calls == []


@pytest.mark.asyncio
async def test_tui_reuses_session_id_between_turns(tmp_path) -> None:
    calls: list[tuple[str, str | None]] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        session_id = kwargs.get("session_id")
        calls.append((prompt, session_id))
        return RunSummary(output=f"answer: {prompt}", session_id=session_id or "s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "first"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert app.state.session_id == "s1"

        prompt.text = "second"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert calls == [("first", None), ("second", "s1")]
        app.exit()


@pytest.mark.asyncio
async def test_tui_prompt_newline_slash_and_file_suggestions(tmp_path) -> None:
    tmp_path.joinpath("src").mkdir()
    tmp_path.joinpath("src", "app.py").write_text("print('hi')\n", encoding="utf-8")
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        panel = app.query_one(PromptPanel)

        prompt.text = "hello"
        prompt.move_cursor((0, len(prompt.text)))
        await pilot.press("shift+enter")
        assert prompt.text == "hello\n"

        panel.refresh_suggestions("/")
        assert any(suggestion.startswith("/model") for suggestion in panel.suggestions)

        panel.refresh_suggestions("@src/")
        assert "@src/app.py" in panel.suggestions
        app.exit()


@pytest.mark.asyncio
async def test_tui_skills_use_loads_skill_without_printing_body(tmp_path) -> None:
    skill_dir = tmp_path / ".agents" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\nVERY LONG SKILL BODY",
        encoding="utf-8",
    )
    calls: list[tuple[str, list[str]]] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        calls.append((prompt, kwargs["skill_names"]))
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/skills use demo"
        await pilot.press("enter")
        await pilot.pause(0.1)

        assert not calls
        transcript_text = "\n".join(block.body for block in app.query(UserBlock))
        assert "Loaded skill: demo" in transcript_text
        assert "VERY LONG SKILL BODY" not in transcript_text

        prompt.text = "use it"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert calls == [("use it", ["demo"])]
        app.exit()


@pytest.mark.asyncio
async def test_tui_load_skill_tool_output_is_summarized(tmp_path) -> None:
    tool_output = json.dumps(
        {
            "ok": True,
            "name": "load_skill",
            "output": "# Skill: demo\n\nVERY LONG SKILL BODY",
            "error": None,
            "metadata": {
                "name": "demo",
                "description": "Demo skill",
                "root": str(tmp_path / ".agents" / "skills" / "demo"),
            },
            "awaitUserResponse": False,
        }
    )

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        kwargs["emit_event"](
            DeepyStreamEvent(
                kind="tool_output",
                text=tool_output,
                payload={"call_id": "load-1"},
            )
        )
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "load skill"
        await pilot.press("enter")
        await pilot.pause(0.2)

        block = app.query_one(ToolBlock)
        assert block.title == "Load Skill ok - demo"
        assert "Loaded skill: demo" in block.body
        assert "VERY LONG SKILL BODY" not in block.body
        app.exit()


@pytest.mark.asyncio
async def test_tui_stream_events_render_transcript_blocks(tmp_path) -> None:
    tool_output = json.dumps(
        {
            "ok": True,
            "name": "write",
            "output": "Wrote file",
            "error": None,
            "metadata": {
                "path": "src/app.py",
                "diff": "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n",
            },
            "awaitUserResponse": False,
        }
    )

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        emit_event = kwargs["emit_event"]
        emit_event(DeepyStreamEvent(kind="reasoning_delta", text="thinking"))
        emit_event(DeepyStreamEvent(kind="text_delta", text="hello"))
        emit_event(
            DeepyStreamEvent(
                kind="tool_call",
                name="write",
                payload={"call_id": "call-1", "arguments": '{"path":"src/app.py"}'},
            )
        )
        emit_event(
            DeepyStreamEvent(
                kind="tool_output",
                text=tool_output,
                payload={"call_id": "call-1"},
            )
        )
        return RunSummary(
            output="hello",
            session_id="s1",
            complete=True,
            usage=TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        )

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "change it"
        await pilot.press("enter")
        await pilot.pause(0.2)

        thinking = app.query_one(ThinkingBlock)
        assert thinking.title == "Thinking"
        assert thinking.body == "thinking"
        assert app.query_one(AssistantBlock).markdown == "hello"
        tool_block = app.query_one(ToolBlock)
        assert tool_block.title == "Write ok - src/app.py"
        assert "Parameters\n  src/app.py" in tool_block.body
        assert "Output\n  Wrote file" in tool_block.body
        assert "src/app.py" in app.query_one(DiffBlock).body
        usage = app.query_one(UsageLine)
        assert usage.body == "input 1 · output 2 · total 3"
        assert usage.line.startswith("Usage  input 1")
        ordered = [type(block).__name__ for block in app.query(".transcript-block")]
        assert ordered.index("AssistantBlock") > ordered.index("ToolBlock")
        app.exit()


@pytest.mark.asyncio
async def test_tui_ignores_final_message_after_text_delta_to_avoid_duplicate_output(
    tmp_path,
) -> None:
    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        emit_event = kwargs["emit_event"]
        emit_event(DeepyStreamEvent(kind="text_delta", text="你好"))
        emit_event(DeepyStreamEvent(kind="text_delta", text="，世界"))
        emit_event(DeepyStreamEvent(kind="message", text="你好，世界"))
        return RunSummary(output="你好，世界", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "hello"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert [block.markdown for block in app.query(AssistantBlock)] == ["你好，世界"]
        app.exit()


@pytest.mark.asyncio
async def test_tui_uses_message_event_when_no_text_delta_was_streamed(tmp_path) -> None:
    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        kwargs["emit_event"](DeepyStreamEvent(kind="message", text="final only"))
        return RunSummary(output="final only", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "hello"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert [block.markdown for block in app.query(AssistantBlock)] == ["final only"]
        app.exit()


@pytest.mark.asyncio
async def test_tui_interleaves_thinking_and_tool_calls_in_stream_order(tmp_path) -> None:
    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        emit_event = kwargs["emit_event"]
        emit_event(DeepyStreamEvent(kind="reasoning_delta", text="first"))
        emit_event(
            DeepyStreamEvent(
                kind="tool_call",
                name="WebFetch",
                payload={"call_id": "fetch-1", "arguments": '{"url":"https://example.com"}'},
            )
        )
        emit_event(DeepyStreamEvent(kind="reasoning_delta", text="second"))
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "fetch"
        await pilot.press("enter")
        await pilot.pause(0.2)

        blocks = list(app.query(".transcript-block"))
        ordered = [
            (type(block).__name__, getattr(block, "body", ""))
            for block in blocks
            if isinstance(block, ThinkingBlock | ToolBlock)
        ]
        assert ordered == [
            ("ThinkingBlock", "first"),
            ("ToolBlock", "Parameters\n  https://example.com"),
            ("ThinkingBlock", "second"),
        ]
        app.exit()


@pytest.mark.asyncio
async def test_tui_autoscrolls_when_live_block_grows(tmp_path) -> None:
    release = asyncio.Event()

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        emit_event = kwargs["emit_event"]
        for index in range(80):
            emit_event(DeepyStreamEvent(kind="reasoning_delta", text=f"line {index}\n"))
            await asyncio.sleep(0)
        await release.wait()
        return RunSummary(output="", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(80, 12)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "think"
        await pilot.press("enter")
        await pilot.pause(0.5)

        transcript = app.query_one("#transcript")
        assert transcript.max_scroll_y > 0
        assert transcript.scroll_y == transcript.max_scroll_y

        release.set()
        await pilot.pause(0.2)
        app.exit()


@pytest.mark.asyncio
async def test_tui_tool_output_is_compacted(tmp_path) -> None:
    long_output = "\n".join(f"line {index}" for index in range(30))
    tool_output = json.dumps(
        {
            "ok": True,
            "name": "WebFetch",
            "output": long_output,
            "error": None,
            "metadata": {"url": "https://example.com"},
            "awaitUserResponse": False,
        }
    )

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        kwargs["emit_event"](
            DeepyStreamEvent(
                kind="tool_call",
                name="WebFetch",
                payload={"call_id": "fetch-1", "arguments": '{"url":"https://example.com"}'},
            )
        )
        kwargs["emit_event"](
            DeepyStreamEvent(
                kind="tool_output",
                text=tool_output,
                payload={"call_id": "fetch-1"},
            )
        )
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "fetch"
        await pilot.press("enter")
        await pilot.pause(0.2)

        body = app.query_one(ToolBlock).body
        assert "Parameters\n  https://example.com" in body
        assert "Output\n  line 0" in body
        assert "line 7" in body
        assert "line 8" not in body
        assert "... output truncated ..." in body
        app.exit()


@pytest.mark.asyncio
async def test_tui_stream_errors_render_error_block(tmp_path) -> None:
    async def failing_run_once(prompt: str, **kwargs) -> RunSummary:
        raise RuntimeError(f"failed: {prompt}")

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=failing_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "break"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert app.query_one(ErrorBlock).body == "failed: break"
        assert app.state.status == "Error"
        app.exit()
