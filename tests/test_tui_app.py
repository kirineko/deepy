from __future__ import annotations

import asyncio
import json

import pytest
from textual.widgets import Label, OptionList, TextArea
from textual.command import CommandPalette
from textual.widgets.option_list import Option

from deepy.config import Settings
from deepy.config import load_settings
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary
from deepy.tui.app import DeepyTuiApp
from deepy.tui.commands import DeepyCommandProvider
from deepy.tui.screens import ChoiceScreen, InfoScreen
from deepy.tui.widgets import (
    AssistantBlock,
    DiffBlock,
    ErrorBlock,
    InfoBlock,
    PromptPanel,
    PromptTextArea,
    QuestionBlock,
    ThinkingBlock,
    ToolBlock,
    UsageLine,
    UserBlock,
)
from deepy.sessions import DeepyJsonlSession
from deepy.usage import TokenUsage


async def _idle_run_once(prompt: str, **kwargs) -> RunSummary:
    return RunSummary(output=f"answer: {prompt}", session_id="s1", complete=True)


def _option_prompt_text(option: Option) -> str:
    prompt = option.prompt
    return getattr(prompt, "plain", str(prompt))


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

        panel.refresh_suggestions("/re")
        assert panel.suggestions
        assert all(suggestion.split(maxsplit=1)[0].startswith("/re") for suggestion in panel.suggestions)

        panel.refresh_suggestions("@src/")
        assert "@src/app.py" in panel.suggestions
        app.exit()


@pytest.mark.asyncio
async def test_tui_file_suggestions_support_keyboard_selection(tmp_path) -> None:
    tmp_path.joinpath("aaa.py").write_text("", encoding="utf-8")
    tmp_path.joinpath("bbb.py").write_text("", encoding="utf-8")
    tmp_path.joinpath("ui").mkdir()
    tmp_path.joinpath("ui", "panel.py").write_text("", encoding="utf-8")
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        panel = app.query_one(PromptPanel)
        options = app.query_one("#prompt-suggestions", OptionList)

        prompt.text = "@"
        await pilot.pause()
        assert options.display is True
        assert options.highlighted == 0

        await pilot.press("down")
        assert options.highlighted == 1

        await pilot.press("tab")
        assert options.highlighted == 2

        await pilot.press("up")
        assert options.highlighted == 1

        await pilot.press("enter")
        assert prompt.text == "@bbb.py "

        prompt.text = "@"
        await pilot.pause()
        assert options.highlighted == 0
        await pilot.press("tab")
        await pilot.press("tab")
        assert options.highlighted == 2
        await pilot.press("enter")
        assert prompt.text == "@ui/"
        assert "@ui/panel.py" in panel.suggestions
        app.exit()


