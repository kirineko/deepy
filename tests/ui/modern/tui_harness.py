from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from textual.widgets.option_list import Option

from deepy.llm.runner import RunSummary
from deepy.ui.modern.app import DeepyTuiApp
from deepy.ui.modern.screens import TextInputScreen
from deepy.ui.modern.widgets import InlineChoiceBlock, PromptTextArea


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


async def _choose_inline_option(app: DeepyTuiApp, pilot, title: str, *, down: int = 0) -> None:
    await _wait_for(
        pilot,
        lambda: app.query(InlineChoiceBlock).first()
        and app.query(InlineChoiceBlock).last().title_text == title,
    )
    for _ in range(down):
        await pilot.press("down")
    await pilot.press("enter")


async def _submit_text_input(app: DeepyTuiApp, pilot, title: str, value: str) -> None:
    await _wait_for(
        pilot,
        lambda: isinstance(app.screen, TextInputScreen)
        and app.screen.title_text == title,
    )
    app.screen.query_one("#text-input").value = value  # type: ignore[attr-defined]
    await pilot.press("enter")


async def _submit_prompt(app: DeepyTuiApp, pilot, text: str, condition: Callable[[], object]) -> None:
    prompt = app.query_one("#prompt-input", PromptTextArea)
    prompt.text = text
    prompt.action_submit()
    await _wait_for(pilot, condition)


@asynccontextmanager
async def tui_harness(
    app: DeepyTuiApp,
    size: tuple[int, int] = (100, 32),
) -> AsyncIterator[tuple[DeepyTuiApp, object, PromptTextArea]]:
    async with app.run_test(size=size) as pilot:
        prompt = app.query_one("#prompt-input", PromptTextArea)
        try:
            yield app, pilot, prompt
        finally:
            app.exit()
