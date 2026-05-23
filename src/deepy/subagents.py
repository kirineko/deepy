from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_SUBAGENT_TOOLS = frozenset(
    {
        "Search",
        "WebFetch",
        "WebSearch",
        "load_skill",
        "read_file",
        "task_output",
        "test_shell",
    }
)
MUTATION_TOOLS = frozenset({"apply_patch", "edit_text", "shell", "write_file"})
DEFAULT_CUSTOM_TOOLS = ("Search", "read_file")
MAX_SUBAGENT_TURNS = 100
SUBAGENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class SubagentMcpConfig:
    inherit_search: bool = False


@dataclass(frozen=True)
class SubagentDefinition:
    name: str
    description: str
    instructions: str
    tools: tuple[str, ...]
    model: str | None = None
    max_turns: int = 30
    mcp: SubagentMcpConfig = field(default_factory=SubagentMcpConfig)
    source: str = "built-in"

    @property
    def tool_name(self) -> str:
        return f"subagent_{self.name.replace('-', '_')}"


@dataclass(frozen=True)
class SubagentDiagnostic:
    path: str
    message: str


@dataclass(frozen=True)
class SubagentDiscoveryResult:
    definitions: tuple[SubagentDefinition, ...]
    diagnostics: tuple[SubagentDiagnostic, ...] = ()


def built_in_subagents() -> tuple[SubagentDefinition, ...]:
    return (
        SubagentDefinition(
            name="explore",
            description=(
                "Use for broad read-only codebase, documentation, dependency, or web/search "
                "investigation that can run independently before Deepy synthesizes the answer."
            ),
            tools=("Search", "read_file", "WebSearch", "WebFetch", "load_skill"),
            max_turns=30,
            mcp=SubagentMcpConfig(inherit_search=True),
            instructions=(
                "You are Deepy's explore subagent. Investigate the assigned scope without "
                "modifying files. Prefer local Search/read_file first, use web or search-class "
                "MCP tools when current or external information is needed, and return a concise "
                "report with key findings, relevant paths or URLs, uncertainties, and next steps."
            ),
        ),
        SubagentDefinition(
            name="reviewer",
            description=(
                "Use for focused read-only review of correctness, security, maintainability, "
                "design risk, regressions, or missing tests."
            ),
            tools=("Search", "read_file", "WebFetch"),
            max_turns=24,
            instructions=(
                "You are Deepy's reviewer subagent. Review only the assigned code, design, or "
                "change. Do not modify files or run commands. Prioritize concrete findings with "
                "file references, severity, impact, and suggested fixes. If no issue is found, "
                "state the residual risk or missing verification plainly."
            ),
        ),
        SubagentDefinition(
            name="tester",
            description=(
                "Use for bug reproduction, targeted test execution, diagnostics, and command-based "
                "verification through Deepy's constrained test_shell."
            ),
            tools=("Search", "read_file", "test_shell"),
            max_turns=30,
            instructions=(
                "You are Deepy's tester subagent. Reproduce behavior and run targeted verification "
                "commands only through test_shell. Do not modify source files. Report exact commands, "
                "exit codes, key stdout/stderr, and what remains unverified. If test_shell returns "
                "approval_required, stop and report the command, reason, and approval token so the "
                "main Deepy agent can ask the user."
            ),
        ),
    )


def discover_subagents(
    project_root: Path,
    *,
    user_home: Path | None = None,
) -> SubagentDiscoveryResult:
    definitions: dict[str, SubagentDefinition] = {
        definition.name: definition for definition in built_in_subagents()
    }
    diagnostics: list[SubagentDiagnostic] = []
    home = user_home if user_home is not None else Path.home()

    for path, source in (
        (home / ".deepy" / "subagents", "user"),
        (project_root / ".deepy" / "subagents", "project"),
    ):
        loaded, errors = load_subagents_from_directory(path, source=source)
        diagnostics.extend(errors)
        for definition in loaded:
            definitions[definition.name] = definition

    return SubagentDiscoveryResult(
        definitions=tuple(definitions[name] for name in sorted(definitions)),
        diagnostics=tuple(diagnostics),
    )


def load_subagents_from_directory(
    directory: Path,
    *,
    source: str,
) -> tuple[tuple[SubagentDefinition, ...], tuple[SubagentDiagnostic, ...]]:
    if not directory.exists() or not directory.is_dir():
        return (), ()

    definitions: list[SubagentDefinition] = []
    diagnostics: list[SubagentDiagnostic] = []
    for path in sorted(directory.glob("*.md")):
        definition, error = load_subagent_file(path, source=source)
        if definition is None:
            diagnostics.append(SubagentDiagnostic(str(path), error or "Invalid subagent."))
            continue
        definitions.append(definition)
    return tuple(definitions), tuple(diagnostics)