@pytest.mark.asyncio
async def test_tui_slash_suggestions_tab_cycles_and_enter_confirms(tmp_path) -> None:
    calls: list[str] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        calls.append(prompt)
        return RunSummary(output="unexpected", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        options = app.query_one("#prompt-suggestions", OptionList)

        prompt.text = "/re"
        await pilot.pause()
        assert options.display is True
        assert options.highlighted == 0

        await pilot.press("tab")
        assert options.highlighted == 1

        await pilot.press("enter")
        assert prompt.text == "/reset "
        assert options.display is False
        assert calls == []
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
async def test_tui_preserves_scroll_position_and_new_output_indicator(tmp_path) -> None:
    first_batch_done = asyncio.Event()
    continue_output = asyncio.Event()

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        emit_event = kwargs["emit_event"]
        for index in range(80):
            emit_event(DeepyStreamEvent(kind="reasoning_delta", text=f"line {index}\n"))
            await asyncio.sleep(0)
        first_batch_done.set()
        await continue_output.wait()
        emit_event(DeepyStreamEvent(kind="reasoning_delta", text="late line\n"))
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(80, 12)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "fill transcript"
        await pilot.press("enter")
        await asyncio.wait_for(first_batch_done.wait(), timeout=1)
        await pilot.pause(0.1)

        transcript = app.query_one("#transcript")
        assert transcript.max_scroll_y > 0
        transcript.scroll_home(animate=False)
        await pilot.pause(0.1)
        assert transcript.scroll_y < transcript.max_scroll_y

        continue_output.set()
        await pilot.pause(0.2)

        assert transcript.scroll_y < transcript.max_scroll_y
        status = app.query_one("#status-right", Label)
        assert "New output below" in str(status.content)
        app.exit()


@pytest.mark.asyncio
async def test_tui_submitting_prompt_from_history_scrolls_to_bottom(tmp_path) -> None:
    calls = 0

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        nonlocal calls
        calls += 1
        emit_event = kwargs["emit_event"]
        if calls == 1:
            for index in range(80):
                emit_event(DeepyStreamEvent(kind="reasoning_delta", text=f"line {index}\n"))
                await asyncio.sleep(0)
        return RunSummary(output=f"ok {calls}", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(80, 12)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "fill transcript"
        await pilot.press("enter")
        await pilot.pause(0.5)

        transcript = app.query_one("#transcript")
        assert transcript.max_scroll_y > 0
        transcript.scroll_home(animate=False)
        await pilot.pause(0.1)
        assert transcript.scroll_y < transcript.max_scroll_y

        prompt.text = "new prompt"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert transcript.scroll_y == transcript.max_scroll_y
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


@pytest.mark.asyncio
async def test_tui_unknown_slash_command_is_not_sent_to_model(tmp_path) -> None:
    calls: list[str] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        calls.append(prompt)
        return RunSummary(output="unexpected", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/unknown"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert calls == []
        assert "Unsupported TUI command: /unknown" in app.query_one(ErrorBlock).body
        app.exit()


@pytest.mark.asyncio
async def test_tui_command_provider_discovers_and_searches_commands(tmp_path) -> None:
    calls: list[tuple[str, str]] = []

    def fake_invoke(name: str, argument: str = "") -> None:
        calls.append((name, argument))

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        app.invoke_tui_command = fake_invoke  # type: ignore[method-assign]
        provider = DeepyCommandProvider(app.screen)

        discovered = [hit async for hit in provider.discover()]
        assert any(hit.text == "/help" and hit.help == "Help: Show commands, keybindings, and TUI state" for hit in discovered)

        help_hit = next(hit for hit in discovered if hit.text == "/help")
        help_hit.command()
        assert calls == [("help", "")]

        searched = [hit async for hit in provider.search("mcp")]
        assert any(hit.text == "/mcp" and hit.help == "Tools: Show MCP status" for hit in searched)
        app.exit()


@pytest.mark.asyncio
async def test_tui_command_palette_closes_with_escape(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause(0.2)
        assert isinstance(app.screen, CommandPalette)

        await pilot.press("escape")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, CommandPalette)
        app.exit()


@pytest.mark.asyncio
async def test_tui_escape_still_requests_interrupt_while_busy(tmp_path) -> None:
    release = asyncio.Event()

    async def slow_run_once(prompt: str, **kwargs) -> RunSummary:
        await release.wait()
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=slow_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "long task"
        await pilot.press("enter")
        await pilot.pause(0.2)

        await pilot.press("escape")
        await pilot.pause(0.1)
        assert app.state.interrupt_requested is True
        assert app.state.status == "Interrupt requested"

        release.set()
        await pilot.pause(0.2)
        app.exit()


@pytest.mark.asyncio
async def test_tui_help_command_opens_info_screen(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/help"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert isinstance(app.screen, InfoScreen)
        assert "Deepy TUI Commands" in app.screen.markdown
        app.exit()


@pytest.mark.asyncio
async def test_tui_status_command_opens_status_screen(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/status"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert isinstance(app.screen, InfoScreen)
        assert "Project:" in app.screen.markdown
        assert "MCP:" in app.screen.markdown
        app.exit()


@pytest.mark.asyncio
async def test_tui_theme_and_model_direct_commands_persist_settings(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    settings = load_settings(config_path)
    app = DeepyTuiApp(settings=settings, project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/theme light"
        await pilot.press("enter")
        await pilot.pause(0.2)
        prompt.text = "/model set deepseek-v4-flash high"
        await pilot.press("enter")
        await pilot.pause(0.2)

        saved = load_settings(config_path)
        assert saved.ui.theme == "light"
        assert saved.model.name == "deepseek-v4-flash"
        assert saved.model.reasoning_mode == "high"
        app.exit()


@pytest.mark.asyncio
async def test_tui_new_command_resets_session_and_loaded_skills(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        app.state = app.state.__class__(session_id="old-session")
        app.controller.loaded_skill_names.append("demo")
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/new"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert app.state.session_id is None
        assert app.controller.loaded_skill_names == []
        assert "Started a new TUI session." in app.query_one(InfoBlock).body
        app.exit()


@pytest.mark.asyncio
async def test_tui_compact_command_reports_result(tmp_path, monkeypatch) -> None:
    class Result:
        compacted = True
        before_tokens = 100
        after_tokens = 40
        preserved_item_count = 2
        message = ""

    async def fake_compact(self, session_id: str, *, focus_instruction: str | None = None):
        assert session_id == "s1"
        assert focus_instruction == "keep decisions"
        return Result()

    monkeypatch.setattr("deepy.tui.app.DeepySessionManager.compact_session", fake_compact)
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        app.state = app.state.__class__(session_id="s1")
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/compact keep decisions"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert any("Context compacted" in block.body for block in app.query(InfoBlock))
        app.exit()


@pytest.mark.asyncio
async def test_tui_resumes_session_and_restores_transcript(tmp_path) -> None:
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
    write_output = json.dumps(
        {
            "ok": True,
            "name": "write",
            "output": "Wrote file",
            "error": None,
            "metadata": {
                "path": "selection_sort.py",
                "diff": "--- a/selection_sort.py\n+++ b/selection_sort.py\n@@ -1 +1 @@\n-old\n+new\n",
            },
            "awaitUserResponse": False,
        }
    )
    shell_output = json.dumps(
        {
            "ok": True,
            "name": "shell",
            "output": "排序后: [1, 2, 3]",
            "error": None,
            "metadata": {"command": "python selection_sort.py", "exitCode": 0},
            "awaitUserResponse": False,
        }
    )
    await session.add_items(
        [
            {"role": "user", "content": "hello"},
            {
                "type": "function_call",
                "call_id": "write-1",
                "name": "write",
                "arguments": '{"path":"selection_sort.py"}',
            },
            {"type": "function_call_output", "call_id": "write-1", "output": write_output},
            {"role": "assistant", "content": "Hi."},
            {"type": "function_call_output", "call_id": "shell-1", "output": shell_output},
        ]
    )
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/resume s1"
        await pilot.press("enter")
        await pilot.pause(0.3)

        assert app.state.session_id == "s1"
        assert any(block.body == "hello" for block in app.query(UserBlock))
        assert any(block.markdown == "Hi." for block in app.query(AssistantBlock))
        assert not any("function_call_output" in block.body for block in app.query(InfoBlock))
        tool_blocks = list(app.query(ToolBlock))
        assert any(block.title == "Write ok - selection_sort.py" for block in tool_blocks)
        assert any("Command: python selection_sort.py" in block.body for block in tool_blocks)
        assert app.query_one(DiffBlock).body.startswith("selection_sort.py")
        app.exit()


@pytest.mark.asyncio
async def test_tui_sessions_command_opens_session_picker(tmp_path) -> None:
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
    await session.add_items([{"role": "user", "content": "hello"}])
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/sessions"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert isinstance(app.screen, ChoiceScreen)
        assert app.screen.title_text == "Sessions"
        app.exit()


@pytest.mark.asyncio
async def test_tui_question_answer_continues_same_session(tmp_path) -> None:
    calls: list[tuple[str, str | None]] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        calls.append((prompt, kwargs.get("session_id")))
        if len(calls) == 1:
            return RunSummary(
                output="",
                session_id="s1",
                complete=False,
                status="waiting_for_user",
                pending_questions=[
                    {
                        "question": "Which package manager?",
                        "options": [{"label": "uv"}, {"label": "pip"}],
                    }
                ],
            )
        return RunSummary(output="continued", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "ask"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert app.query_one(QuestionBlock).body == "Which package manager?"
        await pilot.press("enter")
        await pilot.pause(0.3)

        assert calls[0] == ("ask", None)
        assert calls[1][1] == "s1"
        assert '"Which package manager?"="uv"' in calls[1][0]
        app.exit()


@pytest.mark.asyncio
async def test_tui_ask_user_question_tool_block_does_not_duplicate_question(tmp_path) -> None:
    tool_args = json.dumps(
        {
            "questions": [
                {
                    "question": "Which package manager?",
                    "options": [{"label": "uv"}, {"label": "pip"}],
                }
            ]
        }
    )
    tool_output = json.dumps(
        {
            "ok": True,
            "name": "AskUserQuestion",
            "output": (
                "Waiting for user input.\n"
                "1. Which package manager?\n"
                "   Mode: single-select\n"
                "   - uv\n"
                "   - pip"
            ),
            "error": None,
            "metadata": {
                "kind": "ask_user_question",
                "questions": [
                    {
                        "question": "Which package manager?",
                        "options": [{"label": "uv"}, {"label": "pip"}],
                    }
                ],
            },
            "awaitUserResponse": True,
        }
    )

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        emit_event = kwargs["emit_event"]
        emit_event(
            DeepyStreamEvent(
                kind="tool_call",
                name="AskUserQuestion",
                payload={"call_id": "ask-1", "arguments": tool_args},
            )
        )
        emit_event(
            DeepyStreamEvent(
                kind="tool_output",
                text=tool_output,
                payload={"call_id": "ask-1"},
            )
        )
        return RunSummary(
            output="",
            session_id="s1",
            complete=False,
            status="waiting_for_user",
            pending_questions=[
                {
                    "question": "Which package manager?",
                    "options": [{"label": "uv"}, {"label": "pip"}],
                }
            ],
        )

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "ask"
        await pilot.press("enter")
        await pilot.pause(0.2)

        tool_block = app.query_one(ToolBlock)
        assert tool_block.title == "AskUserQuestion ok"
        assert tool_block.body == "Waiting for user input."
        assert "Parameters" not in tool_block.body
        assert "Which package manager?" not in tool_block.body
        assert app.query_one(QuestionBlock).body == "Which package manager?"
        app.exit()


@pytest.mark.asyncio
async def test_tui_question_multiselect_custom_and_cancel_paths(tmp_path) -> None:
    prompts: list[str] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        prompts.append(prompt)
        return RunSummary(
            output="",
            session_id="s1",
            complete=False,
            status="waiting_for_user",
            pending_questions=[
                {
                    "question": "Select work",
                    "multiSelect": True,
                    "options": [{"label": "tests"}, {"label": "docs"}],
                }
            ],
        )

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "ask"
        await pilot.press("enter")
        await pilot.pause(0.2)

        block = app.query_one(QuestionBlock)
        block.selected_values = frozenset({"tests", "__other__"})
        custom = block.query_one("#question-custom", TextArea)
        custom.text = "lint"
        block.action_submit()
        await pilot.pause(0.2)

        assert '"Select work"="tests, lint"' in prompts[-1]
        app.exit()

    declined: list[str] = []

    async def cancel_run_once(prompt: str, **kwargs) -> RunSummary:
        declined.append(prompt)
        return RunSummary(
            output="",
            session_id="s1",
            complete=False,
            status="waiting_for_user",
            pending_questions=[
                {"question": "Proceed?", "options": [{"label": "Yes"}]},
            ],
        )

    cancel_app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=cancel_run_once)
    async with cancel_app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = cancel_app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "ask"
        await pilot.press("enter")
        await pilot.pause(0.2)
        cancel_app.query_one(QuestionBlock).action_cancel()
        await pilot.pause(0.1)

        assert any("declined to answer" in block.body for block in cancel_app.query(UserBlock))
        cancel_app.exit()


@pytest.mark.asyncio
async def test_tui_question_custom_text_area_submits_with_enter(tmp_path) -> None:
    prompts: list[str] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        prompts.append(prompt)
        if len(prompts) == 1:
            return RunSummary(
                output="",
                session_id="s1",
                complete=False,
                status="waiting_for_user",
                pending_questions=[
                    {
                        "question": "Python goal?",
                        "options": [{"label": "Web"}, {"label": "Data"}],
                    }
                ],
            )
        return RunSummary(output="continued", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "ask"
        await pilot.press("enter")
        await pilot.pause(0.2)

        block = app.query_one(QuestionBlock)
        options = block.query_one("#question-options", OptionList)
        options.highlighted = 2
        await pilot.press("enter")
        await pilot.pause(0.1)

        custom_option_text = _option_prompt_text(options.get_option_at_index(2))
        assert custom_option_text.startswith("[x]")
        assert "Custom answer" in custom_option_text
        custom = block.query_one("#question-custom", TextArea)
        assert custom.display
        assert custom.has_focus

        custom.text = "AI"
        await pilot.press("enter")
        await pilot.pause(0.3)

        assert '"Python goal?"="AI"' in prompts[-1]
        app.exit()


@pytest.mark.asyncio
async def test_tui_question_single_select_toggle_updates_selected_marker(tmp_path) -> None:
    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        return RunSummary(
            output="",
            session_id="s1",
            complete=False,
            status="waiting_for_user",
            pending_questions=[
                {
                    "question": "Python goal?",
                    "options": [{"label": "Web"}, {"label": "Data"}],
                }
            ],
        )

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "ask"
        await pilot.press("enter")
        await pilot.pause(0.2)

        block = app.query_one(QuestionBlock)
        options = block.query_one("#question-options", OptionList)
        options.highlighted = 1
        block.action_toggle_selected()

        assert block.selected_values == frozenset({"Data"})
        assert "[x] Data" in _option_prompt_text(options.get_option_at_index(1))
        app.exit()


@pytest.mark.asyncio
async def test_tui_question_single_select_marker_follows_highlight(tmp_path) -> None:
    calls: list[str] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        calls.append(prompt)
        if len(calls) == 1:
            return RunSummary(
                output="",
                session_id="s1",
                complete=False,
                status="waiting_for_user",
                pending_questions=[
                    {
                        "question": "Python goal?",
                        "options": [{"label": "Web"}, {"label": "Data"}],
                    }
                ],
            )
        return RunSummary(output="continued", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "ask"
        await pilot.press("enter")
        await pilot.pause(0.2)

        options = app.query_one("#question-options", OptionList)
        options.focus()
        await pilot.pause()
        assert options.has_focus
        assert "[x] Web" in _option_prompt_text(options.get_option_at_index(0))
        assert "[ ] Data" in _option_prompt_text(options.get_option_at_index(1))

        await pilot.press("down")
        await pilot.pause(0.1)
        assert "[ ] Web" in _option_prompt_text(options.get_option_at_index(0))
        assert "[x] Data" in _option_prompt_text(options.get_option_at_index(1))

        await pilot.press("enter")
        await pilot.pause(0.3)
        assert '"Python goal?"="Data"' in calls[-1]
        app.exit()


@pytest.mark.asyncio
async def test_tui_tool_block_expands_hidden_details(tmp_path) -> None:
    long_output = "\n".join(f"line {index}" for index in range(30))
    tool_output = json.dumps(
        {
            "ok": True,
            "name": "read",
            "output": long_output,
            "error": None,
            "metadata": {"path": "src/app.py"},
            "awaitUserResponse": False,
        }
    )

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        kwargs["emit_event"](
            DeepyStreamEvent(
                kind="tool_output",
                text=tool_output,
                payload={"call_id": "read-1"},
            )
        )
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "read"
        await pilot.press("enter")
        await pilot.pause(0.2)

        block = app.query_one(ToolBlock)
        assert block.details.startswith("line 0")
        assert "line 29" in block.details
        block.action_toggle_expand()
        await pilot.pause()
        assert block.query_one(".tool-details").display is True
        app.exit()


@pytest.mark.asyncio
async def test_tui_tool_surfaces_show_metadata_and_side_projection(tmp_path) -> None:
    shell_output = json.dumps(
        {
            "ok": False,
            "name": "shell",
            "output": "boom",
            "error": "Command exited with code 2.",
            "metadata": {
                "command": "false",
                "cwd": str(tmp_path),
                "exitCode": 2,
                "durationMs": 15,
                "shellPath": "/bin/zsh",
                "commandDialect": "posix",
                "outputTruncated": True,
            },
            "awaitUserResponse": False,
        }
    )
    todo_output = json.dumps(
        {
            "ok": True,
            "name": "todo_write",
            "output": "Updated todos",
            "error": None,
            "metadata": {
                "kind": "todo_list",
                "todos": [
                    {"id": "t1", "content": "Implement shell block", "status": "completed"},
                    {"id": "t2", "content": "Verify side panel", "status": "in_progress"},
                    {"id": "t3", "content": "Ship todo progress UI", "status": "pending"},
                ],
            },
            "awaitUserResponse": False,
        }
    )
    mcp_output = json.dumps(
        {
            "ok": False,
            "name": "external_tool",
            "output": "",
            "error": "server unavailable",
            "metadata": {"kind": "mcp_tool", "server": "memory", "tool": "search", "state": "unavailable"},
            "awaitUserResponse": False,
        }
    )

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        kwargs["emit_event"](DeepyStreamEvent(kind="tool_output", text=shell_output, payload={"call_id": "s"}))
        kwargs["emit_event"](DeepyStreamEvent(kind="tool_output", text=todo_output, payload={"call_id": "t"}))
        kwargs["emit_event"](DeepyStreamEvent(kind="tool_output", text=mcp_output, payload={"call_id": "m"}))
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "tools"
        await pilot.press("enter")
        await pilot.pause(0.2)

        shell_block, todo_block, mcp_block = list(app.query(ToolBlock))
        assert "Exit code: 2" in shell_block.body
        assert "Duration: 15 ms" in shell_block.body
        assert "Shell: /bin/zsh" in shell_block.body
        assert "Truncated: true" in shell_block.body
        assert "Progress  [######------------]  1/3 completed (33%)" in todo_block.body
        assert "Status    1 done | 1 active | 1 pending" in todo_block.body
        assert "Current   " in todo_block.body
        assert "[>] " in todo_block.body
        assert "Verify side panel" in todo_block.body
        assert "Parameters" not in todo_block.body
        assert "Server: memory" in mcp_block.body
        assert "Tool: search" in mcp_block.body
        assert "State: unavailable" in mcp_block.body
        assert "Todos:" in app.query_one("#side-status").content
        app.exit()


@pytest.mark.asyncio
async def test_tui_prompt_history_navigation(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "first"
        await pilot.press("enter")
        await pilot.pause(0.2)
        prompt.text = "second"
        await pilot.press("enter")
        await pilot.pause(0.2)
        prompt.text = ""
        await pilot.press("ctrl+up")
        assert prompt.text == "second"
        await pilot.press("ctrl+up")
        assert prompt.text == "first"
        await pilot.press("ctrl+down")
        assert prompt.text == "second"
        await pilot.press("ctrl+down")
        assert prompt.text == ""
        await pilot.press("up")
        assert prompt.text == "second"
        await pilot.press("up")
        assert prompt.text == "first"
        await pilot.press("down")
        assert prompt.text == "second"
        app.exit()


@pytest.mark.asyncio
async def test_tui_prompt_arrow_keys_still_move_inside_multiline_input(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "first\nsecond"
        prompt.move_cursor((1, 0))

        await pilot.press("up")
        assert prompt.cursor_location == (0, 0)

        await pilot.press("down")
        assert prompt.cursor_location == (1, 0)
        app.exit()
