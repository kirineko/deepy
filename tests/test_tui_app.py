from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from textual.command import CommandPalette
from textual.widgets import Label, OptionList, TextArea
from textual.widgets.option_list import Option

import deepy.tui.app as tui_app
import deepy.tui.runner as tui_runner
from deepy.config import ModelConfig, Settings
from deepy.config import load_settings
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary
from deepy.skill_market import InstalledSkill, MarketSkill
from deepy.skills import SkillInfo
from deepy.status import BalanceInfo, BalanceStatus
from deepy.tui.app import DeepyTuiApp
from deepy.tui.commands import DeepyCommandProvider
from deepy.tui.screens import ChoiceScreen, InfoScreen, ResetConfigScreen, SkillManagementScreen
from deepy.tui.state import set_session_id
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
    decode_kitty_text_sequences,
)
from deepy.sessions import DeepyJsonlSession
from deepy.ui.local_command import LocalCommandResult
from deepy.usage import TokenUsage


async def _idle_run_once(prompt: str, **kwargs) -> RunSummary:
    return RunSummary(output=f"answer: {prompt}", session_id="s1", complete=True)


def _option_prompt_text(option: Option) -> str:
    prompt = option.prompt
    return getattr(prompt, "plain", str(prompt))


async def _wait_for(pilot, condition: Callable[[], object], *, timeout: float = 1.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    last_error: Exception | None = None
    while True:
        try:
            if condition():
                return
        except Exception as exc:
            last_error = exc
        if loop.time() >= deadline:
            raise AssertionError("Timed out waiting for TUI test condition") from last_error
        await pilot.pause(0.01)


async def _submit_prompt(app: DeepyTuiApp, pilot, text: str, condition: Callable[[], object]) -> None:
    prompt = app.query_one("#prompt-input", PromptTextArea)
    prompt.text = text
    prompt.action_submit()
    await _wait_for(pilot, condition)


def test_decode_kitty_text_sequences_decodes_chinese_text_event() -> None:
    assert decode_kitty_text_sequences("[32;;20320;22909u") == "你好"
    assert decode_kitty_text_sequences("[32;;20320:22909u") == "你好"
    assert decode_kitty_text_sequences("[0;1;20320:22909u") == "你好"
    assert decode_kitty_text_sequences("\x1b[32;;20320;22909u") == "你好"
    assert decode_kitty_text_sequences("ask [32;;20320;22909u") == "ask 你好"
    assert decode_kitty_text_sequences("[32;;104:101:108:108:111u") == "hello"
    assert decode_kitty_text_sequences("say [32;;104:101:108:108:111u") == "say hello"


def test_decode_kitty_text_sequences_leaves_non_text_sequences_unchanged() -> None:
    assert decode_kitty_text_sequences("\x1b[20320u") == "\x1b[20320u"
    assert decode_kitty_text_sequences("[32;;not-a-codepointu") == "[32;;not-a-codepointu"
    assert decode_kitty_text_sequences("[32;;7u") == "[32;;7u"


@pytest.mark.asyncio
async def test_tui_starts_and_exits_headless(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        assert app.query_one("#prompt-input", PromptTextArea).has_focus
        startup_text = app.query_one(InfoBlock).body
        assert startup_text.startswith("Experimental Textual TUI.")
        assert "Ctrl+J for newline" in startup_text
        assert "Shift+Enter" not in startup_text
        assert app.query(InfoBlock).first() is not None
        await pilot.press("ctrl+o")
        assert app.query_one("#side-panel").has_class("-visible")
        app.exit()


@pytest.mark.asyncio
async def test_tui_prompt_decodes_kitty_text_sequence(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "[32;;20320:22909u"
        await _wait_for(pilot, lambda: prompt.text == "你好")
        assert prompt.cursor_location == (0, 2)
        app.exit()


def test_tui_help_markdown_advertises_ctrl_j_newline(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    help_markdown = app._help_markdown()

    assert "- **Ctrl+J** - insert newline" in help_markdown
    assert "**/ps**" in help_markdown
    assert "**/stop**" in help_markdown
    assert "Shift+Enter" not in help_markdown


@pytest.mark.asyncio
async def test_tui_exit_slash_command_exits_without_model_turn(tmp_path, monkeypatch) -> None:
    calls: list[str] = []
    exited: list[bool] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        calls.append(prompt)
        return RunSummary(output="unexpected", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)
    app.background_tasks.start(
        command="sleep",
        argv=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
    )
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: exited.append(True))

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/exit"
        await pilot.press("enter")
        await pilot.pause(0.1)

        assert exited == [True]
        assert calls == []
        assert app.exit_summary_text is not None
        assert "Deepy Session Summary" in app.exit_summary_text
        assert app.background_tasks.running_count() == 0


@pytest.mark.asyncio
async def test_tui_ctrl_d_confirm_exits_with_summary(tmp_path, monkeypatch) -> None:
    exited: list[bool] = []
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: exited.append(True))

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        await pilot.press("ctrl+d")
        await pilot.press("ctrl+d")
        await pilot.pause(0.1)

        assert exited == [True]
        assert app.exit_summary_text is not None
        assert "Deepy Session Summary" in app.exit_summary_text


@pytest.mark.asyncio
async def test_tui_exit_summary_counts_session_messages(tmp_path) -> None:
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
    await session.add_items(
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "assistant", "content": "done"},
        ]
    )
    session.record_usage({"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12})
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)
    app.state = set_session_id(app.state, "s1")

    summary = app._build_exit_summary_text()

    assert "messages" in summary
    assert "3 total" in summary
    assert "2 assistant" in summary
    assert "requests 2" in summary


@pytest.mark.asyncio
async def test_tui_exit_summary_includes_session_cost(tmp_path, monkeypatch) -> None:
    balances = iter(
        [
            BalanceStatus(
                is_available=True,
                balance_infos=(
                    BalanceInfo("CNY", "100.00", "0.00", "100.00"),
                ),
            ),
            BalanceStatus(
                is_available=True,
                balance_infos=(
                    BalanceInfo("CNY", "99.75", "0.00", "99.75"),
                ),
            ),
        ]
    )

    monkeypatch.setattr(tui_app, "fetch_deepseek_balance", lambda settings: next(balances))
    app = DeepyTuiApp(
        settings=Settings(model=ModelConfig(api_key="sk-test")),
        project_root=tmp_path,
        run_once=_idle_run_once,
    )
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: None)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "hello"
        await pilot.press("enter")
        await pilot.pause(0.2)

        app._exit_with_summary()

        assert app.exit_summary_text is not None
        assert "session cost" in app.exit_summary_text
        assert "CNY 0.25" in app.exit_summary_text


