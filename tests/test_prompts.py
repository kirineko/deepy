from __future__ import annotations

from deepy.config import Settings
from deepy.prompts import build_system_prompt
from deepy.prompts.rules import load_project_rules
from deepy.prompts.runtime_context import build_runtime_context
from deepy.skills import (
    discover_skills,
    find_skill,
    format_loaded_skills_for_prompt,
    format_skills_for_prompt,
    match_skills_for_prompt,
    read_skill_body,
)


def test_discover_skills_reads_user_and_project_skills_with_project_override(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    user_skill = home / ".agents" / "skills" / "demo"
    project_skill = project / ".deepy" / "skills" / "demo"
    other_skill = project / ".deepy" / "skills" / "other"
    user_skill.mkdir(parents=True)
    project_skill.mkdir(parents=True)
    other_skill.mkdir(parents=True)
    user_skill.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: User version\n---\nBody",
        encoding="utf-8",
    )
    project_skill.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Project version\n---\nBody",
        encoding="utf-8",
    )
    other_skill.joinpath("SKILL.md").write_text("# Other skill\n", encoding="utf-8")

    skills = discover_skills(project, home=home)

    assert [(skill.name, skill.description, skill.scope) for skill in skills] == [
        ("demo", "Project version", "project"),
        ("other", "Other skill", "project"),
    ]


def test_format_skills_for_prompt_groups_by_scope(tmp_path):
    project = tmp_path / "project"
    skill_dir = project / ".deepy" / "skills" / "review"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: review\ndescription: Review code\n---\n",
        encoding="utf-8",
    )

    rendered = format_skills_for_prompt(discover_skills(project, home=tmp_path / "home"))

    assert "Project skills:" in rendered
    assert "review - Review code" in rendered


def test_load_project_rules_reads_project_then_user_rules(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    home.joinpath(".deepy").mkdir(parents=True)
    project.joinpath("AGENTS.md").write_text("project rule", encoding="utf-8")
    home.joinpath(".deepy", "AGENTS.md").write_text("user rule", encoding="utf-8")

    rules = load_project_rules(project, home=home)

    assert "project rule" in rules
    assert "user rule" in rules
    assert rules.index("project rule") < rules.index("user rule")


def test_system_prompt_includes_rules_default_skill_and_skills(tmp_path):
    skill_dir = tmp_path / ".deepy" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text("---\nname: demo\ndescription: Demo skill\n---\n", encoding="utf-8")

    prompt = build_system_prompt(
        tmp_path,
        Settings(),
        project_rules="Follow local rules.",
        skills=discover_skills(tmp_path, home=tmp_path / "home"),
        runtime_context="Runtime context here.",
    )

    assert "Keep the latest user task" in prompt
    assert "Follow local rules." in prompt
    assert "## WebSearch" in prompt
    assert "## WebFetch" in prompt
    assert "## bash" in prompt
    assert "Use `modify` for file changes" in prompt
    assert "Match shell commands to the runtime context" in prompt
    assert "## modify" in prompt
    assert "content` only when the target file does not exist" in prompt
    assert "demo - Demo skill" in prompt
    assert "Runtime context here." in prompt


def test_system_prompt_includes_powershell_tool_guidance(tmp_path):
    prompt = build_system_prompt(
        tmp_path,
        Settings(),
        project_rules="",
        skills=[],
        runtime_context=(
            "Runtime environment:\n"
            "- OS family: windows\n"
            "- Shell kind: powershell\n"
            "- Command dialect: powershell\n"
            "- Path style: windows"
        ),
    )

    assert "Prefer PowerShell syntax for `powershell`" in prompt
    assert "detected runtime shell" in prompt
    assert "command dialect" in prompt
    assert "PowerShell-compatible commands and Windows paths" in prompt


def test_system_prompt_keeps_static_cache_prefix_before_dynamic_context(tmp_path):
    prompt = build_system_prompt(
        tmp_path,
        Settings(),
        project_rules="Dynamic project rule.",
        skills=[],
        runtime_context="Dynamic runtime context.",
    )

    assert prompt.index("Tool documentation:") < prompt.index("Project rules:")
    assert prompt.index("Default skill:") < prompt.index("Project rules:")
    assert prompt.index("Project rules:") < prompt.index("Runtime context:")
    assert "Dynamic runtime context." in prompt


def test_find_skill_and_read_body_strip_frontmatter(tmp_path):
    skill_dir = tmp_path / ".deepy" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Body\nUse this skill.",
        encoding="utf-8",
    )

    skill = find_skill(tmp_path, "demo", home=tmp_path / "home")

    assert skill is not None
    assert read_skill_body(skill) == "# Body\nUse this skill."


