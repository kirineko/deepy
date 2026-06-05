from __future__ import annotations

from pathlib import Path

from .constants import SENSITIVE_MUTATION_NAMES, UNSUPPORTED_TEXT_MUTATION_SUFFIXES
from .file_state import FileSnippet
from .result import ToolResult
from .shell_command import (
    _find_suffix_matches,
    _load_gitignore_matcher,
    _normalize_relative_suffix,
)
from .text_io import _detect_text_encoding
from .tool_dataclasses import MutationErrorCode, MutationPolicyDecision, UpdateEdit

def _resolve_in_cwd(cwd: Path, path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = cwd / candidate
    return candidate.resolve()


def _resolve_mutation_target(cwd: Path, path: str) -> tuple[Path | None, str | None, dict[str, object]]:
    if not path:
        return None, "file_path is required.", {"error_code": MutationErrorCode.INVALID_ARGUMENTS}
    raw = Path(path).expanduser()
    candidate = raw if raw.is_absolute() else cwd / raw
    try:
        target = candidate.resolve(strict=False)
        root = cwd.resolve(strict=False)
    except OSError as exc:
        return (
            None,
            f"Could not resolve path: {exc}",
            {"error_code": MutationErrorCode.PATH_POLICY, "path": str(candidate)},
        )
    if not _is_relative_to(target, root):
        return (
            None,
            "File mutation target must stay within the current project.",
            {
                "error_code": MutationErrorCode.PATH_POLICY,
                "path": str(target),
                "policyDecision": "deny",
            },
        )
    if _path_has_symlink_escape(candidate, root):
        return (
            None,
            "File mutation target follows a symlink outside the current project.",
            {
                "error_code": MutationErrorCode.SYMLINK_POLICY,
                "path": str(target),
                "policyDecision": "deny",
                "symlinkPolicy": "deny_escape",
            },
        )
    return target, None, {}


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _path_has_symlink_escape(path: Path, root: Path) -> bool:
    try:
        relative = path.resolve(strict=False).relative_to(root)
    except ValueError:
        return True
    current = root
    parts = relative.parts
    for part in parts:
        current = current / part
        try:
            if current.is_symlink() and not _is_relative_to(current.resolve(strict=True), root):
                return True
        except OSError:
            return True
    return False


def _mutation_policy_decision(cwd: Path, target: Path) -> MutationPolicyDecision:
    root = cwd.resolve()
    if _is_sensitive_mutation_target(target):
        return MutationPolicyDecision(
            decision="requires_approval",
            reason="Target matches sensitive-file policy.",
            metadata={"policyKind": "sensitive_file", "path": str(target)},
        )
    try:
        relative = target.relative_to(root)
    except ValueError:
        return MutationPolicyDecision(
            decision="deny",
            reason="Target is outside the current project.",
            metadata={"policyKind": "workspace_boundary", "path": str(target)},
        )
    if relative.parts and relative.parts[0] == ".git":
        return MutationPolicyDecision(
            decision="deny",
            reason="Mutating .git internals is blocked.",
            metadata={"policyKind": "sensitive_directory", "path": str(target)},
        )
    gitignore = _load_gitignore_matcher(root)
    if gitignore.ignores(str(relative).replace("\\", "/"), target.is_dir()):
        return MutationPolicyDecision(
            decision="warn",
            reason="Target matches .gitignore.",
            metadata={"policyKind": "ignore", "path": str(target)},
        )
    return MutationPolicyDecision(metadata={"path": str(target)})


def _is_sensitive_mutation_target(target: Path) -> bool:
    lowered = {part.lower() for part in target.parts}
    return any(name in lowered for name in SENSITIVE_MUTATION_NAMES)


def _policy_error_result(name: str, decision: MutationPolicyDecision) -> str | None:
    if decision.decision == "deny":
        return ToolResult.error_result(
            name,
            decision.reason or "Mutation denied by policy.",
            metadata={
                "error_code": MutationErrorCode.GUARDRAIL_BLOCK,
                **decision.result_metadata(),
            },
        ).to_json()
    if decision.decision == "requires_approval":
        return ToolResult.error_result(
            name,
            decision.reason or "Mutation requires approval.",
            metadata={
                "error_code": MutationErrorCode.APPROVAL_REQUIRED,
                **decision.result_metadata(),
            },
        ).to_json()
    return None


def _unsupported_text_mutation_reason(path: Path) -> str | None:
    if path.exists():
        if not path.is_file():
            return "Target is not a regular text file."
        try:
            sample = path.read_bytes()[:8192]
        except OSError as exc:
            return f"Could not read target bytes: {exc}"
        detected_encoding = _detect_text_encoding(sample)
        if b"\x00" in sample and detected_encoding != "utf16le":
            return "Target appears to be binary and cannot be mutated as text."
    if path.suffix.lower() in UNSUPPORTED_TEXT_MUTATION_SUFFIXES:
        return "Target type is not supported by text mutation tools."
    return None


def _mutation_error_metadata(
    code: str,
    *,
    path: Path | None = None,
    recovery: str | None = None,
    **extra: object,
) -> dict[str, object]:
    metadata: dict[str, object] = {"error_code": code}
    if path is not None:
        metadata["path"] = str(path)
    if recovery:
        metadata["recovery"] = recovery
    metadata.update(extra)
    return metadata


def _update_noop_metadata(edit: UpdateEdit, target: Path) -> dict[str, object]:
    return {
        "index": edit.index,
        "path": str(target),
        "error": "Update would not change file content.",
        **_mutation_error_metadata(MutationErrorCode.NO_OP, path=target),
    }


def _resolve_read_target(cwd: Path, path: str) -> tuple[Path | None, str | None]:
    candidate = Path(path).expanduser()
    target = _resolve_in_cwd(cwd, path)
    if target.exists() or candidate.is_absolute():
        return target, None
    if candidate.parts and candidate.parts[0] == "..":
        return None, "Relative read paths must stay within the current project."

    suffix = _normalize_relative_suffix(path)
    if not suffix:
        return target, None
    matches = _find_suffix_matches(cwd, suffix)
    if len(matches) > 1:
        shown = "\n".join(str(match) for match in matches[:3])
        more = f"\n...and {len(matches) - 3} more." if len(matches) > 3 else ""
        return (
            None,
            "File path is ambiguous and may refer to multiple files:\n" + shown + more,
        )
    if len(matches) == 1:
        return matches[0], None
    return target, None


def _snippet_metadata(snippet: FileSnippet) -> dict[str, object]:
    return {
        "id": snippet.id,
        "filePath": str(snippet.path),
        "file_path": str(snippet.path),
        "startLine": snippet.start_line,
        "endLine": snippet.end_line,
        "start_line": snippet.start_line,
        "end_line": snippet.end_line,
    }