@pytest.mark.asyncio
async def test_tui_exit_summary_shows_unavailable_session_cost(tmp_path, monkeypatch) -> None:
    balances = iter(
        [
            BalanceStatus(
                is_available=True,
                balance_infos=(
                    BalanceInfo("CNY", "100.00", "0.00", "100.00"),
                ),
            ),
            BalanceStatus(unavailable_reason="timeout"),
        ]
    )

    monkeypatch.setattr(tui_app, "fetch_deepseek_balance", lambda settings: next(balances))
    app = DeepyTuiApp(
        settings=Settings(model=ModelConfig(api_key="sk-test")),
        project_root=tmp_path,
        run_once=_idle_run_once,
    )
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: None)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "hello"
        await pilot.press("enter")
        await pilot.pause(0.2)

        app._exit_with_summary()

        assert app.exit_summary_text is not None
        assert "session cost" in app.exit_summary_text
        assert "unavailable (end timeout)" in app.exit_summary_text


@pytest.mark.asyncio
async def test_tui_exit_summary_marks_third_party_cost_unsupported(tmp_path, monkeypatch) -> None:
    def fail_fetch(settings):
        raise AssertionError("balance lookup should not run")

    monkeypatch.setattr(tui_app, "fetch_deepseek_balance", fail_fetch)
    app = DeepyTuiApp(
        settings=Settings(
            model=ModelConfig(
                provider="xiaomi",
                name="mimo-v2.5-pro",
                base_url="https://api.xiaomimimo.com/v1",
                api_key="sk-test",
            )
        ),
        project_root=tmp_path,
        run_once=_idle_run_once,
    )
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: None)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)

        app._exit_with_summary()

        assert app.exit_summary_text is not None
        assert "session cost" in app.exit_summary_text
        assert "unsupported" in app.exit_summary_text