def load_subagent_file(path: Path, *, source: str) -> tuple[SubagentDefinition | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"Failed to read subagent definition: {exc}"
    frontmatter, body, error = _split_frontmatter(text)
    if error is not None:
        return None, error
    try:
        raw = yaml.safe_load(frontmatter) if frontmatter.strip() else None
    except yaml.YAMLError as exc:
        return None, f"Invalid YAML frontmatter: {exc}"
    if not isinstance(raw, dict):
        return None, "Subagent frontmatter must be a YAML mapping."
    return validate_subagent_definition(raw, body, source=f"{source}:{path}")


def validate_subagent_definition(
    raw: dict[str, Any],
    body: str,
    *,
    source: str,
) -> tuple[SubagentDefinition | None, str | None]:
    name = normalize_subagent_name(raw.get("name"))
    if name is None:
        return None, "Subagent requires a valid name using letters, digits, '_' or '-'."
    description = _clean_string(raw.get("description"))
    if not description:
        return None, "Subagent requires a non-empty description."
    instructions = body.strip()
    if not instructions:
        return None, "Subagent requires a Markdown body with instructions."

    model = _clean_string(raw.get("model"))
    if model in {"", "inherit"}:
        model = None

    max_turns_raw = raw.get("max_turns", 30)
    if isinstance(max_turns_raw, bool) or not isinstance(max_turns_raw, int):
        return None, "max_turns must be an integer."
    if max_turns_raw < 1 or max_turns_raw > MAX_SUBAGENT_TURNS:
        return None, f"max_turns must be between 1 and {MAX_SUBAGENT_TURNS}."

    tools, error = _parse_tools(raw.get("tools"), raw.get("disallowedTools"))
    if error is not None:
        return None, error

    mcp, error = _parse_mcp(raw.get("mcp"))
    if error is not None:
        return None, error

    return (
        SubagentDefinition(
            name=name,
            description=description,
            instructions=instructions,
            tools=tools,
            model=model,
            max_turns=max_turns_raw,
            mcp=mcp,
            source=source,
        ),
        None,
    )


def normalize_subagent_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"[^a-z0-9_-]+", "_", value.strip().lower()).strip("_-")
    if not normalized or not SUBAGENT_NAME_RE.match(normalized):
        return None
    return normalized


def _split_frontmatter(text: str) -> tuple[str, str, str | None]:
    if not text.startswith("---\n"):
        return "", "", "Subagent Markdown must start with YAML frontmatter."
    end = text.find("\n---", 4)
    if end < 0:
        return "", "", "Subagent YAML frontmatter is not closed."
    frontmatter = text[4:end]
    body_start = end + len("\n---")
    if body_start < len(text) and text[body_start] == "\n":
        body_start += 1
    return frontmatter, text[body_start:], None


def _parse_tools(tools_value: object, disallowed_value: object) -> tuple[tuple[str, ...], str | None]:
    if tools_value is None:
        tools = list(DEFAULT_CUSTOM_TOOLS)
    else:
        raw_tools = _string_list(tools_value)
        if raw_tools is None:
            return (), "tools must be a list of supported tool names."
        tools = [_canonical_tool_name(item) for item in raw_tools]

    disallowed: set[str] = set()
    if disallowed_value is not None:
        raw_disallowed = _string_list(disallowed_value)
        if raw_disallowed is None:
            return (), "disallowedTools must be a list of tool names."
        disallowed = {_canonical_tool_name(item) for item in raw_disallowed}

    unsupported = sorted(
        {
            item
            for item in [*tools, *disallowed]
            if item not in SUPPORTED_SUBAGENT_TOOLS or item in MUTATION_TOOLS
        }
    )
    if unsupported:
        return (), "Unsupported subagent tools: " + ", ".join(unsupported)

    result: list[str] = []
    for tool in tools:
        if tool in disallowed or tool in result:
            continue
        result.append(tool)
    if not result:
        return (), "Subagent must have at least one supported tool."
    return tuple(result), None


def _parse_mcp(value: object) -> tuple[SubagentMcpConfig, str | None]:
    if value is None:
        return SubagentMcpConfig(), None
    if not isinstance(value, Mapping):
        return SubagentMcpConfig(), "mcp must be a mapping."
    mcp = {str(key): item for key, item in value.items()}
    allowed_keys = {"inherit_search"}
    unknown = sorted(key for key in mcp if key not in allowed_keys)
    if unknown:
        return SubagentMcpConfig(), "Unsupported mcp options: " + ", ".join(unknown)
    inherit = mcp.get("inherit_search", False)
    if not isinstance(inherit, bool):
        return SubagentMcpConfig(), "mcp.inherit_search must be true or false."
    return SubagentMcpConfig(inherit_search=inherit), None


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        result.append(item)
    return result


def _canonical_tool_name(value: str) -> str:
    aliases = {
        "search": "Search",
        "webfetch": "WebFetch",
        "web_search": "WebSearch",
        "websearch": "WebSearch",
        "read": "read_file",
    }
    stripped = value.strip()
    return aliases.get(stripped.lower(), stripped)


def _clean_string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
