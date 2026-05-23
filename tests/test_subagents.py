from __future__ import annotations

from deepy.subagents import (
    built_in_subagents,
    discover_subagents,
    load_subagent_file,
)


def test_built_in_subagents_are_available():
    definitions = {definition.name: definition for definition in built_in_subagents()}

    assert set(definitions) == {"explore", "reviewer", "tester"}
    assert definitions["explore"].mcp.inherit_search is True
    assert "test_shell" in definitions["tester"].tools
    assert "apply_patch" not in definitions["tester"].tools
    assert definitions["tester"].tool_name == "subagent_tester"


def test_custom_subagent_parses_markdown_frontmatter(tmp_path):
    path = tmp_path / "triage.md"
    path.write_text(
        """---
name: triage
description: Read logs and summarize likely causes.
model: inherit
tools:
  - Search
  - read_file
mcp:
  inherit_search: false
max_turns: 12
---

Read only. Return concise findings.
""",
        encoding="utf-8",
    )

    definition, error = load_subagent_file(path, source="project")

    assert error is None
    assert definition is not None
    assert definition.name == "triage"
    assert definition.model is None
    assert definition.max_turns == 12
    assert definition.tools == ("Search", "read_file")


def test_discovery_precedence_project_over_user_over_builtin(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    (project / ".deepy" / "subagents").mkdir(parents=True)
    (home / ".deepy" / "subagents").mkdir(parents=True)
    (home / ".deepy" / "subagents" / "tester.md").write_text(
        """---
name: tester
description: User tester.
tools: [Search]
---
User tester prompt.
""",
        encoding="utf-8",
    )
    (project / ".deepy" / "subagents" / "tester.md").write_text(
        """---
name: tester
description: Project tester.
tools: [read_file]
---
Project tester prompt.
""",
        encoding="utf-8",
    )

    result = discover_subagents(project, user_home=home)
    tester = next(definition for definition in result.definitions if definition.name == "tester")

    assert tester.description == "Project tester."
    assert tester.tools == ("read_file",)
    assert tester.source.startswith("project:")


def test_invalid_custom_subagent_is_reported_and_agents_skills_ignored(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    (project / ".deepy" / "subagents").mkdir(parents=True)
    (project / ".agents" / "skills").mkdir(parents=True)
    (project / ".deepy" / "subagents" / "bad.md").write_text(
        """---
name: bad
description: Bad
tools: [apply_patch]
---
Prompt.
""",
        encoding="utf-8",
    )
    (project / ".agents" / "skills" / "not-a-subagent.md").write_text(
        """---
name: shadow
description: Should not load.
---
Ignored.
""",
        encoding="utf-8",
    )

    result = discover_subagents(project, user_home=home)

    assert any("Unsupported subagent tools" in diagnostic.message for diagnostic in result.diagnostics)
    assert "shadow" not in {definition.name for definition in result.definitions}