def test_tui_runner_prints_exit_summary_after_app_closes(tmp_path, monkeypatch, capsys) -> None:
    class FakeApp:
        exit_summary_text = "Deepy Session Summary\nmodel deepseek-v4-pro"

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def run(self):
            return None

    monkeypatch.setattr(tui_app, "DeepyTuiApp", FakeApp)

    code = tui_runner.run_tui(Settings(), project_root=tmp_path)

    assert code == 0
    assert "Deepy Session Summary" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_tui_reuses_session_id_between_turns(tmp_path) -> None:
    calls: list[tuple[str, str | None, bool]] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        session_id = kwargs.get("session_id")
        calls.append((prompt, session_id, kwargs.get("background_tasks") is app.background_tasks))
        return RunSummary(output=f"answer: {prompt}", session_id=session_id or "s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "first"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert app.state.session_id == "s1"

        prompt.text = "second"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert calls == [("first", None, True), ("second", "s1", True)]
        app.exit()


@pytest.mark.asyncio
async def test_tui_prompt_newline_slash_and_file_suggestions(tmp_path) -> None:
    tmp_path.joinpath("src").mkdir()
    tmp_path.joinpath("src", "app.py").write_text("print('hi')\n", encoding="utf-8")
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        panel = app.query_one(PromptPanel)

        prompt.text = "hello"
        prompt.move_cursor((0, len(prompt.text)))
        await pilot.press("ctrl+j")
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
async def test_tui_input_suggestion_ghost_text_accepts_tab_and_right_without_overlap(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        panel = app.query_one(PromptPanel)
        ghost = app.query_one("#prompt-ghost", Label)
        options = app.query_one("#prompt-suggestions", OptionList)

        panel.set_input_suggestion("run tests")
        await pilot.pause(0.01)

        assert ghost.display is True
        assert str(ghost.content) == "run tests"

        await pilot.press("tab")
        await pilot.pause(0.01)

        assert prompt.text == "run tests"
        assert ghost.display is False

        prompt.clear()
        await pilot.pause(0.01)

        assert ghost.display is True
        assert str(ghost.content) == "run tests"

        prompt.clear()
        panel.set_input_suggestion("commit changes")
        prompt.text = "/"
        await pilot.pause(0.01)

        assert options.display is True
        assert ghost.display is False

        prompt.clear()
        panel.set_input_suggestion("commit changes")
        await pilot.pause(0.01)
        prompt.action_cursor_right()
        await pilot.pause(0.01)

        assert prompt.text == "commit changes"
        app.exit()


@pytest.mark.asyncio
async def test_tui_input_suggestion_returns_after_type_delete_cycle(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        panel = app.query_one(PromptPanel)
        ghost = app.query_one("#prompt-ghost", Label)
        options = app.query_one("#prompt-suggestions", OptionList)

        panel.set_input_suggestion("run tests")
        prompt.text = "typed"
        await pilot.pause(0.01)

        assert ghost.display is False
        assert panel.input_suggestion == "run tests"

        prompt.clear()
        await pilot.pause(0.01)

        assert ghost.display is True
        assert str(ghost.content) == "run tests"
        assert options.display is False

        await pilot.press("tab")
        await pilot.pause(0.01)

        assert prompt.text == "run tests"
        app.exit()


@pytest.mark.asyncio
async def test_tui_enter_does_not_accept_input_suggestion(tmp_path) -> None:
    calls: list[str] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        calls.append(prompt)
        return RunSummary(output="unexpected", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        panel = app.query_one(PromptPanel)
        ghost = app.query_one("#prompt-ghost", Label)

        panel.set_input_suggestion("run tests")
        await pilot.pause(0.01)
        await pilot.press("enter")
        await pilot.pause(0.01)

        assert prompt.text == ""
        assert ghost.display is True
        assert calls == []
        app.exit()


@pytest.mark.asyncio
async def test_tui_file_suggestions_support_tab_acceptance_and_keyboard_selection(tmp_path) -> None:
    tmp_path.joinpath("aaa.py").write_text("", encoding="utf-8")
    tmp_path.joinpath("bbb.py").write_text("", encoding="utf-8")
    tmp_path.joinpath("ui").mkdir()
    tmp_path.joinpath("ui", "panel.py").write_text("", encoding="utf-8")
    tmp_path.joinpath("ui", "nested").mkdir()
    tmp_path.joinpath("ui", "nested", "view.py").write_text("", encoding="utf-8")
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        panel = app.query_one(PromptPanel)
        options = app.query_one("#prompt-suggestions", OptionList)

        prompt.text = "@"
        await pilot.pause(0.01)
        assert options.display is True
        assert options.highlighted == 0

        await pilot.press("down")
        assert options.highlighted == 1

        await pilot.press("tab")
        assert prompt.text == "@bbb.py "
        assert options.display is False

        prompt.text = "@"
        await pilot.pause(0.01)
        await pilot.press("down")
        await pilot.press("down")
        assert options.highlighted == 2

        await pilot.press("enter")
        assert prompt.text == "@ui/"
        assert "@ui/nested/" in panel.suggestions
        assert "@ui/panel.py" in panel.suggestions

        prompt.text = "@"
        await pilot.pause(0.01)
        assert options.highlighted == 0
        await pilot.press("down")
        await pilot.press("down")
        assert options.highlighted == 2
        await pilot.press("enter")
        assert prompt.text == "@ui/"
        app.exit()


@pytest.mark.asyncio
async def test_tui_slash_suggestions_tab_cycles_and_enter_confirms(tmp_path) -> None:
    calls: list[str] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        calls.append(prompt)
        return RunSummary(output="unexpected", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        options = app.query_one("#prompt-suggestions", OptionList)

        prompt.text = "/re"
        await pilot.pause(0.01)
        assert options.display is True
        assert options.highlighted == 0

        await pilot.press("down")
        assert options.highlighted == 1

        await pilot.press("tab")
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
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/skills use demo"
        await pilot.press("enter")
        await pilot.pause(0.1)

        assert not calls
        transcript_text = "\n".join(block.body for block in app.query(InfoBlock))
        assert "Loaded skill: demo" in transcript_text
        assert "VERY LONG SKILL BODY" not in transcript_text

        prompt.text = "use it"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert calls == [("use it", ["demo"])]
        app.exit()


@pytest.mark.asyncio
async def test_tui_init_command_routes_generated_prompt_without_unsupported_message(tmp_path) -> None:
    calls: list[tuple[str, str | None]] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        calls.append((prompt, kwargs.get("session_id")))
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/init prefer concise guidance"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert len(calls) == 1
        assert "Analyze this repository and create the project root AGENTS.md file." in calls[0][0]
        assert "Additional user instruction:\nprefer concise guidance" in calls[0][0]
        assert not any("not supported" in block.body for block in app.query(ErrorBlock))
        app.exit()


@pytest.mark.asyncio
async def test_tui_reset_form_writes_config_and_reloads_settings(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    settings = Settings(path=config_path)
    app = DeepyTuiApp(settings=settings, project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/reset"
        await pilot.press("enter")
        await pilot.pause(0.1)

        assert isinstance(app.screen, ResetConfigScreen)
        app.screen.query_one("#reset-api-key").value = "sk-test"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-model").value = "deepseek-v4-flash"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-base-url").value = "https://example.test"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-theme").value = "light"  # type: ignore[attr-defined]
        await pilot.press("ctrl+s")
        await pilot.pause(0.2)

        saved = load_settings(config_path)
        assert saved.model.api_key == "sk-test"
        assert saved.model.provider == "deepseek"
        assert saved.model.name == "deepseek-v4-flash"
        assert saved.model.base_url == "https://example.test"
        assert saved.model.reasoning_mode == "max"
        assert saved.ui.theme == "light"
        assert app.settings.ui.theme == "light"
        assert any("Wrote" in block.body for block in app.query(InfoBlock))
        app.exit()


@pytest.mark.asyncio
async def test_tui_reset_form_writes_third_party_provider_settings(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    app = DeepyTuiApp(settings=Settings(path=config_path), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/reset"
        await pilot.press("enter")
        await pilot.pause(0.1)

        assert isinstance(app.screen, ResetConfigScreen)
        app.screen.query_one("#reset-api-key").value = "sk-test"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-provider").value = "xiaomi"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-model").value = "mimo-v2.5"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-base-url").value = "https://api.xiaomimimo.com/v1"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-thinking").value = "disabled"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-theme").value = "light"  # type: ignore[attr-defined]
        await pilot.press("ctrl+s")
        await pilot.pause(0.2)

        saved = load_settings(config_path)
        assert saved.model.provider == "xiaomi"
        assert saved.model.name == "mimo-v2.5"
        assert saved.model.reasoning_mode == "disabled"
        assert saved.model.reasoning_effort == "none"
        app.exit()


@pytest.mark.asyncio
async def test_tui_reset_form_accepts_openrouter_custom_model_and_effort(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    app = DeepyTuiApp(settings=Settings(path=config_path), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/reset"
        await pilot.press("enter")
        await pilot.pause(0.1)

        assert isinstance(app.screen, ResetConfigScreen)
        app.screen.query_one("#reset-api-key").value = "sk-test"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-provider").value = "openrouter"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-model").value = "anthropic/claude-sonnet-4.5"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-thinking").value = "minimal"  # type: ignore[attr-defined]
        app.screen.query_one("#reset-theme").value = "light"  # type: ignore[attr-defined]
        await pilot.press("ctrl+s")
        await pilot.pause(0.2)

        saved = load_settings(config_path)
        assert saved.model.provider == "openrouter"
        assert saved.model.name == "anthropic/claude-sonnet-4.5"
        assert saved.model.reasoning_mode == "minimal"
        assert saved.model.reasoning_effort == "minimal"
        app.exit()


@pytest.mark.asyncio
async def test_tui_reset_form_cancellation_preserves_config(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[model]\nname = \"deepseek-v4-pro\"\n", encoding="utf-8")
    settings = load_settings(config_path)
    app = DeepyTuiApp(settings=settings, project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/reset"
        await pilot.press("enter")
        await pilot.pause(0.1)
        await pilot.press("escape")
        await pilot.pause(0.1)

        assert config_path.read_text(encoding="utf-8") == "[model]\nname = \"deepseek-v4-pro\"\n"
        assert app.settings.model.name == "deepseek-v4-pro"
        app.exit()


@pytest.mark.asyncio
async def test_tui_input_suggestion_command_toggles_config(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[ui]\ninput_suggestions_enabled = true\n", encoding="utf-8")
    app = DeepyTuiApp(settings=load_settings(config_path), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)

        prompt.text = "/input-suggestion"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert load_settings(config_path).ui.input_suggestions_enabled is False
        assert app.input_suggestions.enabled is False
        assert any("Input suggestions disabled." in block.body for block in app.query(InfoBlock))

        prompt.text = "/input-suggestion extra"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert load_settings(config_path).ui.input_suggestions_enabled is False
        assert any("Usage: /input-suggestion" in block.body for block in app.query(ErrorBlock))
        app.exit()


def _local_command_result(
    command: str,
    *,
    output: str = "ok\n",
    exit_code: int = 0,
    shell_kind: str = "zsh",
    command_dialect: str = "posix",
    os_family: str = "posix",
    tty_mode: str = "pty",
) -> LocalCommandResult:
    return LocalCommandResult(
        command=command,
        output=output,
        display_output=output,
        context_output=output,
        exit_code=exit_code,
        cwd=Path("/tmp"),
        shell_path="powershell.exe" if shell_kind == "powershell" else "cmd.exe" if shell_kind == "cmd" else "/bin/zsh",
        shell_kind=shell_kind,
        command_dialect=command_dialect,
        path_style="windows" if os_family == "windows" else "posix",
        os_family=os_family,
        tty_mode=tty_mode,
        duration_ms=12,
        timeout_ms=120000,
    )


@pytest.mark.asyncio
async def test_tui_local_command_runs_renders_and_persists_without_model_turn(tmp_path, monkeypatch) -> None:
    model_calls: list[str] = []
    local_calls: list[str] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        model_calls.append(prompt)
        return RunSummary(output="unexpected", session_id="s1", complete=True)

    def fake_run_local_command(command: str, **kwargs) -> LocalCommandResult:
        local_calls.append(command)
        return _local_command_result(command, output="hello\n")

    monkeypatch.setattr("deepy.tui.app.run_local_command", fake_run_local_command)
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "!echo hello"
        await pilot.press("enter")
        await pilot.pause(0.3)

        assert local_calls == ["echo hello"]
        assert model_calls == []
        assert app.state.session_id is not None
        assert any("hello" in block.body for block in app.query(ToolBlock))
        session = DeepyJsonlSession.open(tmp_path, app.state.session_id)
        items = await session.get_items()
        assert items[0]["role"] == "user"
        assert items[0]["content"] == "!echo hello"
        assert items[1]["name"] == "shell"
        app.exit()


@pytest.mark.asyncio
async def test_tui_local_command_appends_separate_shell_blocks_for_later_commands(tmp_path, monkeypatch) -> None:
    local_calls: list[str] = []

    def fake_run_local_command(command: str, **kwargs) -> LocalCommandResult:
        local_calls.append(command)
        return _local_command_result(command, output=f"{command}\n")

    monkeypatch.setattr("deepy.tui.app.run_local_command", fake_run_local_command)
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "!pwd"
        await pilot.press("enter")
        await pilot.pause(0.3)

        prompt.text = "!ls"
        await pilot.press("enter")
        await pilot.pause(0.3)

        blocks = list(app.query(ToolBlock))
        assert local_calls == ["pwd", "ls"]
        assert len(blocks) == 2
        assert "pwd" in blocks[0].body
        assert "ls" in blocks[1].body
        app.exit()


@pytest.mark.asyncio
async def test_tui_empty_local_command_shows_usage_without_session_or_model(tmp_path) -> None:
    calls: list[str] = []

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        calls.append(prompt)
        return RunSummary(output="unexpected", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "!"
        await pilot.press("enter")
        await pilot.pause(0.1)

        assert calls == []
        assert app.state.session_id is None
        assert any("Usage: !<command>" in block.body for block in app.query(ErrorBlock))
        app.exit()


@pytest.mark.asyncio
async def test_tui_local_command_renders_windows_powershell_pipe_metadata(tmp_path, monkeypatch) -> None:
    def fake_run_local_command(command: str, **kwargs) -> LocalCommandResult:
        return _local_command_result(
            command,
            output="中文\n",
            shell_kind="powershell",
            command_dialect="powershell",
            os_family="windows",
            tty_mode="pipe",
        )

    monkeypatch.setattr("deepy.tui.app.run_local_command", fake_run_local_command)
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "!Write-Output 中文"
        await pilot.press("enter")
        await pilot.pause(0.3)

        block = app.query_one(ToolBlock)
        assert "中文" in block.body
        assert "Power" in block.body or "powershell" in block.body
        app.exit()


@pytest.mark.asyncio
async def test_tui_local_command_accepts_windows_cmd_pipe_metadata(tmp_path, monkeypatch) -> None:
    def fake_run_local_command(command: str, **kwargs) -> LocalCommandResult:
        return _local_command_result(
            command,
            output="ok\n",
            shell_kind="cmd",
            command_dialect="cmd",
            os_family="windows",
            tty_mode="pipe",
        )

    monkeypatch.setattr("deepy.tui.app.run_local_command", fake_run_local_command)
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "!echo ok"
        await pilot.press("enter")
        await pilot.pause(0.3)

        block = app.query_one(ToolBlock)
        assert "ok" in block.body
        assert app.state.session_id is not None
        app.exit()


def _installed_record(name: str, path: Path) -> InstalledSkill:
    return InstalledSkill(
        name=name,
        scope="user",
        install_path=path,
        market_url="https://market.test",
        version_id="v1",
        version="1.0.0",
        sha256="sha",
        content_hash="hash",
        installed_at="2026-05-19T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_tui_skill_market_subcommands(tmp_path, monkeypatch) -> None:
    installed = _installed_record("demo", tmp_path / ".agents" / "skills" / "demo")
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "deepy.tui.app.search_market_skills",
        lambda query: [MarketSkill(name="demo", description=f"result {query}", version="1.0.0")],
    )
    monkeypatch.setattr(
        "deepy.tui.app.install_market_skill",
        lambda name, **kwargs: calls.append(("install", kwargs["scope"])) or installed,
    )
    monkeypatch.setattr(
        "deepy.tui.app.uninstall_market_skill",
        lambda name: calls.append(("uninstall", name)) or name,
    )
    monkeypatch.setattr("deepy.tui.app.list_installed_skills", lambda: [installed])
    monkeypatch.setattr(
        "deepy.tui.app.update_market_skill",
        lambda name: calls.append(("update", name)) or ("updated", installed),
    )
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await _wait_for(pilot, lambda: app.query_one("#prompt-input", PromptTextArea).has_focus)

        await _submit_prompt(
            app,
            pilot,
            "/skills search pdf",
            lambda: any("demo" in block.body and "result pdf" in block.body for block in app.query(InfoBlock)),
        )
        assert any("demo" in block.body and "result pdf" in block.body for block in app.query(InfoBlock))

        await _submit_prompt(app, pilot, "/skills install demo", lambda: isinstance(app.screen, ChoiceScreen))
        assert isinstance(app.screen, ChoiceScreen)
        app.screen.dismiss("user")
        await _wait_for(pilot, lambda: ("install", "user") in calls)
        assert ("install", "user") in calls

        await _submit_prompt(
            app,
            pilot,
            "/skills installed",
            lambda: any("Market-installed skills" in block.body for block in app.query(InfoBlock)),
        )
        assert any("Market-installed skills" in block.body for block in app.query(InfoBlock))

        await _submit_prompt(app, pilot, "/skills update demo", lambda: ("update", "demo") in calls)
        assert ("update", "demo") in calls

        await _submit_prompt(app, pilot, "/skills uninstall demo", lambda: ("uninstall", "demo") in calls)
        assert ("uninstall", "demo") in calls
        app.exit()


@pytest.mark.asyncio
async def test_tui_skill_management_screen_installs_market_skill(tmp_path, monkeypatch) -> None:
    installed = _installed_record("market-demo", tmp_path / ".agents" / "skills" / "market-demo")
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "deepy.tui.app.search_market_skills",
        lambda query: [MarketSkill(name="market-demo", description="Market demo", version="1.0.0")],
    )
    monkeypatch.setattr(
        "deepy.tui.app.install_market_skill",
        lambda name, **kwargs: calls.append((name, kwargs["scope"])) or installed,
    )
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await _wait_for(pilot, lambda: app.query_one("#prompt-input", PromptTextArea).has_focus)
        await _submit_prompt(app, pilot, "/skills", lambda: isinstance(app.screen, SkillManagementScreen))

        assert isinstance(app.screen, SkillManagementScreen)
        assert app.screen.view == "market"
        app.screen.action_toggle_view()
        assert isinstance(app.screen, SkillManagementScreen)
        assert app.screen.view == "installed"
        app.screen.action_toggle_view()
        assert isinstance(app.screen, SkillManagementScreen)
        assert app.screen.view == "market"

        app.screen.action_primary()
        await _wait_for(pilot, lambda: isinstance(app.screen, ChoiceScreen))
        assert isinstance(app.screen, ChoiceScreen)
        app.screen.dismiss("user")
        await _wait_for(pilot, lambda: calls == [("market-demo", "user")])

        assert calls == [("market-demo", "user")]
        assert any("Installed skill: market-demo" in block.body for block in app.query(InfoBlock))
        app.exit()


@pytest.mark.asyncio
async def test_tui_skill_management_blocks_builtin_uninstall_from_command(tmp_path, monkeypatch) -> None:
    calls: list[str] = []

    def fail_uninstall(name: str) -> str:
        calls.append(name)
        raise AssertionError("builtin uninstall should not call market uninstall")

    monkeypatch.setattr("deepy.tui.app.uninstall_market_skill", fail_uninstall)
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/skills uninstall skill-creator"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert calls == []
        assert any("Built-in skill cannot be uninstalled" in block.body for block in app.query(ErrorBlock))
        app.exit()


@pytest.mark.asyncio
async def test_tui_skill_management_screen_uses_compact_market_rows(tmp_path, monkeypatch) -> None:
    long_description = " ".join(["description"] * 40)

    monkeypatch.setattr(
        "deepy.tui.app.search_market_skills",
        lambda query: [MarketSkill(name="long-demo", description=long_description, version="1.0.0")],
    )
    monkeypatch.setattr(
        "deepy.tui.app.discover_skills",
        lambda project_root: [
            SkillInfo(
                name="skill-creator",
                path=tmp_path / "builtin" / "skill-creator" / "SKILL.md",
                description="Create skills",
                scope="builtin",
            )
        ],
    )
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(120, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/skills"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert isinstance(app.screen, SkillManagementScreen)
        assert app.screen.view == "market"
        assert app.screen._title() == "Skill Market (1)"
        options = app.screen.query_one("#skill-options", OptionList)
        market_prompt = str(options.get_option_at_index(0).prompt)
        assert market_prompt.count("\n") <= 1
        assert len(market_prompt) < 160

        await pilot.press("tab")
        await pilot.pause(0.1)
        assert app.screen.view == "installed"
        assert app.screen._title() == "Installed Skills (0)"
        assert app.screen._selected_entry() is None
        app.exit()


@pytest.mark.asyncio
async def test_tui_skills_uninstall_removes_manual_project_skill(tmp_path, monkeypatch) -> None:
    calls: list[str] = []
    skill_dir = tmp_path / ".agents" / "skills" / "manual"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\ndescription: Manual skill\n---\n# Manual\n", encoding="utf-8")

    def fail_uninstall(name: str) -> str:
        calls.append(name)
        raise AssertionError("manual skill removal should not call market uninstall")

    monkeypatch.setattr("deepy.tui.app.uninstall_market_skill", fail_uninstall)
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/skills uninstall manual"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert calls == []
        assert not skill_dir.exists()
        assert any("Removed local skill: manual" in block.body for block in app.query(InfoBlock))
        app.exit()


@pytest.mark.asyncio
async def test_tui_status_bar_shows_context_and_compact_next(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    settings = Settings(path=config_path)
    entry = SimpleNamespace(
        id="s1",
        latest_context_window_tokens=900,
        usage=None,
    )
    monkeypatch.setattr("deepy.tui.app.list_session_entries", lambda project_root: [entry])
    monkeypatch.setattr(
        "deepy.tui.app.load_mcp_config",
        lambda settings, *, project_root=None: SimpleNamespace(definitions=(object(),)),
    )
    app = DeepyTuiApp(
        settings=settings.__class__(
            model=settings.model,
            context=settings.context.__class__(window_tokens=1000, compact_trigger_ratio=0.8),
            logging=settings.logging,
            notify=settings.notify,
            tools=settings.tools,
            mcp=settings.mcp,
            ui=settings.ui,
            path=settings.path,
        ),
        project_root=tmp_path,
        run_once=_idle_run_once,
    )

    async with app.run_test(size=(120, 32)) as pilot:
        await pilot.pause(0.01)
        app.background_tasks.start(
            command="worker",
            argv=[sys.executable, "-c", "import time; time.sleep(5)"],
            cwd=tmp_path,
        )
        app.state = app.state.__class__(session_id="s1")
        app._update_status("Idle")
        await pilot.pause(0.1)

        left = str(app.query_one("#status-left", Label).content)
        assert "model deepseek-v4-pro[max]" in left
        assert "cwd" in left
        assert "mcp 1" in left
        assert "bg 1" in left
        assert "ctx 900/1K" in left
        assert "compact next" in left
        app.background_tasks.stop_all(force_after_grace=True)
        app.exit()


@pytest.mark.asyncio
async def test_tui_status_bar_hides_mcp_when_no_servers(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "deepy.tui.app.load_mcp_config",
        lambda settings, *, project_root=None: SimpleNamespace(definitions=()),
    )
    app = DeepyTuiApp(settings=Settings(path=tmp_path / "config.toml"), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(120, 32)) as pilot:
        await pilot.pause(0.01)
        app._update_status("Idle")
        await pilot.pause(0.1)

        left = str(app.query_one("#status-left", Label).content)
        assert not any(segment.strip().startswith("mcp ") for segment in left.split("·"))
        app.exit()


@pytest.mark.asyncio
async def test_tui_initial_setup_guides_missing_config(tmp_path) -> None:
    settings = Settings(path=tmp_path / "config.toml")
    app = DeepyTuiApp(
        settings=settings,
        project_root=tmp_path,
        run_once=_idle_run_once,
        guide_missing_config=True,
    )

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.2)

        assert isinstance(app.screen, ResetConfigScreen)
        assert any("Deepy needs a provider API key" in block.body for block in app.query(InfoBlock))
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
        await pilot.pause(0.01)
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
            "name": "write_file",
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
                name="write_file",
                payload={"call_id": "call-1", "arguments": '{"file_path":"src/app.py"}'},
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
        await pilot.pause(0.01)
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
async def test_tui_folds_retryable_file_tool_attempt_into_later_success(tmp_path) -> None:
    retryable_output = json.dumps(
        {
            "ok": False,
            "name": "write_file",
            "output": "",
            "error": "Invalid tool arguments JSON",
            "metadata": {
                "error_code": "invalid_arguments",
                "retryable": True,
                "recovery": "Pass valid JSON.",
                "parse_error": "unexpected character",
            },
            "awaitUserResponse": False,
        }
    )
    success_output = json.dumps(
        {
            "ok": True,
            "name": "write_file",
            "output": "Wrote file",
            "error": None,
            "metadata": {"path": "src/app.py"},
            "awaitUserResponse": False,
        }
    )

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        emit_event = kwargs["emit_event"]
        emit_event(
            DeepyStreamEvent(
                kind="tool_call",
                name="write_file",
                payload={
                    "call_id": "bad-1",
                    "arguments": (
                        '{"file_path":"src/app.py","content":SECRET,'
                        '"overwrite":true,"snapshot_id":snapshot_1}'
                    ),
                },
            )
        )
        emit_event(
            DeepyStreamEvent(kind="tool_output", text=retryable_output, payload={"call_id": "bad-1"})
        )
        emit_event(
            DeepyStreamEvent(
                kind="tool_call",
                name="write_file",
                payload={
                    "call_id": "good-1",
                    "arguments": '{"file_path":"src/app.py","content":"new\\n"}',
                },
            )
        )
        emit_event(
            DeepyStreamEvent(kind="tool_output", text=success_output, payload={"call_id": "good-1"})
        )
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "write"
        await pilot.press("enter")
        await pilot.pause(0.2)

        tool_blocks = list(app.query(ToolBlock))
        assert len(tool_blocks) == 1
        block = tool_blocks[0]
        assert block.title == "Write ok - src/app.py"
        assert "Recovered after argument retry." in block.body
        assert "SECRET" not in block.body
        app.exit()


@pytest.mark.asyncio
async def test_tui_does_not_fold_blocking_file_tool_failure(tmp_path) -> None:
    blocking_output = json.dumps(
        {
            "ok": False,
            "name": "write_file",
            "output": "",
            "error": "Existing file replacement requires a snapshot_id.",
            "metadata": {"error_code": "stale_snapshot", "path": "src/app.py"},
            "awaitUserResponse": False,
        }
    )
    success_output = json.dumps(
        {
            "ok": True,
            "name": "write_file",
            "output": "Wrote file",
            "error": None,
            "metadata": {"path": "src/app.py"},
            "awaitUserResponse": False,
        }
    )

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        emit_event = kwargs["emit_event"]
        emit_event(
            DeepyStreamEvent(
                kind="tool_call",
                name="write_file",
                payload={"call_id": "bad-1", "arguments": '{"file_path":"src/app.py"}'},
            )
        )
        emit_event(
            DeepyStreamEvent(kind="tool_output", text=blocking_output, payload={"call_id": "bad-1"})
        )
        emit_event(
            DeepyStreamEvent(
                kind="tool_call",
                name="write_file",
                payload={"call_id": "good-1", "arguments": '{"file_path":"src/app.py"}'},
            )
        )
        emit_event(
            DeepyStreamEvent(kind="tool_output", text=success_output, payload={"call_id": "good-1"})
        )
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "write"
        await pilot.press("enter")
        await pilot.pause(0.2)

        tool_blocks = list(app.query(ToolBlock))
        assert len(tool_blocks) == 2
        assert tool_blocks[0].title == "Write failed - src/app.py"
        assert tool_blocks[1].title == "Write ok - src/app.py"
        app.exit()


@pytest.mark.asyncio
async def test_tui_retryable_tool_block_exposes_bounded_recovery_details(tmp_path) -> None:
    retryable_output = json.dumps(
        {
            "ok": False,
            "name": "write_file",
            "output": "",
            "error": "Invalid tool arguments JSON",
            "metadata": {
                "error_code": "invalid_arguments",
                "retryable": True,
                "recovery": "Pass valid JSON.",
                "parse_error": "\n".join(f"parse line {index}" for index in range(20)),
            },
            "awaitUserResponse": False,
        }
    )

    async def fake_run_once(prompt: str, **kwargs) -> RunSummary:
        kwargs["emit_event"](
            DeepyStreamEvent(
                kind="tool_call",
                name="write_file",
                payload={
                    "call_id": "bad-1",
                    "arguments": '{"file_path":"src/app.py","content":SECRET}',
                },
            )
        )
        kwargs["emit_event"](
            DeepyStreamEvent(kind="tool_output", text=retryable_output, payload={"call_id": "bad-1"})
        )
        return RunSummary(output="ok", session_id="s1", complete=True)

    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=fake_run_once)

    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "write"
        await pilot.press("enter")
        await pilot.pause(0.2)

        block = app.query_one(ToolBlock)
        assert block.title == "Write retryable"
        assert "src/app.py (malformed args)" in block.body
        assert "SECRET" not in block.body
        assert "Pass valid JSON." in block.details
        assert "parse line 6" in block.details
        assert "parse line 8" not in block.details
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/help"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert isinstance(app.screen, InfoScreen)
        assert "Deepy TUI Commands" in app.screen.markdown
        app.exit()


@pytest.mark.asyncio
async def test_tui_ps_command_opens_background_task_screen(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)
    app.background_tasks.start(
        command="worker",
        argv=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
    )

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/ps"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert isinstance(app.screen, InfoScreen)
        assert "Background Tasks" in app.screen.markdown
        assert "worker" in app.screen.markdown
        app.background_tasks.stop_all(force_after_grace=True)
        app.exit()


@pytest.mark.asyncio
async def test_tui_stop_command_requests_background_task_stop(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)
    app.background_tasks.start(
        command="worker",
        argv=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
    )

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/stop"
        await pilot.press("enter")
        await pilot.pause(0.1)

        assert isinstance(app.screen, ChoiceScreen)
        await pilot.press("enter")
        await pilot.pause(0.2)

        blocks = list(app.query(InfoBlock))
        assert any("Stop requested for background task" in block.body for block in blocks)
        left = str(app.query_one("#status-left", Label).content)
        assert "bg " not in left
        app.exit()


@pytest.mark.asyncio
async def test_tui_status_command_opens_status_screen(tmp_path, monkeypatch) -> None:
    calls = 0

    def fake_fetch(settings):
        nonlocal calls
        calls += 1
        return BalanceStatus(is_available=True)

    monkeypatch.setattr(tui_app, "fetch_deepseek_balance", fake_fetch)
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/status"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert isinstance(app.screen, InfoScreen)
        assert calls == 1
        assert "Project:" in app.screen.markdown
        assert "MCP:" in app.screen.markdown
        assert "Balance:" in app.screen.markdown
        app.exit()


@pytest.mark.asyncio
async def test_tui_status_command_does_not_fetch_balance_for_third_party_provider(tmp_path, monkeypatch) -> None:
    def fail_fetch(settings):
        raise AssertionError("balance lookup should not run")

    monkeypatch.setattr(tui_app, "fetch_deepseek_balance", fail_fetch)
    app = DeepyTuiApp(
        settings=Settings(
            model=ModelConfig(
                provider="xiaomi",
                name="mimo-v2.5-pro",
                base_url="https://api.xiaomimimo.com/v1",
                api_key="sk-test",
            )
        ),
        project_root=tmp_path,
        run_once=_idle_run_once,
    )

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/status"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert isinstance(app.screen, InfoScreen)
        assert "Balance:" in app.screen.markdown
        assert "unsupported provider" in app.screen.markdown
        app.exit()


@pytest.mark.asyncio
async def test_tui_non_status_surfaces_do_not_fetch_balance(tmp_path, monkeypatch) -> None:
    def fail_fetch(settings):
        raise AssertionError("balance lookup should not run")

    monkeypatch.setattr(tui_app, "fetch_deepseek_balance", fail_fetch)
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        app._update_status("Idle")
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/help"
        await pilot.press("enter")
        await pilot.pause(0.2)
        app._exit_with_summary()

        assert app.exit_summary_text is not None


@pytest.mark.asyncio
async def test_tui_theme_and_model_direct_commands_persist_settings(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    settings = load_settings(config_path)
    app = DeepyTuiApp(settings=settings, project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/theme light"
        await pilot.press("enter")
        await pilot.pause(0.2)
        prompt.text = "/model set deepseek-v4-flash high"
        await pilot.press("enter")
        await pilot.pause(0.2)
        prompt.text = "/model set openrouter xiaomi/mimo-v2.5 high"
        await pilot.press("enter")
        await pilot.pause(0.2)

        saved = load_settings(config_path)
        assert saved.ui.theme == "light"
        assert saved.model.provider == "openrouter"
        assert saved.model.name == "xiaomi/mimo-v2.5"
        assert saved.model.reasoning_mode == "high"
        rendered_info = "\n".join(block.body for block in app.query(InfoBlock))
        assert "Provider switched to openrouter" in rendered_info
        assert "Reconfigure the API key" in rendered_info
        assert "https://openrouter.ai/workspaces/default/keys" in rendered_info
        app.exit()


@pytest.mark.asyncio
async def test_tui_model_picker_refocuses_prompt_after_save(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    settings = load_settings(config_path)
    app = DeepyTuiApp(settings=settings, project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/model"
        await pilot.press("enter")
        await _wait_for(
            pilot,
            lambda: isinstance(app.screen, ChoiceScreen)
            and app.screen.title_text == "Select provider",
        )

        await pilot.press("enter")
        await _wait_for(
            pilot,
            lambda: isinstance(app.screen, ChoiceScreen)
            and app.screen.title_text == "Select model",
        )
        await pilot.press("enter")
        await _wait_for(
            pilot,
            lambda: isinstance(app.screen, ChoiceScreen)
            and app.screen.title_text == "Select thinking",
        )
        await pilot.press("enter")

        await _wait_for(pilot, lambda: app.query_one("#prompt-input", PromptTextArea).has_focus)
        saved = load_settings(config_path)
        assert saved.model.provider == "deepseek"
        assert saved.model.name == "deepseek-v4-pro"
        app.exit()


@pytest.mark.asyncio
async def test_tui_model_picker_refocuses_prompt_after_cancel(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    settings = load_settings(config_path)
    app = DeepyTuiApp(settings=settings, project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/model"
        await pilot.press("enter")
        await _wait_for(
            pilot,
            lambda: isinstance(app.screen, ChoiceScreen)
            and app.screen.title_text == "Select provider",
        )

        await pilot.press("escape")

        await _wait_for(pilot, lambda: app.query_one("#prompt-input", PromptTextArea).has_focus)
        app.exit()


@pytest.mark.asyncio
async def test_tui_new_command_resets_session_and_loaded_skills(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
            "name": "write_file",
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
                "name": "write_file",
                "arguments": '{"path":"selection_sort.py"}',
            },
            {"type": "function_call_output", "call_id": "write-1", "output": write_output},
            {"role": "assistant", "content": "Hi."},
            {"type": "function_call_output", "call_id": "shell-1", "output": shell_output},
        ]
    )
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
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
    session.record_usage({"prompt_tokens": 120, "completion_tokens": 4, "total_tokens": 124})
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "/sessions"
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert isinstance(app.screen, ChoiceScreen)
        assert app.screen.title_text == "Sessions"
        container = app.screen.query_one("Vertical")
        assert "width: 112" in container.styles.css
        options = app.screen.query_one("#choice-list", OptionList)
        label = _option_prompt_text(options.get_option_at_index(0))
        assert label.startswith("hello  ")
        assert "\n" not in label
        assert "completed" in label
        assert "120 tokens" in label
        assert "s1" in label
        assert "updated=" not in label
        assert "history estimate" not in label
        assert ".jsonl" not in label
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
        await _wait_for(pilot, lambda: app.query_one("#prompt-input", PromptTextArea).has_focus)
        await _submit_prompt(app, pilot, "ask", lambda: app.query_one(QuestionBlock))

        assert app.query_one(QuestionBlock).body == "Which package manager?"
        app.query_one(QuestionBlock).action_submit()
        await _wait_for(pilot, lambda: len(calls) == 2)

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
        await _wait_for(pilot, lambda: app.query_one("#prompt-input", PromptTextArea).has_focus)
        await _submit_prompt(app, pilot, "ask", lambda: app.query_one(QuestionBlock))

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
        await _wait_for(pilot, lambda: app.query_one("#prompt-input", PromptTextArea).has_focus)
        await _submit_prompt(app, pilot, "ask", lambda: app.query_one(QuestionBlock))

        block = app.query_one(QuestionBlock)
        block.selected_values = frozenset({"tests", "__other__"})
        custom = block.query_one("#question-custom", TextArea)
        custom.text = "lint"
        block.action_submit()
        await _wait_for(pilot, lambda: len(prompts) >= 2)

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
        await _wait_for(pilot, lambda: cancel_app.query_one("#prompt-input", PromptTextArea).has_focus)
        await _submit_prompt(cancel_app, pilot, "ask", lambda: cancel_app.query_one(QuestionBlock))
        cancel_app.query_one(QuestionBlock).action_cancel()
        await _wait_for(
            pilot,
            lambda: any("declined to answer" in block.body for block in cancel_app.query(UserBlock)),
        )

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
        await _wait_for(pilot, lambda: app.query_one("#prompt-input", PromptTextArea).has_focus)
        await _submit_prompt(app, pilot, "ask", lambda: app.query_one(QuestionBlock))

        block = app.query_one(QuestionBlock)
        options = block.query_one("#question-options", OptionList)
        options.highlighted = 2
        block.action_toggle_selected()
        await _wait_for(
            pilot,
            lambda: (
                block.query_one("#question-custom", TextArea).display
                and block.query_one("#question-custom", TextArea).has_focus
            ),
        )

        custom_option_text = _option_prompt_text(options.get_option_at_index(2))
        assert custom_option_text.startswith("[x]")
        assert "Custom answer" in custom_option_text
        custom = block.query_one("#question-custom", TextArea)
        assert custom.display
        assert custom.has_focus

        custom.text = "AI"
        custom.move_cursor((0, len(custom.text)))
        custom.action_newline()
        assert custom.text == "AI\n"
        custom.insert("coding")
        custom.action_submit()
        await _wait_for(pilot, lambda: len(prompts) == 2)

        assert '"Python goal?"="AI coding"' in prompts[-1]
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
        await _wait_for(pilot, lambda: app.query_one("#prompt-input", PromptTextArea).has_focus)
        await _submit_prompt(app, pilot, "ask", lambda: app.query_one(QuestionBlock))

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
        await _wait_for(pilot, lambda: app.query_one("#prompt-input", PromptTextArea).has_focus)
        await _submit_prompt(app, pilot, "ask", lambda: app.query_one(QuestionBlock))

        options = app.query_one("#question-options", OptionList)
        options.focus()
        await _wait_for(pilot, lambda: options.has_focus)
        assert options.has_focus
        assert "[x] Web" in _option_prompt_text(options.get_option_at_index(0))
        assert "[ ] Data" in _option_prompt_text(options.get_option_at_index(1))

        options.action_cursor_down()
        await _wait_for(pilot, lambda: "[x] Data" in _option_prompt_text(options.get_option_at_index(1)))
        assert "[ ] Web" in _option_prompt_text(options.get_option_at_index(0))
        assert "[x] Data" in _option_prompt_text(options.get_option_at_index(1))

        app.query_one(QuestionBlock).action_submit()
        await _wait_for(pilot, lambda: len(calls) == 2)
        assert '"Python goal?"="Data"' in calls[-1]
        app.exit()


@pytest.mark.asyncio
async def test_tui_tool_block_expands_hidden_details(tmp_path) -> None:
    long_output = "\n".join(f"line {index}" for index in range(30))
    tool_output = json.dumps(
        {
            "ok": True,
            "name": "read_file",
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
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "read"
        await pilot.press("enter")
        await pilot.pause(0.2)

        block = app.query_one(ToolBlock)
        assert block.details.startswith("line 0")
        assert "line 29" in block.details
        block.action_toggle_expand()
        await pilot.pause(0.01)
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
        await pilot.pause(0.01)
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
        await _wait_for(pilot, lambda: app.query_one("#prompt-input", PromptTextArea).has_focus)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        app.controller.add_prompt_history("first")
        app.controller.add_prompt_history("second")
        prompt.text = ""
        prompt.action_history_previous()
        await _wait_for(pilot, lambda: prompt.text == "second")
        assert prompt.text == "second"
        prompt.action_history_previous()
        await _wait_for(pilot, lambda: prompt.text == "first")
        assert prompt.text == "first"
        prompt.action_history_next()
        await _wait_for(pilot, lambda: prompt.text == "second")
        assert prompt.text == "second"
        prompt.action_history_next()
        await _wait_for(pilot, lambda: prompt.text == "")
        assert prompt.text == ""
        prompt.action_cursor_up()
        await _wait_for(pilot, lambda: prompt.text == "second")
        assert prompt.text == "second"
        prompt.action_cursor_up()
        await _wait_for(pilot, lambda: prompt.text == "first")
        assert prompt.text == "first"
        prompt.action_cursor_down()
        await _wait_for(pilot, lambda: prompt.text == "second")
        assert prompt.text == "second"
        app.exit()


@pytest.mark.asyncio
async def test_tui_prompt_arrow_keys_still_move_inside_multiline_input(tmp_path) -> None:
    app = DeepyTuiApp(settings=Settings(), project_root=tmp_path, run_once=_idle_run_once)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.01)
        prompt = app.query_one("#prompt-input", PromptTextArea)
        prompt.text = "first\nsecond"
        prompt.move_cursor((1, 0))

        await pilot.press("up")
        assert prompt.cursor_location == (0, 0)

        await pilot.press("down")
        assert prompt.cursor_location == (1, 0)
        app.exit()
