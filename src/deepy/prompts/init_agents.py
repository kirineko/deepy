from __future__ import annotations

from pathlib import Path


def build_agents_init_prompt(project_root: Path, *, extra_instruction: str = "") -> str:
    target = project_root.resolve() / "AGENTS.md"
    action = "update" if target.exists() else "create"
    extra = extra_instruction.strip()
    extra_block = f"\nAdditional user instruction:\n{extra}\n" if extra else ""
    return f"""Analyze this repository and {action} the project root AGENTS.md file.

Target file: {target}
{extra_block}
Requirements:
- Inspect the actual repository structure, configuration, commands, tests, and docs before writing.
- If the target file already exists, read it first and preserve useful accurate guidance.
- Write only the project root AGENTS.md unless the user explicitly asks for more files.
- Make the file useful for future coding agents that know nothing about this project.
- Use the main natural language already used by this repository's docs and comments.
- Keep it concise and specific. Avoid generic advice that is not grounded in this repo.
- Include sections only when they are useful for this repo.

Recommended sections:
- Project overview
- Commands
- Architecture and module organization
- Coding style and naming
- Verification and testing
- Agent workflow and boundaries
- Security or configuration notes, if relevant

For commands, include exact commands that exist in this repo, such as test, lint,
type-check, build, or run commands. For boundaries, include concrete constraints
that prevent accidental unrelated rewrites or loss of user changes.
"""
