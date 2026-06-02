from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal, cast


class AuditMode(StrEnum):
    NORMAL = "normal"
    AUTO = "auto"
    YOLO = "yolo"


AUDIT_MODES = {mode.value for mode in AuditMode}
DEFAULT_AUDIT_MODE = AuditMode.YOLO
AuditAction = Literal["text_write", "command", "background_task_control", "mcp_tool"]
ApprovalOutcome = Literal["approve", "reject"]


def parse_audit_mode(value: object, *, default: AuditMode = DEFAULT_AUDIT_MODE) -> AuditMode:
    if isinstance(value, AuditMode):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in AUDIT_MODES:
            return AuditMode(normalized)
    return default


def is_valid_audit_mode(value: str) -> bool:
    return value in AUDIT_MODES


def next_audit_mode(mode: AuditMode | str) -> AuditMode:
    current = parse_audit_mode(mode)
    order = (AuditMode.NORMAL, AuditMode.AUTO, AuditMode.YOLO)
    index = order.index(current)
    return order[(index + 1) % len(order)]


@dataclass
class AuditModeState:
    mode: AuditMode = DEFAULT_AUDIT_MODE

    @classmethod
    def from_value(cls, value: object) -> "AuditModeState":
        return cls(parse_audit_mode(value))

    def set(self, value: AuditMode | str) -> AuditMode:
        self.mode = parse_audit_mode(value, default=self.mode)
        return self.mode

    def cycle(self) -> AuditMode:
        self.mode = next_audit_mode(self.mode)
        return self.mode


@dataclass(frozen=True)
class McpSafeTool:
    server: str
    tool: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "McpSafeTool | None":
        server = value.get("server")
        tool = value.get("tool")
        if not isinstance(server, str) or not server.strip():
            return None
        if not isinstance(tool, str) or not tool.strip():
            return None
        return cls(server=server.strip(), tool=tool.strip())


@dataclass(frozen=True)
class AuditConfig:
    mode: AuditMode = DEFAULT_AUDIT_MODE
    mcp_safe_tools: tuple[McpSafeTool, ...] = ()
    invalid_mode: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "AuditConfig":
        raw_mode = raw.get("mode")
        mode = parse_audit_mode(raw_mode)
        invalid_mode = (
            str(raw_mode)
            if isinstance(raw_mode, str) and raw_mode.strip() and raw_mode.strip().lower() not in AUDIT_MODES
            else None
        )
        safe_tools: list[McpSafeTool] = []
        for item in _safe_tool_entries(raw.get("mcp_safe_tools")):
            parsed = McpSafeTool.from_mapping(item)
            if parsed is not None:
                safe_tools.append(parsed)
        return cls(mode=mode, mcp_safe_tools=tuple(safe_tools), invalid_mode=invalid_mode)

    def is_mcp_tool_safe(self, server: str, tool: str) -> bool:
        return any(entry.server == server and entry.tool == tool for entry in self.mcp_safe_tools)


@dataclass
class AuditPolicy:
    mode_getter: Callable[[], AuditMode]
    config: AuditConfig = field(default_factory=AuditConfig)

    @classmethod
    def from_mode(cls, mode: AuditMode | str, config: AuditConfig | None = None) -> "AuditPolicy":
        parsed = parse_audit_mode(mode)
        return cls(lambda: parsed, config=config or AuditConfig(mode=parsed))

    def active_mode(self) -> AuditMode:
        return parse_audit_mode(self.mode_getter())

    def needs_approval(self, action: AuditAction) -> bool:
        mode = self.active_mode()
        if mode == AuditMode.YOLO:
            return False
        if mode == AuditMode.NORMAL:
            return action in {"text_write", "command", "background_task_control", "mcp_tool"}
        if mode == AuditMode.AUTO:
            return action in {"command", "background_task_control", "mcp_tool"}
        return True

    def needs_mcp_approval(self, *, server: str, tool: str) -> bool:
        mode = self.active_mode()
        if mode == AuditMode.YOLO:
            return False
        if mode == AuditMode.AUTO and self.config.is_mcp_tool_safe(server, tool):
            return False
        return True


@dataclass(frozen=True)
class PendingApproval:
    index: int
    name: str
    tool_name: str
    arguments: str
    call_id: str = ""
    agent_name: str = ""
    action_kind: str = "tool"
    server_name: str = ""
    preflight: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ApprovalDecision:
    outcome: ApprovalOutcome
    always: bool = False
    rejection_message: str | None = None


def _safe_tool_entries(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    entries: list[Mapping[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            entries.append(cast(Mapping[str, Any], item))
    return entries