def test_match_skills_for_prompt_uses_name_and_description(tmp_path):
    project = tmp_path / "project"
    django_dir = project / ".deepy" / "skills" / "django"
    review_dir = project / ".deepy" / "skills" / "review"
    django_dir.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    django_dir.joinpath("SKILL.md").write_text(
        "---\nname: django\ndescription: Django migration specialist\n---\n",
        encoding="utf-8",
    )
    review_dir.joinpath("SKILL.md").write_text(
        "---\nname: review\ndescription: Pull request review\n---\n",
        encoding="utf-8",
    )

    matches = match_skills_for_prompt(
        discover_skills(project, home=tmp_path / "home"),
        "Please fix the Django migration failure.",
    )

    assert [skill.name for skill in matches] == ["django"]


def test_format_loaded_skills_for_prompt_includes_skill_body(tmp_path):
    skill_dir = tmp_path / ".deepy" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Body\nUse this skill.",
        encoding="utf-8",
    )
    skill = find_skill(tmp_path, "demo", home=tmp_path / "home")
    assert skill is not None

    rendered = format_loaded_skills_for_prompt([skill])

    assert '<skill name="demo">' in rendered
    assert "Use this skill." in rendered


def test_format_loaded_skills_for_prompt_is_deterministic(tmp_path):
    alpha_dir = tmp_path / ".deepy" / "skills" / "alpha"
    beta_dir = tmp_path / ".deepy" / "skills" / "beta"
    alpha_dir.mkdir(parents=True)
    beta_dir.mkdir(parents=True)
    alpha_dir.joinpath("SKILL.md").write_text(
        "---\nname: alpha\ndescription: Alpha\n---\nAlpha body.",
        encoding="utf-8",
    )
    beta_dir.joinpath("SKILL.md").write_text(
        "---\nname: beta\ndescription: Beta\n---\nBeta body.",
        encoding="utf-8",
    )
    alpha = find_skill(tmp_path, "alpha", home=tmp_path / "home")
    beta = find_skill(tmp_path, "beta", home=tmp_path / "home")
    assert alpha is not None
    assert beta is not None

    rendered = format_loaded_skills_for_prompt([beta, alpha])

    assert rendered.index('<skill name="alpha">') < rendered.index('<skill name="beta">')


def test_build_runtime_context_includes_top_level_entries(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "reference").mkdir()
    (tmp_path / "spec").mkdir()
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / "dist").mkdir()
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    context = build_runtime_context(tmp_path)

    assert f"Project root: {tmp_path}" in context
    assert "Current working directory:" in context
    assert "Home directory:" in context
    assert "System:" in context
    assert "Shell:" in context
    assert "Runtime environment:" in context
    assert "- OS family:" in context
    assert "- Shell kind:" in context
    assert "- Command dialect:" in context
    assert "- Path style:" in context
    assert "Python:" in context
    assert "Node:" in context
    assert "Tool availability:" in context
    assert "- rg:" in context
    assert "- jq:" in context
    assert "- ast-grep:" in context
    assert "Git dirty:" in context
    assert "- src/" in context
    assert "- README.md" in context
    assert "- reference/" in context
    assert "- spec/" in context
    assert ".pytest_cache/" not in context
    assert "dist/" not in context


def test_build_runtime_context_can_omit_git_dirty_for_prompt_cache(tmp_path):
    context = build_runtime_context(tmp_path, include_git_dirty=False)

    assert "Git dirty:" not in context
