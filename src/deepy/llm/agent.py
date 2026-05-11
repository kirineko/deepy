from __future__ import annotations

from pathlib import Path

from deepy.config import Settings
from deepy.prompts import build_system_prompt
from deepy.skills import SkillInfo
from deepy.tools import ToolRuntime
from deepy.tools.agents import build_function_tools

from .provider import ProviderBundle, build_provider_bundle


def build_deepy_agent(
    settings: Settings,
    runtime: ToolRuntime,
    *,
    project_root: Path,
    provider: ProviderBundle | None = None,
    loaded_skills: list[SkillInfo] | None = None,
):
    from agents import Agent

    provider = provider or build_provider_bundle(settings)
    return Agent(
        name="Deepy",
        instructions=build_system_prompt(project_root, settings, loaded_skills=loaded_skills),
        model=provider.model,
        model_settings=provider.model_settings,
        tools=build_function_tools(runtime),
    )
