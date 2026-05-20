from __future__ import annotations

import base64
import gzip
import math
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
import zlib
from dataclasses import dataclass, field
from difflib import unified_diff
from fnmatch import fnmatch
from html.parser import HTMLParser
from pathlib import Path
from typing import cast

from deepy.config import DEFAULT_WEB_SEARCH_SEARXNG_URL, Settings, mask_secret
from deepy.todos import TodoItem, normalize_todo_items, todo_counts, todo_items_to_payload
from deepy.types.tool_payloads import AskUserOption, AskUserQuestion
from deepy.utils import json as json_utils

from .file_state import FileSnippet, FileState
from .result import ToolResult
from .shell_output import decode_shell_output
from .shell_utils import RuntimeEnvironment
from .shell_utils import build_disable_extglob_command
from .shell_utils import build_shell_init_command
from .shell_utils import detect_runtime_environment
from .shell_utils import rewrite_windows_null_redirect


DEFAULT_LINE_LIMIT = 2_000
MAX_LINE_LENGTH = 2_000
MAX_BASH_OUTPUT_CHARS = 30_000
MAX_BASH_CAPTURE_CHARS = 10 * 1024 * 1024
MAX_WEB_FETCH_BYTES = 2 * 1024 * 1024
MAX_WEB_FETCH_OUTPUT_CHARS = 30_000
MIN_USEFUL_WEB_FETCH_BODY_CHARS = 40
DEFAULT_WEB_SEARCH_URL = "https://html.duckduckgo.com/html/"
DEFAULT_WEB_SEARCH_RESULTS = 8
MAX_WEB_SEARCH_CALLS_PER_TURN = 8
WEB_SEARCH_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
}
PDF_LARGE_PAGE_THRESHOLD = 10
PDF_MAX_PAGE_RANGE = 20
MAX_CANDIDATE_COUNT = 5
MIN_FUZZY_SCORE = 0.45
ATOMIC_RENAME_RETRIES = 5
ATOMIC_RENAME_BACKOFF_SECONDS = 0.02
IGNORED_DIRECTORY_ENTRIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "wheels",
}
UNSUPPORTED_TEXT_MUTATION_SUFFIXES = {
    ".7z",
    ".avif",
    ".db",
    ".gif",
    ".gz",
    ".ico",
    ".ipynb",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp4",
    ".pdf",
    ".png",
    ".sqlite",
    ".tar",
    ".webp",
    ".zip",
}
SENSITIVE_MUTATION_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".netrc",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}


class MutationErrorCode:
    PATH_POLICY = "path_policy"
    SYMLINK_POLICY = "symlink_policy"
    SENSITIVE_POLICY = "sensitive_policy"
    APPROVAL_REQUIRED = "approval_required"
    GUARDRAIL_BLOCK = "guardrail_block"
    UNSUPPORTED_TARGET = "unsupported_target"
    STALE_SNAPSHOT = "stale_snapshot"
    MATCH_NOT_FOUND = "match_not_found"
    AMBIGUOUS_MATCH = "ambiguous_match"
    EXPECTED_COUNT_MISMATCH = "expected_count_mismatch"
    NO_OP = "no_op"
    PATCH_PARSE = "patch_parse_error"
    PATCH_APPLY = "patch_apply_error"
    ATOMIC_WRITE = "atomic_write_error"
    BACKUP = "backup_error"
    PARTIAL_COMMIT = "partial_commit"
    INVALID_ARGUMENTS = "invalid_arguments"


@dataclass(frozen=True)
class MutationPolicyDecision:
    decision: str = "allow"
    reason: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def result_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {"policyDecision": self.decision}
        if self.reason:
            metadata["policyReason"] = self.reason
        metadata.update(self.metadata)
        return metadata


@dataclass(frozen=True)
class AtomicWriteResult:
    fallback_used: bool = False
    retries: int = 0

    def metadata(self) -> dict[str, object]:
        return {
            "atomicWrite": True,
            "atomicFallbackUsed": self.fallback_used,
            "atomicRenameRetries": self.retries,
        }


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


def _edit_scope(text: str, snippet: FileSnippet | None) -> tuple[int, int]:
    if snippet is None:
        return 0, len(text)
    return _line_scope_offsets(text, snippet.start_line, snippet.end_line)


def _line_scope_offsets(text: str, start_line: int, end_line: int) -> tuple[int, int]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return 0, 0
    start_idx = min(max(start_line - 1, 0), len(lines))
    end_idx = min(max(end_line, start_idx), len(lines))
    start = sum(len(line) for line in lines[:start_idx])
    end = sum(len(line) for line in lines[:end_idx])
    return start, end


@dataclass(frozen=True)
class MatchOccurrence:
    start_offset: int
    end_offset: int
    start_line: int
    end_line: int


@dataclass(frozen=True)
class EditMatchResult:
    matches: list[MatchOccurrence]
    matched_text: str
    matched_via: str


@dataclass(frozen=True)
class ClosestMatch:
    text: str
    start_line: int
    end_line: int
    score: float
    strategy: str


@dataclass(frozen=True)
class TextFileMetadata:
    content: str
    encoding: str
    line_endings: str


@dataclass(frozen=True)
class PatchOperation:
    kind: str
    path: str
    content: str | None = None
    hunks: tuple[tuple[str, str], ...] = ()
    move_to: str | None = None
    expected_occurrences: int | None = None
    replace_all: bool = False
    overwrite: bool = False
    snapshot_id: str | None = None
    expected_hash: str | None = None


@dataclass(frozen=True)
class PlannedPatchOperation:
    operation: PatchOperation
    target: Path
    new_target: Path | None
    old_content: str
    new_content: str | None
    encoding: str
    line_endings: str
    policy: MutationPolicyDecision
    occurrences: int | None = None


@dataclass(frozen=True)
class WebSearchPreparation:
    original_query: str
    resolved_query: str
    dominant_language: str
    language_reason: str
    translated: bool = False

    def metadata(self) -> dict[str, object]:
        return {
            "query": self.resolved_query,
            "originalQuery": self.original_query,
            "resolvedQuery": self.resolved_query,
            "translated": self.translated,
            "dominantLanguage": self.dominant_language,
            "languageReason": self.language_reason,
        }


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True)
class WebSearchProviderFailure:
    provider: str
    error: str
    search_url: str | None = None

    def metadata(self) -> dict[str, str]:
        payload = {"provider": self.provider, "error": self.error}
        if self.search_url:
            payload["searchUrl"] = _mask_url_secrets(self.search_url)
        return payload


@dataclass(frozen=True)
class WebSearchProviderResult:
    provider: str
    search_url: str
    results: list[WebSearchResult]


@dataclass(frozen=True)
class ShellInvocation:
    shell_path: str
    args: list[str]
    runtime_environment: RuntimeEnvironment
    env: dict[str, str] | None = None


def _find_occurrences(text: str, needle: str, scope: tuple[int, int]) -> list[MatchOccurrence]:
    matches: list[MatchOccurrence] = []
    scoped_text = text[scope[0] : scope[1]]
    search_index = 0
    while True:
        found = scoped_text.find(needle, search_index)
        if found == -1:
            return matches
        start_offset = scope[0] + found
        end_offset = start_offset + len(needle)
        matches.append(
            MatchOccurrence(
                start_offset=start_offset,
                end_offset=end_offset,
                start_line=_offset_to_line(text, start_offset),
                end_line=_offset_to_line(text, max(start_offset, end_offset - 1)),
            )
        )
        search_index = found + len(needle)


def _find_edit_occurrences(
    text: str,
    needle: str,
    scope: tuple[int, int],
    line_endings: str,
    *,
    matched_via: str = "exact",
) -> EditMatchResult | None:
    matches = _find_occurrences(text, needle, scope)
    if matches:
        return EditMatchResult(matches=matches, matched_text=needle, matched_via=matched_via)
    normalized_needle = _normalize_line_endings(needle, line_endings)
    if normalized_needle == needle:
        return None
    normalized_matches = _find_occurrences(text, normalized_needle, scope)
    if not normalized_matches:
        return None
    return EditMatchResult(
        matches=normalized_matches,
        matched_text=normalized_needle,
        matched_via=_line_ending_matched_via(matched_via),
    )


def _find_loose_escape_edit_occurrences(
    text: str,
    needle: str,
    scope: tuple[int, int],
    line_endings: str,
) -> list[tuple[MatchOccurrence, float, str, str]]:
    matches = [
        (occurrence, score, matched_text, "loose_escape")
        for occurrence, score, matched_text in _find_loose_escape_occurrences(text, needle, scope)
    ]
    normalized_needle = _normalize_line_endings(needle, line_endings)
    if normalized_needle == needle:
        return matches
    matches.extend(
        (
            occurrence,
            score,
            matched_text,
            "loose_escape_line_endings",
        )
        for occurrence, score, matched_text in _find_loose_escape_occurrences(
            text,
            normalized_needle,
            scope,
        )
    )
    return matches


def _line_ending_matched_via(matched_via: str) -> str:
    return "line_endings" if matched_via == "exact" else f"{matched_via}_line_endings"


def _offset_to_line(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, min(offset, len(text))) + 1


def _build_candidate_metadata(
    file_state: FileState,
    path: Path,
    text: str,
    matches: list[MatchOccurrence],
) -> list[dict[str, object]]:
    candidates = []
    for match in matches[:MAX_CANDIDATE_COUNT]:
        preview = _build_candidate_preview(text, match.start_line, match.end_line)
        snippet = file_state.create_snippet(
            path,
            start_line=match.start_line,
            end_line=match.end_line,
            text=preview,
        )
        candidates.append(
            {
                "snippet_id": snippet.id,
                "start_line": match.start_line,
                "end_line": match.end_line,
                "preview": preview,
            }
        )
    return candidates


def _build_candidate_preview(text: str, start_line: int, end_line: int) -> str:
    lines = text.splitlines()
    selected = lines[start_line - 1 : end_line]
    return "\n".join(
        f"{str(start_line + index).rjust(6)}\t{line}" for index, line in enumerate(selected)
    )


def _build_closest_match_metadata(
    file_state: FileState,
    path: Path,
    closest_match: ClosestMatch,
) -> dict[str, object]:
    preview = _build_candidate_preview(text=closest_match.text, start_line=1, end_line=10)
    if preview:
        preview = _renumber_preview(preview, closest_match.start_line)
    snippet = file_state.create_snippet(
        path,
        start_line=closest_match.start_line,
        end_line=closest_match.end_line,
        text=preview,
    )
    return {
        "snippet_id": snippet.id,
        "start_line": closest_match.start_line,
        "end_line": closest_match.end_line,
        "similarity": round(closest_match.score, 3),
        "strategy": closest_match.strategy,
        "preview": preview,
    }


def _renumber_preview(preview: str, start_line: int) -> str:
    lines = [line.split("\t", 1)[1] if "\t" in line else line for line in preview.splitlines()]
    return "\n".join(
        f"{str(start_line + index).rjust(6)}\t{line}" for index, line in enumerate(lines)
    )


def _format_scope_metadata(
    path: Path,
    snippet: FileSnippet | None,
    scope: tuple[int, int],
    text: str,
) -> dict[str, object]:
    if snippet is not None:
        return {
            **_snippet_metadata(snippet),
            "type": "snippet",
            "snippet_id": snippet.id,
        }
    return {
        "type": "full",
        "filePath": str(path),
        "file_path": str(path),
        "startLine": 1,
        "endLine": _offset_to_line(text, max(scope[0], scope[1] - 1)),
        "start_line": 1,
        "end_line": _offset_to_line(text, max(scope[0], scope[1] - 1)),
        "snippet_id": None,
    }


def _apply_replacements(
    text: str,
    matches: list[MatchOccurrence],
    replacement: str,
    replace_all: bool,
) -> str:
    selected_matches = matches if replace_all else matches[:1]
    result = []
    cursor = 0
    for match in selected_matches:
        result.append(text[cursor : match.start_offset])
        result.append(replacement)
        cursor = match.end_offset
    result.append(text[cursor:])
    return "".join(result)


def _find_loose_escape_occurrences(
    text: str,
    needle: str,
    scope: tuple[int, int],
) -> list[tuple[MatchOccurrence, float, str]]:
    pattern = _build_loose_escape_pattern(needle)
    if pattern is None:
        return []
    scoped_text = text[scope[0] : scope[1]]
    normalized_needle = _normalize_loose_text(needle)
    matches = []
    for regex_match in pattern.finditer(scoped_text):
        start_offset = scope[0] + regex_match.start()
        end_offset = scope[0] + regex_match.end()
        matched_text = regex_match.group(0)
        matches.append(
            (
                MatchOccurrence(
                    start_offset=start_offset,
                    end_offset=end_offset,
                    start_line=_offset_to_line(text, start_offset),
                    end_line=_offset_to_line(text, max(start_offset, end_offset - 1)),
                ),
                _similarity_score(normalized_needle, _normalize_loose_text(matched_text)),
                matched_text,
            )
        )
    return matches


def _build_loose_escape_pattern(source: str) -> re.Pattern[str] | None:
    if not source:
        return None
    pattern = []
    index = 0
    while index < len(source):
        if source[index] == "\\":
            slash_end = index
            while slash_end < len(source) and source[slash_end] == "\\":
                slash_end += 1
            if slash_end < len(source) and source[slash_end] in "\"'`\\":
                pattern.append(r"\\*")
                pattern.append(re.escape(source[slash_end]))
                index = slash_end + 1
                continue
            pattern.append(re.escape(source[index:slash_end]))
            index = slash_end
            continue
        pattern.append(re.escape(source[index]))
        index += 1
    return re.compile("".join(pattern))


def _find_closest_match(
    text: str,
    needle: str,
    scope: tuple[int, int],
) -> ClosestMatch | None:
    loose_matches = _find_loose_escape_occurrences(text, needle, scope)
    best_loose: ClosestMatch | None = None
    for occurrence, score, matched_text in loose_matches:
        candidate = ClosestMatch(
            text=matched_text,
            start_line=occurrence.start_line,
            end_line=occurrence.end_line,
            score=score,
            strategy="loose_escape",
        )
        if best_loose is None or candidate.score > best_loose.score:
            best_loose = candidate
    if best_loose is not None:
        return best_loose

    normalized_target = _normalize_loose_text(needle)
    target_line_count = max(1, len(needle.splitlines()) or 1)
    window_sizes = sorted({max(1, target_line_count - 1), target_line_count, target_line_count + 1})
    start_line = _offset_to_line(text, scope[0])
    end_line = _offset_to_line(text, max(scope[0], scope[1] - 1))
    best_match: ClosestMatch | None = None
    for line in range(start_line, end_line + 1):
        for window_size in window_sizes:
            candidate_end = line + window_size - 1
            if candidate_end > end_line:
                continue
            candidate_text = _slice_lines(text, line, candidate_end)
            score = _similarity_score(normalized_target, _normalize_loose_text(candidate_text))
            if score < MIN_FUZZY_SCORE:
                continue
            candidate = ClosestMatch(
                text=candidate_text,
                start_line=line,
                end_line=candidate_end,
                score=score,
                strategy="fuzzy_window",
            )
            if best_match is None or candidate.score > best_match.score:
                best_match = candidate
    return best_match


def _correct_escaped_strings_with_llm(
    settings: Settings,
    *,
    snippet_text: str,
    old: str,
    new: str,
    matched_text: str,
) -> tuple[str, str] | None:
    if not settings.model.api_key or not settings.model.base_url or not settings.model.name:
        return None
    try:
        content = _edit_correction_chat(settings, snippet_text, old, new, matched_text)
        parsed = _parse_corrected_edit_strings(content)
        if parsed is None:
            return None
        corrected_old, corrected_new = parsed
        if _normalize_loose_text(corrected_old) != _normalize_loose_text(old):
            return None
        if _normalize_loose_text(corrected_new) != _normalize_loose_text(new):
            return None
        if corrected_old == corrected_new:
            return None
        return corrected_old, corrected_new
    except Exception:
        return None


def _edit_correction_chat(
    settings: Settings,
    snippet_text: str,
    old: str,
    new: str,
    matched_text: str,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.model.api_key, base_url=settings.model.base_url)
    response = client.chat.completions.create(
        model=settings.model.name,
        messages=[
            {
                "role": "system",
                "content": (
                    "You correct file-edit strings when the only problem is escaping. "
                    "Return XML only using <response><corrected_old_string>...</corrected_old_string>"
                    "<corrected_new_string>...</corrected_new_string></response>. "
                    "Do not change semantics; only fix quoting or escaping so corrected_old_string "
                    "matches the snippet exactly."
                ),
            },
            {
                "role": "user",
                "content": (
                    "<request>\n"
                    f"  <snippet_text><![CDATA[{snippet_text}]]></snippet_text>\n"
                    f"  <old_string><![CDATA[{old}]]></old_string>\n"
                    f"  <new_string><![CDATA[{new}]]></new_string>\n"
                    f"  <matched_text><![CDATA[{matched_text}]]></matched_text>\n"
                    "</request>\n"
                    "<output_format>\n"
                    "  <response>\n"
                    "    <corrected_old_string><![CDATA[...]]></corrected_old_string>\n"
                    "    <corrected_new_string><![CDATA[...]]></corrected_new_string>\n"
                    "  </response>\n"
                    "</output_format>"
                ),
            },
        ],
    )
    content = response.choices[0].message.content
    return content.strip() if isinstance(content, str) else ""


def _parse_corrected_edit_strings(content: str) -> tuple[str, str] | None:
    normalized = _strip_code_fence(content).strip()
    if not normalized:
        return None
    old_match = re.search(
        r"<corrected_old_string>(?:<!\[CDATA\[([\s\S]*?)\]\]>|([\s\S]*?))</corrected_old_string>",
        normalized,
        flags=re.IGNORECASE,
    )
    new_match = re.search(
        r"<corrected_new_string>(?:<!\[CDATA\[([\s\S]*?)\]\]>|([\s\S]*?))</corrected_new_string>",
        normalized,
        flags=re.IGNORECASE,
    )
    corrected_old = old_match.group(1) or old_match.group(2) if old_match else None
    corrected_new = new_match.group(1) or new_match.group(2) if new_match else None
    if isinstance(corrected_old, str) and isinstance(corrected_new, str):
        return corrected_old, corrected_new
    return None


def _slice_lines(text: str, start_line: int, end_line: int) -> str:
    lines = text.splitlines(keepends=True)
    return "".join(lines[start_line - 1 : end_line])


def _normalize_loose_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\\+(?=[\"'`\\])", "", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()


def _similarity_score(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    left_bigrams = _to_bigrams(left)
    right_bigrams = _to_bigrams(right)
    if not left_bigrams or not right_bigrams:
        return 1.0 if left == right else 0.0
    right_counts: dict[str, int] = {}
    for bigram in right_bigrams:
        right_counts[bigram] = right_counts.get(bigram, 0) + 1
    overlap = 0
    for bigram in left_bigrams:
        count = right_counts.get(bigram, 0)
        if count > 0:
            overlap += 1
            right_counts[bigram] = count - 1
    return (2 * overlap) / (len(left_bigrams) + len(right_bigrams))


def _to_bigrams(value: str) -> list[str]:
    if len(value) < 2:
        return [value]
    return [value[index : index + 2] for index in range(len(value) - 1)]


def _prepare_web_search_query(query: str) -> WebSearchPreparation:
    stripped = " ".join(query.split())
    contains_chinese = _contains_chinese_char(stripped)
    if contains_chinese:
        return WebSearchPreparation(
            original_query=query,
            resolved_query=stripped,
            dominant_language="zh",
            language_reason="The query contains Chinese characters.",
        )
    return WebSearchPreparation(
        original_query=query,
        resolved_query=stripped,
        dominant_language="en",
        language_reason="The query does not contain Chinese characters.",
    )


def _prepare_web_search_query_with_llm(
    query: str,
    settings: Settings,
) -> tuple[WebSearchPreparation, str | None]:
    stripped = " ".join(query.split())
    if not settings.model.api_key or not settings.model.base_url or not settings.model.name:
        return (
            _prepare_web_search_query(query),
            "WebSearch default mode requires a valid LLM configuration.",
        )
    try:
        decision = _decide_search_language_with_llm(stripped, settings)
        contains_chinese = _contains_chinese_char(stripped)
        if decision["dominant_language"] == "en" and contains_chinese:
            translated = _translate_search_query_with_llm(stripped, "English", settings)
            if translated:
                return (
                    WebSearchPreparation(
                        original_query=query,
                        resolved_query=translated,
                        dominant_language="en",
                        language_reason=decision["reason"],
                        translated=True,
                    ),
                    None,
                )
        if decision["dominant_language"] == "zh" and not contains_chinese:
            translated = _translate_search_query_with_llm(stripped, "Chinese", settings)
            if translated:
                return (
                    WebSearchPreparation(
                        original_query=query,
                        resolved_query=translated,
                        dominant_language="zh",
                        language_reason=decision["reason"],
                        translated=True,
                    ),
                    None,
                )
        return (
            WebSearchPreparation(
                original_query=query,
                resolved_query=stripped,
                dominant_language=decision["dominant_language"],
                language_reason=decision["reason"],
            ),
            None,
        )
    except Exception as exc:
        return _prepare_web_search_query(query), str(exc)


def _decide_search_language_with_llm(query: str, settings: Settings) -> dict[str, str]:
    prompt = (
        "Decide whether the topic below has more useful online material in English or Chinese.\n\n"
        "Topic:\n"
        "```text\n"
        f"{query}\n"
        "```\n\n"
        "Return strict JSON:\n"
        '{"dominant_language":"en"|"zh","reason":"one short sentence"}\n'
        "Do not include markdown or any extra text."
    )
    parsed = _parse_json_response(_web_search_chat(settings, prompt))
    dominant_language = parsed.get("dominant_language")
    if not isinstance(dominant_language, str) or dominant_language not in {"en", "zh"}:
        raise ValueError(f"Unexpected dominant language: {dominant_language}")
    reason = parsed.get("reason")
    return {
        "dominant_language": dominant_language,
        "reason": reason if isinstance(reason, str) else "",
    }


def _translate_search_query_with_llm(query: str, target_language: str, settings: Settings) -> str:
    prompt = (
        f"Translate the query text below into {target_language}.\n\n"
        "Requirements:\n"
        "- Preserve product names, library names, API names, versions, and abbreviations when appropriate.\n"
        "- Return only the translated query, without quotes or explanation.\n\n"
        "Query:\n"
        "```text\n"
        f"{query}\n"
        "```"
    )
    return _strip_code_fence(_web_search_chat(settings, prompt)).strip().strip("\"'")


def _web_search_chat(settings: Settings, prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.model.api_key, base_url=settings.model.base_url)
    response = client.chat.completions.create(
        model=settings.model.name,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            text = part.get("text") if isinstance(part, dict) else getattr(part, "text", "")
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts).strip()
    return ""


def _parse_json_response(text: str) -> dict[str, object]:
    cleaned = _strip_code_fence(text).strip()
    try:
        parsed = json_utils.loads(cleaned)
    except json_utils.JSONDecodeError:
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace < 0 or last_brace <= first_brace:
            raise ValueError(f"Failed to parse JSON response: {cleaned or '<empty>'}")
        parsed = json_utils.loads(cleaned[first_brace : last_brace + 1])
    if not isinstance(parsed, dict):
        raise ValueError("JSON response must be an object.")
    return parsed


def _strip_code_fence(text: str) -> str:
    trimmed = text.strip()
    match = re.match(r"^```(?:[\w-]+)?\n([\s\S]*?)\n```$", trimmed)
    return match.group(1) if match else trimmed


def _contains_chinese_char(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _format_web_search_activity_label(query: str) -> str:
    normalized = " ".join(query.split())
    if len(normalized) > 180:
        normalized = normalized[:177] + "..."
    return f"WebSearch: {normalized}"


class _SearchResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[WebSearchResult] = []
        self._current_title: list[str] | None = None
        self._current_url: str = ""
        self._snippet_index: int | None = None
        self._snippet_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        if tag == "a" and "result__a" in classes:
            self._current_title = []
            self._current_url = _decode_search_result_url(values.get("href", ""))
            return
        if "result__snippet" in classes and self.results:
            self._snippet_index = len(self.results) - 1
            self._snippet_chunks = []

    def handle_data(self, data: str) -> None:
        if self._current_title is not None:
            self._current_title.append(data)
        elif self._snippet_index is not None:
            self._snippet_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_title is not None:
            title = " ".join("".join(self._current_title).split())
            if title and self._current_url:
                self.results.append(WebSearchResult(title=title, url=self._current_url))
            self._current_title = None
            self._current_url = ""
            return
        if self._snippet_index is not None and tag in {"a", "div", "td"}:
            snippet = " ".join("".join(self._snippet_chunks).split())
            if snippet:
                result = self.results[self._snippet_index]
                self.results[self._snippet_index] = WebSearchResult(
                    title=result.title,
                    url=result.url,
                    snippet=snippet,
                )
            self._snippet_index = None
            self._snippet_chunks = []


def _decode_search_result_url(href: str) -> str:
    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)
    target = query.get("uddg", [""])[0]
    if target:
        return target
    if parsed.scheme and parsed.netloc:
        return href
    return urllib.parse.urljoin("https://duckduckgo.com", href)


def _parse_search_results(html: str) -> list[WebSearchResult]:
    parser = _SearchResultParser()
    parser.feed(html)
    unique: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    for result in parser.results:
        if result.url in seen_urls:
            continue
        seen_urls.add(result.url)
        unique.append(result)
    return unique


def _format_search_results(query: str, results: list[WebSearchResult]) -> str:
    lines = [f"Web search results for: {query}", ""]
    for index, result in enumerate(results[:DEFAULT_WEB_SEARCH_RESULTS], start=1):
        lines.append(f"{index}. {result.title}")
        lines.append(f"   {result.url}")
        if result.snippet:
            lines.append(f"   {result.snippet}")
        lines.append("")
    return "\n".join(lines).strip()


def _parse_searxng_results(body: str) -> list[WebSearchResult]:
    payload = json_utils.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("SearXNG response must be a JSON object.")
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise ValueError("SearXNG response is missing a results array.")
    results: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(url, str) or not url.strip() or url in seen_urls:
            continue
        content = item.get("content")
        snippet = content if isinstance(content, str) else ""
        seen_urls.add(url)
        results.append(
            WebSearchResult(title=" ".join(title.split()), url=url, snippet=snippet.strip())
        )
    return results


def _build_searxng_search_url(base_url: str, query: str) -> str:
    stripped = base_url.strip()
    parsed = urllib.parse.urlparse(stripped)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("SearXNG URL must be a complete http or https URL.")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("SearXNG URL must use http or https.")
    path = parsed.path.rstrip("/")
    endpoint_path = parsed.path if path.endswith("/search") else f"{path}/search"
    parts = parsed._replace(path=endpoint_path or "/search")
    query_params = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query_params.extend([("q", query), ("format", "json")])
    return urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(query_params)))


def _decode_http_body(body: bytes, *, encoding: str | None, charset: str = "utf-8") -> str:
    normalized_encoding = (encoding or "").split(";", 1)[0].strip().lower()
    if normalized_encoding == "gzip":
        body = gzip.decompress(body)
    elif normalized_encoding == "deflate":
        try:
            body = zlib.decompress(body)
        except zlib.error:
            body = zlib.decompress(body, -zlib.MAX_WBITS)
    elif normalized_encoding not in {"", "identity"}:
        raise ValueError(f"Unsupported content encoding: {encoding}")
    return body.decode(charset, errors="replace")


def _response_header(response: object, name: str) -> str | None:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return None
    value = getter(name)
    return value if isinstance(value, str) else None


def _mask_url_secrets(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    sensitive_keys = {"api_key", "apikey", "key", "token", "access_token", "auth", "authorization"}
    masked = [
        (key, mask_secret(value) if key.lower() in sensitive_keys else value)
        for key, value in query_params
    ]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(masked)))


def _format_provider_failures(failures: list[WebSearchProviderFailure]) -> str:
    return "; ".join(f"{failure.provider}: {failure.error}" for failure in failures)


class _ReadableHtmlParser(HTMLParser):
    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
    SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.description_candidates: dict[str, str] = {}
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized == "meta":
            self._record_meta_description(attrs)
            return
        if normalized in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if normalized == "title":
            self._in_title = True
            return
        if normalized in self.BLOCK_TAGS:
            self._append_newline()

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if normalized == "title":
            self._in_title = False
            return
        if normalized in self.BLOCK_TAGS:
            self._append_newline()

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
            return
        if self._skip_depth:
            return
        self.text_parts.append(text)

    def _append_newline(self) -> None:
        if self.text_parts and self.text_parts[-1] != "\n":
            self.text_parts.append("\n")

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def readable_text(self) -> str:
        raw = " ".join(self.text_parts)
        raw = re.sub(r"[ \t]*\n[ \t]*", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return "\n".join(line.strip() for line in raw.splitlines()).strip()

    @property
    def meta_description(self) -> str:
        for key in ("description", "og:description", "twitter:description"):
            text = self.description_candidates.get(key, "").strip()
            if text:
                return text
        return ""

    def _record_meta_description(self, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value for name, value in attrs if value is not None}
        raw_key = attr_map.get("name") or attr_map.get("property")
        content = attr_map.get("content", "")
        if not raw_key or not content:
            return
        key = raw_key.strip().lower()
        if key not in {"description", "og:description", "twitter:description"}:
            return
        normalized = " ".join(content.split()).strip()
        if normalized and key not in self.description_candidates:
            self.description_candidates[key] = normalized


def _validate_web_fetch_url(url: str) -> tuple[str | None, str | None]:
    stripped = url.strip()
    parsed = urllib.parse.urlparse(stripped)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None, "WebFetch requires a complete http or https URL."
    return stripped, None


def _charset_from_content_type(content_type: str) -> str:
    match = re.search(r"charset=([^\s;]+)", content_type, flags=re.IGNORECASE)
    return match.group(1).strip("\"'") if match else "utf-8"


def _is_html_response(content_type: str, text: str) -> bool:
    lowered = content_type.lower()
    if "html" in lowered:
        return True
    prefix = text[:500].lower()
    return "<html" in prefix or "<!doctype html" in prefix


def _extract_readable_html(html: str) -> tuple[str, str, str]:
    parser = _ReadableHtmlParser()
    parser.feed(html)
    parser.close()
    return parser.title, parser.readable_text, parser.meta_description


def _select_web_fetch_html_text(readable_text: str, metadata_text: str) -> str:
    stripped = readable_text.strip()
    if stripped and _is_useful_web_fetch_body_text(stripped):
        return stripped
    return metadata_text.strip() or stripped


def _is_useful_web_fetch_body_text(text: str) -> bool:
    normalized = " ".join(text.split()).strip().lower()
    if len(normalized) >= MIN_USEFUL_WEB_FETCH_BODY_CHARS:
        return True
    return normalized not in {
        "",
        "loading",
        "loading...",
        "please enable javascript",
        "you need to enable javascript to run this app.",
    }


def _format_web_fetch_output(
    *,
    url: str,
    final_url: str,
    content_type: str,
    title: str,
    text: str,
    bytes_truncated: bool,
) -> str:
    lines = [
        f"URL: {url}",
        f"Final URL: {final_url}",
    ]
    if title:
        lines.append(f"Title: {title}")
    if content_type:
        lines.append(f"Content-Type: {content_type}")
    if bytes_truncated:
        lines.append(f"Note: response body was truncated at {MAX_WEB_FETCH_BYTES:,} bytes.")
    lines.append("")
    lines.append(text.strip() if text.strip() else "[No readable text extracted.]")
    return "\n".join(lines).strip()


@dataclass
class ToolRuntime:
    cwd: Path
    settings: Settings
    platform_name: str = field(default_factory=lambda: sys.platform)
    file_state: FileState = field(default_factory=FileState)
    running_processes: dict[str, dict[str, str]] = field(default_factory=dict)
    web_search_calls: int = 0
    todo_items: list[TodoItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        raw_items = [
            item.to_dict() if isinstance(item, TodoItem) else item for item in self.todo_items
        ]
        normalized, error = normalize_todo_items(raw_items)
        if error is None and normalized is not None:
            self.todo_items = normalized

    def _read_file_result(
        self,
        path: str,
        start_line: int = 1,
        limit: int | None = None,
        pages: str | None = None,
        *,
        name: str = "read_file",
    ) -> str:
        target, error = _resolve_read_target(self.cwd, path)
        if error is not None:
            return ToolResult.error_result(name, error).to_json()
        if target is None or not target.exists():
            return ToolResult.error_result(name, f"File does not exist: {path}").to_json()
        if target.is_dir():
            entries, visible_count, ignored_count = _format_directory_entries(target, self.cwd)
            return ToolResult.ok_result(
                name,
                entries,
                metadata={
                    "path": str(target),
                    "kind": "directory",
                    "entryCount": len(list(target.iterdir())),
                    "visibleEntryCount": visible_count,
                    "ignoredEntryCount": ignored_count,
                },
            ).to_json()

        if target.suffix.lower() == ".ipynb":
            output, error = _format_notebook(target)
            if error is not None:
                return ToolResult.error_result(
                    name, error, metadata={"path": str(target)}
                ).to_json()
            return ToolResult.ok_result(
                name,
                output,
                metadata={
                    "path": str(target),
                    "kind": "notebook",
                    "trackedForWrite": False,
                },
            ).to_json()

        if target.suffix.lower() == ".pdf":
            return _read_pdf(target, pages, name=name)

        mime = _image_mime_type(target.suffix.lower())
        if mime is not None:
            data = target.read_bytes()
            return ToolResult(
                ok=True,
                name=name,
                output="File loaded.",
                metadata={"path": str(target), "mime": mime, "bytes": len(data)},
                followUpMessages=[_build_image_follow_up_message(target, mime, data)],
            ).to_json()

        text_metadata = _read_text_metadata(target)
        text = text_metadata.content
        lines = text.splitlines()
        start = max(start_line, 1) - 1
        effective_limit = limit if limit and limit > 0 else DEFAULT_LINE_LIMIT
        selected = lines[start : start + effective_limit]
        formatted_lines = [_truncate_line(line) for line in selected]
        truncated = start + len(selected) < len(lines) or any(
            len(line) > MAX_LINE_LENGTH for line in selected
        )
        full_file_read = start == 0 and not truncated
        numbered = "\n".join(
            f"{idx + start + 1}: {line}" for idx, line in enumerate(formatted_lines)
        )
        if full_file_read:
            snapshot = self.file_state.mark_read(
                target,
                encoding=text_metadata.encoding,
                line_endings=text_metadata.line_endings,
            )
        else:
            snapshot = None
        snippet_metadata = None
        if not full_file_read and selected:
            snippet = self.file_state.create_snippet(
                target,
                start_line=start + 1,
                end_line=start + len(selected),
                text="\n".join(selected),
            )
            snapshot = self.file_state.mark_read(
                target,
                full=False,
                encoding=text_metadata.encoding,
                line_endings=text_metadata.line_endings,
            )
            snippet_metadata = _snippet_metadata(snippet)
        metadata: dict[str, object] = {
            "path": str(target),
            "kind": "file",
            "startLine": start + 1,
            "lineCount": len(selected),
            "lineLimit": effective_limit,
            "totalLines": len(lines),
            "truncated": truncated,
            "trackedForWrite": full_file_read,
            "encoding": text_metadata.encoding,
            "line_endings": text_metadata.line_endings,
        }
        if snapshot is not None:
            metadata.update(
                {
                    "snapshot_id": snapshot.id,
                    "content_hash": snapshot.content_hash,
                    "mtime_ns": snapshot.mtime_ns,
                    "size": snapshot.size,
                }
            )
        if snippet_metadata is not None:
            metadata["snippet"] = snippet_metadata
        return ToolResult.ok_result(
            name,
            numbered,
            metadata=metadata,
        ).to_json()

    def read_file(
        self,
        path: str,
        start_line: int = 1,
        limit: int | None = None,
        pages: str | None = None,
    ) -> str:
        return self._read_file_result(path, start_line=start_line, limit=limit, pages=pages)

    def write(
        self,
        path: str,
        content: object,
        *,
        overwrite: bool = True,
        snapshot_id: str | None = None,
        expected_hash: str | None = None,
        name: str = "write",
    ) -> str:
        target, error, metadata = _resolve_mutation_target(self.cwd, path)
        if error is not None or target is None:
            return ToolResult.error_result(name, error or "Invalid file path.", metadata=metadata).to_json()
        if target.exists():
            if not overwrite:
                return ToolResult.error_result(
                    name,
                    "File already exists; explicit overwrite intent is required.",
                    metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS, path=target),
                ).to_json()
            snapshot = self.file_state.get_snapshot(target)
            if snapshot_id is not None and (snapshot is None or snapshot.id != snapshot_id):
                return ToolResult.error_result(
                    name,
                    "Snapshot id does not match the current managed snapshot.",
                    metadata=_mutation_error_metadata(
                        MutationErrorCode.STALE_SNAPSHOT,
                        path=target,
                        expectedSnapshotId=snapshot_id,
                        actualSnapshotId=snapshot.id if snapshot else None,
                    ),
                ).to_json()
            if expected_hash is not None and (snapshot is None or snapshot.content_hash != expected_hash):
                return ToolResult.error_result(
                    name,
                    "Content hash does not match the current managed snapshot.",
                    metadata=_mutation_error_metadata(
                        MutationErrorCode.STALE_SNAPSHOT,
                        path=target,
                        expectedHash=expected_hash,
                        actualHash=snapshot.content_hash if snapshot else None,
                    ),
                ).to_json()
        policy = _mutation_policy_decision(self.cwd, target)
        policy_error = _policy_error_result(name, policy)
        if policy_error is not None:
            return policy_error
        unsupported_reason = _unsupported_text_mutation_reason(target)
        if unsupported_reason is not None:
            return ToolResult.error_result(
                name,
                unsupported_reason,
                metadata=_mutation_error_metadata(MutationErrorCode.UNSUPPORTED_TARGET, path=target),
            ).to_json()
        ok, error = self.file_state.check_writable(target, require_read=True)
        if not ok:
            metadata = _stale_write_recovery_metadata(target, error)
            return ToolResult.error_result(
                name,
                error or "File is not writable.",
                metadata={
                    **_mutation_error_metadata(
                        MutationErrorCode.STALE_SNAPSHOT,
                        path=target,
                        recovery="Re-read the file before retrying.",
                    ),
                    **metadata,
                },
            ).to_json()
        text_content, repair_metadata, content_error = _coerce_write_content(target, content)
        if content_error is not None:
            return ToolResult.error_result(
                name,
                content_error,
                metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS, path=target),
            ).to_json()
        existing_metadata = _read_text_metadata(target) if target.exists() else None
        old_content = existing_metadata.content if existing_metadata is not None else ""
        encoding = (
            existing_metadata.encoding
            if existing_metadata is not None
            else _default_new_text_encoding()
        )
        line_endings = (
            existing_metadata.line_endings
            if existing_metadata is not None
            else _new_file_line_endings(target, text_content)
        )
        normalized_content = _normalize_line_endings(text_content, line_endings)
        if old_content == normalized_content and target.exists():
            return ToolResult.error_result(
                name,
                "Mutation would not change file content.",
                metadata=_mutation_error_metadata(MutationErrorCode.NO_OP, path=target),
            ).to_json()
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_result = _atomic_write_text_with_encoding(
            target,
            normalized_content,
            encoding,
            platform_name=self.platform_name,
        )
        snapshot = self.file_state.mark_written(
            target,
            encoding=encoding,
            line_endings=line_endings,
        )
        diff = _unified_diff(old_content, normalized_content, path=str(target))
        return ToolResult.ok_result(
            name,
            f"Wrote {target}",
            metadata={
                "path": str(target),
                "encoding": encoding,
                "line_endings": line_endings,
                "changedFiles": [str(target)],
                "policyDecision": policy.decision,
                **policy.result_metadata(),
                **atomic_result.metadata(),
                **repair_metadata,
                "diff": diff,
                "diff_preview": diff,
                **(
                    {
                        "snapshot_id": snapshot.id,
                        "content_hash": snapshot.content_hash,
                    }
                    if snapshot is not None
                    else {}
                ),
            },
        ).to_json()

    def write_file(
        self,
        path: str,
        content: object,
        *,
        overwrite: bool = False,
        snapshot_id: str | None = None,
        expected_hash: str | None = None,
    ) -> str:
        target, _, _ = _resolve_mutation_target(self.cwd, path)
        if target is not None and target.exists() and not overwrite:
            return ToolResult.error_result(
                "write_file",
                "Existing file replacement requires overwrite=true and a fresh snapshot id or content hash.",
                metadata=_mutation_error_metadata(
                    MutationErrorCode.INVALID_ARGUMENTS,
                    path=target,
                    recovery="Read the file first, then retry write_file with overwrite intent and snapshot metadata.",
                ),
            ).to_json()
        if target is not None and target.exists() and not snapshot_id and not expected_hash:
            return ToolResult.error_result(
                "write_file",
                "Existing file replacement requires a snapshot_id or expected_hash.",
                metadata=_mutation_error_metadata(
                    MutationErrorCode.STALE_SNAPSHOT,
                    path=target,
                    recovery="Read the file first and pass the returned snapshot_id or content_hash.",
                ),
            ).to_json()
        return self.write(
            path,
            content,
            overwrite=overwrite,
            snapshot_id=snapshot_id,
            expected_hash=expected_hash,
            name="write_file",
        )

    def edit(
        self,
        path: str | None,
        old: str,
        new: str,
        replace_all: bool = False,
        snippet_id: str | None = None,
        auto_read_if_missing_snapshot: bool = False,
        expected_occurrences: int | None = None,
        *,
        name: str = "edit",
    ) -> str:
        snippet_id = _normalize_optional_tool_identifier(snippet_id)
        path = _normalize_optional_tool_identifier(path)
        if not old:
            return ToolResult.error_result(
                name,
                "old text must not be empty.",
                metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS),
            ).to_json()
        snippet = None
        inferred_snapshot_id = None
        if snippet_id:
            snippet = self.file_state.get_snippet(snippet_id)
            if snippet is None:
                snapshot_path = self.file_state.get_snapshot_path(snippet_id)
                if snapshot_path is not None:
                    target = snapshot_path
                    inferred_snapshot_id = snippet_id
                    snippet_id = None
                elif path:
                    snippet_id = None
                else:
                    return ToolResult.error_result(
                        name,
                        f"Unknown snippet_id: {snippet_id}. Pass file_path for a full-file exact edit, or pass a snippet_id returned from a partial read_file result.",
                        metadata=_mutation_error_metadata(
                            MutationErrorCode.INVALID_ARGUMENTS,
                            recovery="Use file_path for ordinary exact edits. snapshot_id is only for write_file replacement.",
                        ),
                    ).to_json()
            if snippet is None and snippet_id is None and path:
                target, error, metadata = _resolve_mutation_target(self.cwd, path)
                if error is not None or target is None:
                    return ToolResult.error_result(name, error or "Invalid file path.", metadata=metadata).to_json()
            elif snippet is None:
                pass
            else:
                target = snippet.path
                if path:
                    requested_target, error, metadata = _resolve_mutation_target(self.cwd, path)
                    if error is not None or requested_target is None:
                        return ToolResult.error_result(
                            name, error or "Invalid file path.", metadata=metadata
                        ).to_json()
                    if requested_target != target:
                        return ToolResult.error_result(
                            name,
                            "snippet_id does not belong to the provided file_path.",
                            metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS),
                        ).to_json()
        if snippet is None and not snippet_id and inferred_snapshot_id is None:
            if not path:
                return ToolResult.error_result(
                    name,
                    "file_path is required unless snippet_id is provided.",
                    metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS),
                ).to_json()
            target, error, metadata = _resolve_mutation_target(self.cwd, path)
            if error is not None or target is None:
                return ToolResult.error_result(name, error or "Invalid file path.", metadata=metadata).to_json()
        elif snippet is not None:
            target = snippet.path
            if path:
                requested_target, error, metadata = _resolve_mutation_target(self.cwd, path)
                if error is not None or requested_target is None:
                    return ToolResult.error_result(name, error or "Invalid file path.", metadata=metadata).to_json()
                if requested_target != target:
                    return ToolResult.error_result(
                        name,
                        "snippet_id does not belong to the provided file_path.",
                        metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS),
                    ).to_json()
        if not target.exists():
            return ToolResult.error_result(
                name,
                f"File does not exist: {target}",
                metadata=_mutation_error_metadata(MutationErrorCode.UNSUPPORTED_TARGET, path=target),
            ).to_json()
        policy = _mutation_policy_decision(self.cwd, target)
        policy_error = _policy_error_result(name, policy)
        if policy_error is not None:
            return policy_error
        unsupported_reason = _unsupported_text_mutation_reason(target)
        if unsupported_reason is not None:
            return ToolResult.error_result(
                name,
                unsupported_reason,
                metadata=_mutation_error_metadata(MutationErrorCode.UNSUPPORTED_TARGET, path=target),
            ).to_json()
        auto_read_before_edit = False
        auto_read_reason: str | None = None
        if (
            auto_read_if_missing_snapshot
            and snippet is None
        ):
            snapshot_status = self.file_state.snapshot_status(target)
            if snapshot_status in {"missing", "partial"}:
                text_metadata = _read_text_metadata(target)
                self.file_state.mark_read(
                    target,
                    encoding=text_metadata.encoding,
                    line_endings=text_metadata.line_endings,
                )
                auto_read_before_edit = True
                auto_read_reason = snapshot_status
        ok, error = self.file_state.check_writable(
            target,
            require_read=True,
            allow_partial=snippet is not None,
        )
        if not ok:
            return ToolResult.error_result(
                name,
                error or "File is not writable.",
                metadata=_mutation_error_metadata(
                    MutationErrorCode.STALE_SNAPSHOT,
                    path=target,
                    recovery="Re-read the file before retrying.",
                ),
            ).to_json()
        text_metadata = _read_text_metadata(target)
        text = text_metadata.content
        line_endings = text_metadata.line_endings
        scope = _edit_scope(text, snippet)
        fallback_from_snippet_id: str | None = None
        match_result = _find_edit_occurrences(text, old, scope, line_endings)
        matches = match_result.matches if match_result is not None else []
        matched_via = match_result.matched_via if match_result is not None else "exact"
        replacement_new = new
        if not matches:
            loose_matches = _find_loose_escape_edit_occurrences(text, old, scope, line_endings)
            if len(loose_matches) == 1 and loose_matches[0][1] == 1.0:
                corrected = _correct_escaped_strings_with_llm(
                    self.settings,
                    snippet_text=text[scope[0] : scope[1]],
                    old=old,
                    new=new,
                    matched_text=loose_matches[0][2],
                )
                if corrected is not None:
                    corrected_old, corrected_new = corrected
                    corrected_match_result = _find_edit_occurrences(
                        text,
                        corrected_old,
                        scope,
                        line_endings,
                        matched_via="llm_escape_correction",
                    )
                    if corrected_match_result is not None:
                        matches = corrected_match_result.matches
                        replacement_new = corrected_new
                        matched_via = corrected_match_result.matched_via
                if not matches:
                    matches = [loose_matches[0][0]]
                    matched_via = loose_matches[0][3]
        if not matches and snippet is not None and path:
            full_scope = (0, len(text))
            match_result = _find_edit_occurrences(
                text,
                old,
                full_scope,
                line_endings,
                matched_via="full_file_after_snippet_miss",
            )
            if match_result is not None:
                matches = match_result.matches
                matched_via = match_result.matched_via
                scope = full_scope
                fallback_from_snippet_id = snippet.id
                snippet = None
                self.file_state.mark_read(
                    target,
                    encoding=text_metadata.encoding,
                    line_endings=text_metadata.line_endings,
                )
        if not matches:
            closest_match = _find_closest_match(text, old, scope)
            metadata = {"scope": _format_scope_metadata(target, snippet, scope, text)}
            if closest_match is not None:
                metadata["closest_match"] = _build_closest_match_metadata(
                    self.file_state,
                    target,
                    closest_match,
                )
            return ToolResult.error_result(
                name,
                "old_string not found in file.",
                metadata={
                    **_mutation_error_metadata(MutationErrorCode.MATCH_NOT_FOUND, path=target),
                    **metadata,
                },
            ).to_json()
        occurrences = len(matches)
        if expected_occurrences is not None and occurrences != expected_occurrences:
            return ToolResult.error_result(
                name,
                "old_string match count did not equal expected_occurrences.",
                metadata=_mutation_error_metadata(
                    MutationErrorCode.EXPECTED_COUNT_MISMATCH,
                    path=target,
                    expectedOccurrences=expected_occurrences,
                    actualOccurrences=occurrences,
                    scope=_format_scope_metadata(target, snippet, scope, text),
                ),
            ).to_json()
        if occurrences > 1 and not replace_all:
            return ToolResult.error_result(
                name,
                "old_string is not unique; use snippet_id, replace_all, or provide more context.",
                metadata={
                    **_mutation_error_metadata(MutationErrorCode.AMBIGUOUS_MATCH, path=target),
                    "occurrences": occurrences,
                    "match_count": occurrences,
                    "scope": _format_scope_metadata(target, snippet, scope, text),
                    "candidates": _build_candidate_metadata(
                        self.file_state,
                        target,
                        text,
                        matches,
                    ),
                },
            ).to_json()
        normalized_new = _normalize_line_endings(replacement_new, line_endings)
        updated = _apply_replacements(text, matches, normalized_new, replace_all)
        if updated == text:
            return ToolResult.error_result(
                name,
                "Mutation would not change file content.",
                metadata=_mutation_error_metadata(MutationErrorCode.NO_OP, path=target),
            ).to_json()
        atomic_result = _atomic_write_text_with_encoding(
            target,
            updated,
            text_metadata.encoding,
            platform_name=self.platform_name,
        )
        snapshot = self.file_state.mark_written(
            target,
            encoding=text_metadata.encoding,
            line_endings=line_endings,
        )
        diff = _unified_diff(text, updated, path=str(target))
        metadata: dict[str, object] = {
            "path": str(target),
            "file_path": str(target),
            "occurrences": occurrences if replace_all else 1,
            "matched_via": matched_via,
            "encoding": text_metadata.encoding,
            "line_endings": line_endings,
            "read_scope_type": "snippet" if snippet is not None else "full",
            "changedFiles": [str(target)],
            "policyDecision": policy.decision,
            **policy.result_metadata(),
            **atomic_result.metadata(),
            "diff": diff,
            "diff_preview": diff,
        }
        if snapshot is not None:
            metadata["snapshot_id"] = snapshot.id
            metadata["content_hash"] = snapshot.content_hash
        if auto_read_before_edit:
            metadata["autoReadBeforeEdit"] = True
        if auto_read_reason is not None:
            metadata["autoReadReason"] = auto_read_reason
        if inferred_snapshot_id is not None:
            metadata["inferredFromSnapshotId"] = inferred_snapshot_id
        if fallback_from_snippet_id is not None:
            metadata["fallbackFromSnippetId"] = fallback_from_snippet_id
        if snippet is not None:
            metadata["scope"] = _format_scope_metadata(target, snippet, scope, text)
        return ToolResult.ok_result(name, f"Edited {target}", metadata=metadata).to_json()

    def edit_text(
        self,
        path: str | None,
        old: str,
        new: str,
        replace_all: bool = False,
        snippet_id: str | None = None,
        expected_occurrences: int | None = None,
        *,
        auto_read_if_missing_snapshot: bool = True,
        name: str = "edit_text",
    ) -> str:
        return self.edit(
            path,
            old,
            new,
            replace_all=replace_all,
            snippet_id=snippet_id,
            auto_read_if_missing_snapshot=auto_read_if_missing_snapshot,
            expected_occurrences=expected_occurrences,
            name=name,
        )

    def apply_patch(self, operations: object) -> str:
        name = "apply_patch"
        parsed_operations, parse_error, parse_metadata = _parse_structured_patch_operations(operations)
        if parse_error is not None:
            return ToolResult.error_result(
                name,
                parse_error,
                metadata={
                    **_mutation_error_metadata(MutationErrorCode.PATCH_PARSE),
                    **parse_metadata,
                },
            ).to_json()
        if not parsed_operations:
            return ToolResult.error_result(
                name,
                "Structured patch does not contain any operations.",
                metadata=_mutation_error_metadata(MutationErrorCode.PATCH_PARSE),
            ).to_json()

        planned: list[PlannedPatchOperation] = []
        failures: list[dict[str, object]] = []
        staged_content: dict[Path, TextFileMetadata | None] = {}
        for index, operation in enumerate(parsed_operations):
            plan, error, metadata = self._plan_patch_operation(
                operation,
                staged_content=staged_content,
            )
            if error is not None:
                failures.append(
                    {
                        "index": index,
                        "path": operation.path,
                        "operation": operation.kind,
                        "error": error,
                        **metadata,
                    }
                )
            elif plan is not None:
                planned.append(plan)
                destination = plan.new_target or plan.target
                if plan.new_content is None:
                    staged_content[plan.target.resolve()] = None
                    staged_content[destination.resolve()] = None
                else:
                    staged_content[destination.resolve()] = TextFileMetadata(
                        content=plan.new_content,
                        encoding=plan.encoding,
                        line_endings=plan.line_endings,
                    )
        if failures:
            return ToolResult.error_result(
                name,
                "Structured patch preflight failed; no file changes were committed.",
                metadata=_mutation_error_metadata(
                    MutationErrorCode.PATCH_APPLY,
                    failures=failures,
                    preflightFailed=True,
                    operationCount=len(parsed_operations),
                ),
            ).to_json()

        committed: list[dict[str, object]] = []
        diffs: list[str] = []
        changed_files: list[str] = []
        try:
            for plan in planned:
                operation = plan.operation
                target = plan.target
                if operation.kind == "delete_file":
                    backup_metadata = _create_mutation_backup(self.cwd, target)
                    target.unlink()
                    self.file_state.discard_snapshot(target)
                    committed.append(
                        {
                            "operation": operation.kind,
                            "path": str(target),
                            **backup_metadata,
                        }
                    )
                    changed_files.append(str(target))
                    diffs.append(_unified_diff(plan.old_content, "", path=str(target)))
                    continue
                if operation.kind == "move_file" and plan.new_target is not None:
                    backup_metadata = _create_mutation_backup(self.cwd, target)
                    plan.new_target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(target, plan.new_target)
                    self.file_state.discard_snapshot(target)
                    snapshot = self.file_state.mark_written(
                        plan.new_target,
                        encoding=plan.encoding,
                        line_endings=plan.line_endings,
                    )
                    committed.append(
                        {
                            "operation": operation.kind,
                            "path": str(target),
                            "destination": str(plan.new_target),
                            "snapshot_id": snapshot.id if snapshot else None,
                            **backup_metadata,
                        }
                    )
                    changed_files.extend([str(target), str(plan.new_target)])
                    diffs.append(_unified_diff(plan.old_content, plan.new_content or "", path=str(plan.new_target)))
                    continue
                if plan.new_content is None:
                    continue
                destination = plan.new_target or target
                atomic_result = _atomic_write_text_with_encoding(
                    destination,
                    plan.new_content,
                    plan.encoding,
                    platform_name=self.platform_name,
                )
                if destination != target and target.exists():
                    target.unlink()
                    self.file_state.discard_snapshot(target)
                snapshot = self.file_state.mark_written(
                    destination,
                    encoding=plan.encoding,
                    line_endings=plan.line_endings,
                )
                committed.append(
                    {
                        "operation": operation.kind,
                        "path": str(target),
                        "destination": str(destination),
                        "snapshot_id": snapshot.id if snapshot else None,
                        **(
                            {"actualOccurrences": plan.occurrences}
                            if plan.occurrences is not None
                            else {}
                        ),
                        **atomic_result.metadata(),
                    }
                )
                changed_files.append(str(destination))
                diffs.append(_unified_diff(plan.old_content, plan.new_content, path=str(destination)))
        except OSError as exc:
            return ToolResult.error_result(
                name,
                f"Patch commit failed after partial changes: {exc}",
                metadata=_mutation_error_metadata(
                    MutationErrorCode.PARTIAL_COMMIT,
                    committedOperations=committed,
                    failedError=str(exc),
                ),
            ).to_json()

        diff_items = [item for item in diffs if item]
        diff = "\n".join(diff_items)
        unique_changed_files = list(dict.fromkeys(changed_files))
        return ToolResult.ok_result(
            name,
            f"Applied patch to {len(unique_changed_files)} file(s).",
            metadata={
                "path": _patch_changed_path_summary(unique_changed_files),
                "changedFiles": unique_changed_files,
                "operationCount": len(parsed_operations),
                "changedFileCount": len(unique_changed_files),
                "operations": committed,
                "policyDecision": "allow",
                "diff": diff,
                "diff_preview": diff,
            },
        ).to_json()

    def _plan_patch_operation(
        self,
        operation: PatchOperation,
        *,
        staged_content: dict[Path, TextFileMetadata | None] | None = None,
    ) -> tuple[PlannedPatchOperation | None, str | None, dict[str, object]]:
        target, error, metadata = _resolve_mutation_target(
            self.cwd,
            _normalize_patch_operation_path(
                self.cwd,
                operation.path,
                expect_existing=operation.kind != "create_file",
            ),
        )
        if error is not None or target is None:
            return None, error or "Invalid file path.", metadata
        target_key = target.resolve()
        has_staged_target = staged_content is not None and target_key in staged_content
        staged_metadata = staged_content[target_key] if has_staged_target and staged_content is not None else None
        new_target = None
        if operation.move_to is not None:
            new_target, error, metadata = _resolve_mutation_target(
                self.cwd,
                _normalize_patch_operation_path(
                    self.cwd,
                    operation.move_to,
                    expect_existing=False,
                ),
            )
            if error is not None or new_target is None:
                return None, error or "Invalid move destination.", metadata
        policy = _mutation_policy_decision(self.cwd, target)
        policy_error = _policy_error_result("apply_patch", policy)
        if policy_error is not None:
            parsed = json_utils.loads(policy_error)
            return None, parsed.get("error") or "Mutation rejected by policy.", parsed.get("metadata", {})
        if new_target is not None:
            destination_policy = _mutation_policy_decision(self.cwd, new_target)
            policy_error = _policy_error_result("apply_patch", destination_policy)
            if policy_error is not None:
                parsed = json_utils.loads(policy_error)
                return None, parsed.get("error") or "Move destination rejected by policy.", parsed.get("metadata", {})
        if operation.kind == "create_file":
            if target.exists() or staged_metadata is not None:
                return (
                    None,
                    "create_file target already exists.",
                    _mutation_error_metadata(MutationErrorCode.PATCH_APPLY, path=target),
                )
            unsupported_reason = _unsupported_text_mutation_reason(target)
            if unsupported_reason is not None:
                return (
                    None,
                    unsupported_reason,
                    _mutation_error_metadata(MutationErrorCode.UNSUPPORTED_TARGET, path=target),
                )
            content = operation.content or ""
            line_endings = _new_file_line_endings(target, content)
            new_content = _normalize_line_endings(content, line_endings)
            return (
                PlannedPatchOperation(
                    operation=operation,
                    target=target,
                    new_target=None,
                    old_content="",
                    new_content=new_content,
                    encoding=_default_new_text_encoding(),
                    line_endings=line_endings,
                    policy=policy,
                ),
                None,
                {},
            )
        if not target.exists():
            if staged_metadata is None:
                return (
                    None,
                    f"Patch target does not exist: {target}",
                    _mutation_error_metadata(MutationErrorCode.PATCH_APPLY, path=target),
                )
        unsupported_reason = _unsupported_text_mutation_reason(target)
        if unsupported_reason is not None:
            return (
                None,
                unsupported_reason,
                _mutation_error_metadata(MutationErrorCode.UNSUPPORTED_TARGET, path=target),
            )
        if staged_metadata is None:
            ok, stale_error = self.file_state.check_writable(target, require_read=False)
            if not ok:
                return (
                    None,
                    stale_error or "Patch target is stale.",
                    _mutation_error_metadata(
                        MutationErrorCode.STALE_SNAPSHOT,
                        path=target,
                        recovery="Re-read the file before retrying.",
                    ),
                )
            metadata = _read_text_metadata(target)
        else:
            metadata = staged_metadata
        if operation.kind == "delete_file":
            return (
                PlannedPatchOperation(
                    operation=operation,
                    target=target,
                    new_target=None,
                    old_content=metadata.content,
                    new_content=None,
                    encoding=metadata.encoding,
                    line_endings=metadata.line_endings,
                    policy=policy,
                ),
                None,
                {},
            )
        if operation.kind == "move_file":
            if new_target is None:
                return (
                    None,
                    "move_file requires destination_path.",
                    _mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS, path=target),
                )
            if new_target.exists():
                return (
                    None,
                    "move_file destination already exists.",
                    _mutation_error_metadata(MutationErrorCode.PATCH_APPLY, path=new_target),
                )
            return (
                PlannedPatchOperation(
                    operation=operation,
                    target=target,
                    new_target=new_target,
                    old_content=metadata.content,
                    new_content=metadata.content,
                    encoding=metadata.encoding,
                    line_endings=metadata.line_endings,
                    policy=policy,
                ),
                None,
                {},
            )
        if operation.kind == "replace_file":
            if not operation.overwrite:
                return (
                    None,
                    "replace_file requires overwrite=true.",
                    _mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS, path=target),
                )
            if not operation.snapshot_id and not operation.expected_hash:
                return (
                    None,
                    "replace_file requires snapshot_id or expected_hash.",
                    _mutation_error_metadata(
                        MutationErrorCode.STALE_SNAPSHOT,
                        path=target,
                        recovery="Read the file first and pass the returned snapshot_id or content_hash.",
                    ),
                )
            snapshot = self.file_state.get_snapshot(target)
            if operation.snapshot_id is not None and (snapshot is None or snapshot.id != operation.snapshot_id):
                return (
                    None,
                    "Snapshot id does not match the current managed snapshot.",
                    _mutation_error_metadata(
                        MutationErrorCode.STALE_SNAPSHOT,
                        path=target,
                        expectedSnapshotId=operation.snapshot_id,
                        actualSnapshotId=snapshot.id if snapshot else None,
                    ),
                )
            if operation.expected_hash is not None and (
                snapshot is None or snapshot.content_hash != operation.expected_hash
            ):
                return (
                    None,
                    "Content hash does not match the current managed snapshot.",
                    _mutation_error_metadata(
                        MutationErrorCode.STALE_SNAPSHOT,
                        path=target,
                        expectedHash=operation.expected_hash,
                        actualHash=snapshot.content_hash if snapshot else None,
                    ),
                )
            ok, stale_error = self.file_state.check_writable(target, require_read=True)
            if not ok:
                return (
                    None,
                    stale_error or "Patch target is stale.",
                    _mutation_error_metadata(
                        MutationErrorCode.STALE_SNAPSHOT,
                        path=target,
                        recovery="Re-read the file before retrying.",
                    ),
                )
            new_content = _normalize_line_endings(operation.content or "", metadata.line_endings)
            if new_content == metadata.content:
                return (
                    None,
                    "Patch would not change file content.",
                    _mutation_error_metadata(MutationErrorCode.NO_OP, path=target),
                )
            return (
                PlannedPatchOperation(
                    operation=operation,
                    target=target,
                    new_target=None,
                    old_content=metadata.content,
                    new_content=new_content,
                    encoding=metadata.encoding,
                    line_endings=metadata.line_endings,
                    policy=policy,
                ),
                None,
                {},
            )
        new_content = metadata.content
        total_occurrences = 0
        for old_block, new_block in operation.hunks:
            normalized_old = _normalize_line_endings(old_block, metadata.line_endings)
            normalized_new = _normalize_line_endings(new_block, metadata.line_endings)
            matched_old, matched_new, count = _select_patch_replacement_variant(
                new_content,
                normalized_old,
                normalized_new,
            )
            if count == 0:
                closest = _find_closest_match(new_content, normalized_old, (0, len(new_content)))
                closest_metadata = (
                    {"closest_match": _build_closest_match_metadata(self.file_state, target, closest)}
                    if closest is not None
                    else {}
                )
                return (
                    None,
                    "Patch context not found in file.",
                    {
                        **_mutation_error_metadata(MutationErrorCode.MATCH_NOT_FOUND, path=target),
                        **closest_metadata,
                    },
                )
            if (
                operation.expected_occurrences is not None
                and count != operation.expected_occurrences
            ):
                return (
                    None,
                    "Patch match count did not equal expected_occurrences.",
                    _mutation_error_metadata(
                        MutationErrorCode.EXPECTED_COUNT_MISMATCH,
                        path=target,
                        expectedOccurrences=operation.expected_occurrences,
                        actualOccurrences=count,
                    ),
                )
            if count > 1 and not operation.replace_all:
                return (
                    None,
                    "Patch context is ambiguous.",
                    _mutation_error_metadata(
                        MutationErrorCode.AMBIGUOUS_MATCH,
                        path=target,
                        actualOccurrences=count,
                    ),
                )
            total_occurrences += count if operation.replace_all else 1
            new_content = new_content.replace(
                matched_old,
                matched_new,
                count if operation.replace_all else 1,
            )
        if new_content == metadata.content:
            return (
                None,
                "Patch would not change file content.",
                _mutation_error_metadata(MutationErrorCode.NO_OP, path=target),
            )
        return (
            PlannedPatchOperation(
                operation=operation,
                target=target,
                new_target=new_target,
                old_content=metadata.content,
                new_content=new_content,
                encoding=metadata.encoding,
                line_endings=metadata.line_endings,
                policy=policy,
                occurrences=total_occurrences or None,
            ),
            None,
            {},
        )

    def shell(self, command: str, timeout_ms: int = 120_000) -> str:
        name = "shell"
        timeout = max(timeout_ms, 1) / 1000
        marker = f"__DEEPY_CWD_{uuid.uuid4().hex}__"
        shell_invocation = _build_shell_command(command, marker)
        process: subprocess.Popen[bytes] | None = None
        process_id: str | None = None
        try:
            with (
                tempfile.TemporaryFile(mode="w+b") as stdout_file,
                tempfile.TemporaryFile(mode="w+b") as stderr_file,
            ):
                process = subprocess.Popen(
                    [shell_invocation.shell_path, *shell_invocation.args],
                    cwd=self.cwd,
                    env=shell_invocation.env,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    stdin=subprocess.DEVNULL,
                    start_new_session=os.name != "nt",
                )
                process_id = str(process.pid)
                self.running_processes[process_id] = {
                    "startTime": _now_iso(),
                    "command": command,
                }
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    _terminate_process(process)
                    process.wait()
                    stdout, stdout_encoding, stdout_capture_truncated = _read_captured_output(
                        stdout_file, marker=marker
                    )
                    stderr, stderr_encoding, stderr_capture_truncated = _read_captured_output(
                        stderr_file
                    )
                    output, output_truncated = _truncate_output((stdout or "") + (stderr or ""))
                    metadata = _shell_metadata(
                        self.cwd,
                        process_id,
                        shell_invocation,
                        output_truncated=output_truncated,
                        capture_truncated=stdout_capture_truncated or stderr_capture_truncated,
                    )
                    metadata.update(
                        {
                            "timeoutMs": timeout_ms,
                            "interrupted": True,
                            "stdoutEncoding": stdout_encoding,
                            "stderrEncoding": stderr_encoding,
                        }
                    )
                    return ToolResult.error_result(
                        name,
                        f"Command timed out after {timeout_ms}ms.",
                        output=output,
                        metadata=metadata,
                    ).to_json()
                stdout, stdout_encoding, stdout_capture_truncated = _read_captured_output(
                    stdout_file, marker=marker
                )
                stderr, stderr_encoding, stderr_capture_truncated = _read_captured_output(
                    stderr_file
                )
        finally:
            if process_id is not None:
                self.running_processes.pop(process_id, None)

        stdout, final_cwd, exit_code = _extract_bash_sentinel(stdout or "", marker)
        if final_cwd is not None and final_cwd.is_dir():
            self.cwd = final_cwd
        returncode = exit_code if exit_code is not None else process.returncode
        output, output_truncated = _truncate_output(stdout + (stderr or ""))
        metadata = _shell_metadata(
            self.cwd,
            process_id,
            shell_invocation,
            exit_code=returncode,
            output_truncated=output_truncated,
            capture_truncated=stdout_capture_truncated or stderr_capture_truncated,
        )
        metadata.update(
            {
                "stdoutEncoding": stdout_encoding,
                "stderrEncoding": stderr_encoding,
            }
        )
        if returncode == 0:
            return ToolResult.ok_result(
                name,
                output,
                metadata=metadata,
            ).to_json()
        return ToolResult.error_result(
            name,
            f"Command exited with code {returncode}.",
            output=output,
            metadata=metadata,
        ).to_json()

    def ask_user_question(self, questions: object) -> str:
        parsed_questions, error = _parse_ask_user_questions(questions)
        if error is not None:
            return ToolResult.error_result("AskUserQuestion", error).to_json()
        return ToolResult(
            ok=True,
            name="AskUserQuestion",
            output=_build_question_summary(parsed_questions),
            metadata={"kind": "ask_user_question", "questions": parsed_questions},
            awaitUserResponse=True,
        ).to_json()

    def todo_write(self, todos: object | None = None) -> str:
        name = "todo_write"
        if todos is None:
            return ToolResult.ok_result(
                name,
                _todo_tool_output(self.todo_items, changed=False, read_only=True),
                metadata=_todo_tool_metadata(self.todo_items, changed=False, read_only=True),
            ).to_json()
        parsed, error = normalize_todo_items(todos)
        if error is not None or parsed is None:
            return ToolResult.error_result(
                name,
                error or "Invalid todo list.",
                metadata={"kind": "todo_list_error"},
            ).to_json()
        previous = todo_items_to_payload(self.todo_items)
        current = todo_items_to_payload(parsed)
        changed = previous != current
        self.todo_items = parsed
        return ToolResult.ok_result(
            name,
            _todo_tool_output(parsed, changed=changed, read_only=False),
            metadata=_todo_tool_metadata(parsed, changed=changed, read_only=False),
        ).to_json()

    def load_skill(self, name: str) -> str:
        from deepy.skills import find_skill, read_skill_body

        skill = find_skill(self.cwd, name)
        if skill is None:
            return ToolResult.error_result("load_skill", f"Skill not found: {name}").to_json()
        body = read_skill_body(skill)
        if not body:
            return ToolResult.error_result("load_skill", f"Skill is empty: {skill.name}").to_json()
        root = skill.path.parent
        output = (
            f"# Skill: {skill.name}\n\n"
            f"Description: {skill.description or '(no description)'}\n\n"
            f"Scope: {skill.scope}\n\n"
            f"Skill root: {root}\n\n"
            "All scripts, references, and assets in this skill are relative to the skill root.\n\n"
            "---\n\n"
            f"{body}"
        )
        return ToolResult.ok_result(
            "load_skill",
            output,
            metadata={
                "name": skill.name,
                "description": skill.description,
                "scope": skill.scope,
                "path": str(skill.path),
                "root": str(root),
            },
        ).to_json()

    def web_search(self, query: str) -> str:
        name = "WebSearch"
        if not query.strip():
            return ToolResult.error_result(name, 'Missing required "query" string.').to_json()
        self.web_search_calls += 1
        if self.web_search_calls > MAX_WEB_SEARCH_CALLS_PER_TURN:
            return ToolResult.error_result(
                name,
                (
                    f"WebSearch call limit reached for this turn "
                    f"({MAX_WEB_SEARCH_CALLS_PER_TURN}). Stop searching and answer from the "
                    "results already gathered, or use WebFetch only for a specific URL that is "
                    "essential."
                ),
                metadata={
                    "callLimit": MAX_WEB_SEARCH_CALLS_PER_TURN,
                    "callCount": self.web_search_calls,
                },
            ).to_json()
        return self._web_search_builtin(query)

    def web_fetch(self, url: str) -> str:
        name = "WebFetch"
        target_url, validation_error = _validate_web_fetch_url(url)
        if validation_error is not None or target_url is None:
            return ToolResult.error_result(
                name, validation_error or 'Missing required "url" string.'
            ).to_json()

        activity_label = f"WebFetch: {target_url}"
        activity_id = f"web-fetch-{uuid.uuid4().hex}"
        self.running_processes[activity_id] = {
            "startTime": _now_iso(),
            "command": activity_label,
        }
        request = urllib.request.Request(
            target_url,
            headers={
                **WEB_SEARCH_BROWSER_HEADERS,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                final_url = response.geturl()
                content_type = _response_header(response, "Content-Type") or ""
                content_encoding = _response_header(response, "Content-Encoding")
                body = response.read(MAX_WEB_FETCH_BYTES + 1)
        except Exception as exc:
            return ToolResult.error_result(
                name,
                f"WebFetch request failed: {exc}",
                metadata={
                    "url": target_url,
                    "activityLabel": activity_label,
                },
            ).to_json()
        finally:
            self.running_processes.pop(activity_id, None)

        bytes_truncated = len(body) > MAX_WEB_FETCH_BYTES
        body = body[:MAX_WEB_FETCH_BYTES]
        charset = _charset_from_content_type(content_type)
        try:
            decoded = _decode_http_body(body, encoding=content_encoding, charset=charset)
        except Exception as exc:
            return ToolResult.error_result(
                name,
                f"WebFetch response decode failed: {exc}",
                metadata={
                    "url": target_url,
                    "finalUrl": final_url,
                    "contentType": content_type,
                    "contentEncoding": content_encoding,
                    "charset": charset,
                    "activityLabel": activity_label,
                },
            ).to_json()
        if _is_html_response(content_type, decoded):
            title, readable_text, metadata_text = _extract_readable_html(decoded)
            readable_text = _select_web_fetch_html_text(readable_text, metadata_text)
        else:
            title = ""
            readable_text = decoded.strip()
        output = _format_web_fetch_output(
            url=target_url,
            final_url=final_url,
            content_type=content_type,
            title=title,
            text=readable_text,
            bytes_truncated=bytes_truncated,
        )
        output, output_truncated = _truncate_output(output, MAX_WEB_FETCH_OUTPUT_CHARS)
        return ToolResult.ok_result(
            name,
            output,
            metadata={
                "url": target_url,
                "finalUrl": final_url,
                "contentType": content_type,
                "charset": charset,
                "byteCount": len(body),
                "bodyTruncated": bytes_truncated,
                "outputTruncated": output_truncated,
                "activityLabel": activity_label,
            },
        ).to_json()

    def _web_search_builtin(self, query: str) -> str:
        name = "WebSearch"
        prepared, prepare_error = _prepare_web_search_query_with_llm(query, self.settings)
        activity_label = _format_web_search_activity_label(prepared.resolved_query)
        activity_id = f"web-search-{uuid.uuid4().hex}"
        self.running_processes[activity_id] = {
            "startTime": _now_iso(),
            "command": activity_label,
        }
        failures: list[WebSearchProviderFailure] = []
        query_metadata = {
            **prepared.metadata(),
            "activityLabel": activity_label,
            **({"queryPreparationWarning": prepare_error} if prepare_error else {}),
        }
        try:
            searxng_url = (
                self.settings.tools.web_search.searxng_url or DEFAULT_WEB_SEARCH_SEARXNG_URL
            )
            result, failure = self._try_searxng_search(prepared.resolved_query, searxng_url)
            if result is not None:
                return ToolResult.ok_result(
                    name,
                    _format_search_results(prepared.resolved_query, result.results),
                    metadata={
                        **query_metadata,
                        "backend": result.provider,
                        "provider": result.provider,
                        "searchUrl": _mask_url_secrets(result.search_url),
                        "providerAttempts": [{**item.metadata(), "ok": False} for item in failures]
                        + [{"provider": result.provider, "ok": True}],
                        "resultCount": min(len(result.results), DEFAULT_WEB_SEARCH_RESULTS),
                    },
                ).to_json()
            if failure is not None:
                failures.append(failure)

            result, failure = self._try_duckduckgo_search(prepared.resolved_query)
            if result is not None:
                return ToolResult.ok_result(
                    name,
                    _format_search_results(prepared.resolved_query, result.results),
                    metadata={
                        **query_metadata,
                        "backend": result.provider,
                        "provider": result.provider,
                        "searchUrl": _mask_url_secrets(result.search_url),
                        "providerAttempts": [{**item.metadata(), "ok": False} for item in failures]
                        + [{"provider": result.provider, "ok": True}],
                        "resultCount": min(len(result.results), DEFAULT_WEB_SEARCH_RESULTS),
                    },
                ).to_json()
            if failure is not None:
                failures.append(failure)

            return ToolResult.error_result(
                name,
                "WebSearch failed: " + _format_provider_failures(failures),
                metadata={
                    **query_metadata,
                    "backend": "provider_chain",
                    "providerAttempts": [{**item.metadata(), "ok": False} for item in failures],
                },
            ).to_json()
        finally:
            self.running_processes.pop(activity_id, None)

    def _try_duckduckgo_search(
        self,
        query: str,
    ) -> tuple[WebSearchProviderResult | None, WebSearchProviderFailure | None]:
        provider = "duckduckgo_html"
        search_url = (
            DEFAULT_WEB_SEARCH_URL + "?" + urllib.parse.urlencode({"q": query}, doseq=False)
        )
        request = urllib.request.Request(
            search_url,
            headers={
                **WEB_SEARCH_BROWSER_HEADERS,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = _decode_http_body(
                    response.read(),
                    encoding=_response_header(response, "Content-Encoding"),
                )
        except Exception as exc:
            return None, WebSearchProviderFailure(
                provider=provider,
                error=f"request failed: {exc}",
                search_url=search_url,
            )
        results = _parse_search_results(body)
        if not results:
            return None, WebSearchProviderFailure(
                provider=provider,
                error="no parseable results",
                search_url=search_url,
            )
        return WebSearchProviderResult(
            provider=provider, search_url=search_url, results=results
        ), None

    def _try_searxng_search(
        self,
        query: str,
        base_url: str,
    ) -> tuple[WebSearchProviderResult | None, WebSearchProviderFailure | None]:
        provider = "searxng_json"
        try:
            search_url = _build_searxng_search_url(base_url, query)
        except ValueError as exc:
            return None, WebSearchProviderFailure(provider=provider, error=str(exc))
        request = urllib.request.Request(
            search_url,
            headers=WEB_SEARCH_BROWSER_HEADERS,
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = _decode_http_body(
                    response.read(),
                    encoding=_response_header(response, "Content-Encoding"),
                )
            results = _parse_searxng_results(body)
        except Exception as exc:
            return None, WebSearchProviderFailure(
                provider=provider,
                error=f"request failed: {exc}",
                search_url=search_url,
            )
        if not results:
            return None, WebSearchProviderFailure(
                provider=provider,
                error="no parseable results",
                search_url=search_url,
            )
        return WebSearchProviderResult(
            provider=provider, search_url=search_url, results=results
        ), None


def _unified_diff(old: str, new: str, *, path: str) -> str:
    return "".join(
        unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _patch_changed_path_summary(paths: list[str]) -> str:
    if len(paths) == 1:
        return paths[0]
    return f"{len(paths)} files"


def _read_text_preserving_newlines(path: Path) -> str:
    return _read_text_metadata(path).content


def _read_text_metadata(path: Path) -> TextFileMetadata:
    data = path.read_bytes()
    encoding = _detect_text_encoding(data)
    text = data.decode(_python_text_encoding(encoding), errors="replace")
    return TextFileMetadata(
        content=text,
        encoding=encoding,
        line_endings=_detect_line_endings(text),
    )


def _detect_text_encoding(data: bytes) -> str:
    if len(data) >= 2 and data[0] == 0xFF and data[1] == 0xFE:
        return "utf16le"
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf8-sig"
    try:
        data.decode("utf-8", errors="strict")
        return "utf8"
    except UnicodeDecodeError:
        pass
    try:
        data.decode("gb18030", errors="strict")
        return "gb18030"
    except UnicodeDecodeError:
        return "utf8"


def _python_text_encoding(encoding: str) -> str:
    if encoding == "utf16le":
        return "utf-16"
    if encoding == "utf8-sig":
        return "utf-8-sig"
    if encoding == "gb18030":
        return "gb18030"
    return "utf8"


def _default_new_text_encoding() -> str:
    return "utf8"


def _write_text_with_encoding(path: Path, content: str, encoding: str) -> None:
    path.write_bytes(content.encode(_python_text_encoding(encoding)))


def _atomic_write_text_with_encoding(
    path: Path,
    content: str,
    encoding: str,
    *,
    platform_name: str,
) -> AtomicWriteResult:
    data = content.encode(_python_text_encoding(encoding))
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode if path.exists() else None
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp_path = Path(temp_name)
    retries = 0
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
        if mode is not None:
            try:
                os.chmod(temp_path, mode)
            except OSError:
                pass
        max_retries = ATOMIC_RENAME_RETRIES if platform_name.startswith("win") else 0
        while True:
            try:
                os.replace(temp_path, path)
                return AtomicWriteResult(fallback_used=False, retries=retries)
            except PermissionError:
                if retries >= max_retries:
                    raise
                retries += 1
                time.sleep(ATOMIC_RENAME_BACKOFF_SECONDS * retries)
    except OSError:
        try:
            _write_text_with_encoding(path, content, encoding)
            return AtomicWriteResult(fallback_used=True, retries=retries)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass


def _create_mutation_backup(cwd: Path, path: Path) -> dict[str, object]:
    if not path.exists() or not path.is_file():
        return {"backupCreated": False}
    backup_dir = cwd / ".deepy" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    relative_name = str(path.relative_to(cwd.resolve())).replace("/", "__").replace("\\", "__")
    backup_path = backup_dir / f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}-{relative_name}"
    shutil.copy2(path, backup_path)
    return {"backupCreated": True, "backupPath": str(backup_path)}


def _stale_write_recovery_metadata(path: Path, error: str | None) -> dict[str, object]:
    if error != "File changed since it was read: it no longer exists.":
        return {}
    return {
        "path": str(path),
        "recovery": (
            "The file was deleted after Deepy read it. Re-read the path or use a "
            "managed full-file replacement before deletion; do not recreate Unicode "
            "files through shell here-strings."
        ),
        "recovery_kind": "stale_deleted_file",
    }


def _coerce_write_content(path: Path, content: object) -> tuple[str, dict[str, object], str | None]:
    if isinstance(content, str):
        return content, {}, None
    if path.suffix.lower() == ".json" and content is not None and not isinstance(content, bytes):
        try:
            return (
                json_utils.dumps_pretty(content),
                {"input_repaired": True, "repair_kind": "json-stringify-content"},
                None,
            )
        except TypeError as exc:
            return "", {}, f"JSON content is not serializable: {exc}"
    return "", {}, "content must be a string."


def _normalize_optional_tool_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped.casefold() in {"null", "none", "undefined"}:
        return None
    return value


STRUCTURED_PATCH_OPERATION_FIELDS = {
    "type",
    "file_path",
    "destination_path",
    "content",
    "old_text",
    "new_text",
    "anchor",
    "expected_occurrences",
    "replace_all",
    "overwrite",
    "snapshot_id",
    "expected_hash",
}


def _parse_structured_patch_operations(
    value: object,
) -> tuple[list[PatchOperation], str | None, dict[str, object]]:
    if isinstance(value, str):
        return (
            [],
            "apply_patch now requires structured operations, not a patch string.",
            {
                "recovery": "Call apply_patch with an operations array of create_file, replace_block, insert_after, replace_all, delete_file, move_file, or replace_file objects.",
                "expectedProtocol": "structured_operations",
            },
        )
    if isinstance(value, dict):
        container = cast(dict[str, object], value)
        raw_operations = container.get("operations")
    else:
        raw_operations = value
    if not isinstance(raw_operations, list):
        return (
            [],
            "apply_patch requires an operations array.",
            {
                "recovery": "Pass {'operations': [...]} or the operations array from the tool schema.",
                "expectedProtocol": "structured_operations",
            },
        )

    operations: list[PatchOperation] = []
    failures: list[dict[str, object]] = []
    for index, item in enumerate(raw_operations):
        operation, error, metadata = _parse_structured_patch_operation(item)
        if error is not None:
            failures.append({"index": index, "error": error, **metadata})
        elif operation is not None:
            operations.append(operation)
    if failures:
        return [], "Invalid structured patch operation.", {"failures": failures}
    return operations, None, {}


def _parse_structured_patch_operation(
    value: object,
) -> tuple[PatchOperation | None, str | None, dict[str, object]]:
    if not isinstance(value, dict):
        return None, "Each operation must be an object.", {}
    value = cast(dict[str, object], value)
    unknown = sorted(set(value) - STRUCTURED_PATCH_OPERATION_FIELDS)
    if unknown:
        return None, "Operation contains unsupported fields.", {"unsupportedFields": unknown}
    kind = value.get("type")
    if not isinstance(kind, str) or not kind:
        return None, "Operation type is required.", {}
    file_path = value.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        return None, "file_path is required.", {"operation": kind}
    unexpected = _unexpected_structured_patch_fields(kind, value)
    if unexpected:
        return (
            None,
            "Operation contains fields that are not valid for its type.",
            {"operation": kind, "path": file_path, "invalidFields": unexpected},
        )

    expected_occurrences, error = _optional_positive_int(value.get("expected_occurrences"))
    if error is not None:
        return None, error, {"operation": kind, "path": file_path}
    replace_all = value.get("replace_all")
    replace_all_bool = bool(replace_all) if isinstance(replace_all, bool) else False
    overwrite = value.get("overwrite")
    overwrite_bool = bool(overwrite) if isinstance(overwrite, bool) else False
    snapshot_id = _optional_string_value(value.get("snapshot_id"))
    expected_hash = _optional_string_value(value.get("expected_hash"))

    if kind == "create_file":
        content = value.get("content")
        if not isinstance(content, str):
            return None, "create_file requires string content.", {"operation": kind, "path": file_path}
        return (
            PatchOperation(kind=kind, path=file_path, content=content),
            None,
            {},
        )
    if kind == "replace_file":
        content = value.get("content")
        if not isinstance(content, str):
            return None, "replace_file requires string content.", {"operation": kind, "path": file_path}
        return (
            PatchOperation(
                kind=kind,
                path=file_path,
                content=content,
                overwrite=overwrite_bool,
                snapshot_id=snapshot_id,
                expected_hash=expected_hash,
            ),
            None,
            {},
        )
    if kind == "delete_file":
        return PatchOperation(kind=kind, path=file_path), None, {}
    if kind == "move_file":
        destination = value.get("destination_path")
        if not isinstance(destination, str) or not destination.strip():
            return None, "move_file requires destination_path.", {"operation": kind, "path": file_path}
        return PatchOperation(kind=kind, path=file_path, move_to=destination), None, {}
    if kind in {"replace_block", "replace_all"}:
        old_text = value.get("old_text")
        new_text = value.get("new_text")
        if not isinstance(old_text, str) or old_text == "":
            return None, f"{kind} requires non-empty old_text.", {"operation": kind, "path": file_path}
        if not isinstance(new_text, str):
            return None, f"{kind} requires string new_text.", {"operation": kind, "path": file_path}
        if old_text == new_text:
            return None, "Operation would not change file content.", {
                **_mutation_error_metadata(MutationErrorCode.NO_OP),
                "operation": kind,
                "path": file_path,
            }
        return (
            PatchOperation(
                kind=kind,
                path=file_path,
                hunks=((old_text, new_text),),
                expected_occurrences=expected_occurrences if expected_occurrences is not None else (None if kind == "replace_all" else 1),
                replace_all=kind == "replace_all" or replace_all_bool,
            ),
            None,
            {},
        )
    if kind in {"insert_before", "insert_after"}:
        anchor = value.get("anchor")
        content = value.get("content")
        if not isinstance(anchor, str) or anchor == "":
            return None, f"{kind} requires non-empty anchor.", {"operation": kind, "path": file_path}
        if not isinstance(content, str) or content == "":
            return None, f"{kind} requires non-empty content.", {"operation": kind, "path": file_path}
        old_text = anchor
        new_text = content + anchor if kind == "insert_before" else anchor + content
        return (
            PatchOperation(
                kind=kind,
                path=file_path,
                hunks=((old_text, new_text),),
                expected_occurrences=expected_occurrences if expected_occurrences is not None else 1,
                replace_all=replace_all_bool,
            ),
            None,
            {},
        )
    return None, "Unsupported apply_patch operation type.", {"operation": kind, "path": file_path}


def _unexpected_structured_patch_fields(kind: str, value: dict[str, object]) -> list[str]:
    allowed_by_kind = {
        "create_file": {"type", "file_path", "content"},
        "replace_file": {
            "type",
            "file_path",
            "content",
            "overwrite",
            "snapshot_id",
            "expected_hash",
        },
        "delete_file": {"type", "file_path"},
        "move_file": {"type", "file_path", "destination_path"},
        "replace_block": {
            "type",
            "file_path",
            "old_text",
            "new_text",
            "expected_occurrences",
            "replace_all",
        },
        "insert_before": {
            "type",
            "file_path",
            "anchor",
            "content",
            "expected_occurrences",
            "replace_all",
        },
        "insert_after": {
            "type",
            "file_path",
            "anchor",
            "content",
            "expected_occurrences",
            "replace_all",
        },
        "replace_all": {
            "type",
            "file_path",
            "old_text",
            "new_text",
            "expected_occurrences",
            "replace_all",
        },
    }
    allowed = allowed_by_kind.get(kind)
    if allowed is None:
        return []
    return sorted(
        field
        for field, field_value in value.items()
        if field not in allowed and _structured_patch_field_is_set(field_value)
    )


def _structured_patch_field_is_set(value: object) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str) and value == "":
        return False
    return True


def _optional_positive_int(value: object) -> tuple[int | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, bool) or not isinstance(value, int):
        return None, "expected_occurrences must be an integer or null."
    if value < 1:
        return None, "expected_occurrences must be greater than zero."
    return value, None


def _optional_string_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value
    return None


def _normalize_patch_operation_path(cwd: Path, path: str, *, expect_existing: bool) -> str:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return path
    parts = candidate.parts
    if not parts or parts[0] not in {"a", "b"}:
        return path
    stripped = Path(*parts[1:]) if len(parts) > 1 else Path()
    if not str(stripped):
        return path
    if expect_existing and (cwd / stripped).exists():
        return str(stripped)
    if not expect_existing and not (cwd / candidate).exists():
        return str(stripped)
    return path


def _new_file_line_endings(path: Path, content: str) -> str:
    suffix = path.suffix.lower()
    if suffix in {".bat", ".cmd"}:
        return "CRLF"
    return _detect_line_endings(content)


def _select_patch_replacement_variant(
    text: str,
    old: str,
    new: str,
) -> tuple[str, str, int]:
    variants: list[tuple[str, str]] = [(old, new)]
    if old.endswith("\n"):
        variants.append((old[:-1], new[:-1] if new.endswith("\n") else new))
    if old.startswith("\n"):
        variants.append((old[1:], new[1:] if new.startswith("\n") else new))
    if old.startswith("\n") and old.endswith("\n"):
        trimmed_new = new
        if trimmed_new.startswith("\n"):
            trimmed_new = trimmed_new[1:]
        if trimmed_new.endswith("\n"):
            trimmed_new = trimmed_new[:-1]
        variants.append((old[1:-1], trimmed_new))

    seen: set[str] = set()
    best = (old, new, 0)
    for candidate_old, candidate_new in variants:
        if not candidate_old or candidate_old in seen:
            continue
        seen.add(candidate_old)
        count = text.count(candidate_old)
        if count == 1:
            return candidate_old, candidate_new, count
        if count > best[2]:
            best = (candidate_old, candidate_new, count)
    return best


def _format_notebook(path: Path) -> tuple[str, str | None]:
    raw = _read_text_preserving_newlines(path)
    if not raw:
        return "WARNING: File is empty.", None
    try:
        parsed = json_utils.loads(raw)
    except json_utils.JSONDecodeError as exc:
        return "", f"Failed to parse notebook JSON: {exc}"
    if not isinstance(parsed, dict):
        return "WARNING: Notebook has no cells.", None

    cells = parsed.get("cells")
    lines: list[str] = []
    if isinstance(cells, list):
        for index, raw_cell in enumerate(cells):
            cell = _string_key_dict(raw_cell)
            if cell is None:
                continue
            raw_cell_type = cell.get("cell_type")
            cell_type = raw_cell_type if isinstance(raw_cell_type, str) else "unknown"
            lines.append(f"# Cell {index + 1} ({cell_type})")
            lines.extend(_normalize_notebook_field(cell.get("source")))

            outputs = cell.get("outputs")
            if not isinstance(outputs, list):
                continue
            for output_index, raw_output in enumerate(outputs):
                output = _string_key_dict(raw_output)
                if output is None:
                    continue
                raw_output_type = output.get("output_type")
                output_type = raw_output_type if isinstance(raw_output_type, str) else "output"
                lines.append(f"# Output {output_index + 1} ({output_type})")
                lines.extend(_format_notebook_output(output))

    if not lines:
        return "WARNING: Notebook has no cells.", None
    return "\n".join(f"{idx + 1}: {line}" for idx, line in enumerate(lines)), None


def _normalize_notebook_field(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).removesuffix("\n").removesuffix("\r") for item in value]
    if isinstance(value, str):
        return value.splitlines()
    return []


def _format_notebook_output(output: dict[str, object]) -> list[str]:
    lines = _normalize_notebook_field(output.get("text"))
    data = output.get("data")
    data_dict = _string_key_dict(data)
    if data_dict is not None:
        lines.extend(_normalize_notebook_field(data_dict.get("text/plain")))
        image_png = data_dict.get("image/png")
        if isinstance(image_png, str):
            lines.append(f"[image/png {len(image_png)} chars]")
        image_jpeg = data_dict.get("image/jpeg")
        if isinstance(image_jpeg, str):
            lines.append(f"[image/jpeg {len(image_jpeg)} chars]")
    traceback = output.get("traceback")
    if isinstance(traceback, list):
        lines.extend(str(item).removesuffix("\n").removesuffix("\r") for item in traceback)
    return lines or ["[output omitted]"]


def _string_key_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    if not all(isinstance(key, str) for key in value):
        return None
    return {key: item for key, item in value.items() if isinstance(key, str)}


@dataclass(frozen=True)
class PageRange:
    start: int
    end: int

    @property
    def count(self) -> int:
        return self.end - self.start + 1

    def label(self) -> str:
        return f"{self.start}-{self.end}"


def _read_pdf(path: Path, pages: str | None, *, name: str) -> str:
    data = path.read_bytes()
    page_count = _count_pdf_pages(data)
    page_range, range_error = _parse_page_range(pages)
    if range_error is not None:
        return ToolResult.error_result(name, range_error, metadata={"path": str(path)}).to_json()

    if page_range is None and page_count is not None and page_count > PDF_LARGE_PAGE_THRESHOLD:
        return ToolResult.error_result(
            name,
            f'PDF has {page_count} pages; provide "pages" to read a range.',
            metadata={"path": str(path), "pageCount": page_count},
        ).to_json()
    if page_range is not None and page_range.count > PDF_MAX_PAGE_RANGE:
        return ToolResult.error_result(
            name,
            f"PDF page range exceeds {PDF_MAX_PAGE_RANGE} pages.",
            metadata={"path": str(path), "pageCount": page_count},
        ).to_json()
    if page_range is not None and page_count is not None and page_range.end > page_count:
        return ToolResult.error_result(
            name,
            f"PDF page range exceeds total page count ({page_count}).",
            metadata={"path": str(path), "pageCount": page_count},
        ).to_json()

    encoded = base64.b64encode(data).decode("ascii")
    return ToolResult.ok_result(
        name,
        f"data:application/pdf;base64,{encoded}",
        metadata={
            "path": str(path),
            "mime": "application/pdf",
            "encoding": "base64",
            "bytes": len(data),
            "pageCount": page_count,
            "pages": page_range.label() if page_range is not None else None,
        },
    ).to_json()


def _count_pdf_pages(data: bytes) -> int | None:
    try:
        text = data.decode("latin1", errors="ignore")
    except Exception:
        return None
    return len(re.findall(r"/Type\s*/Page\b(?!s)", text))


def _parse_page_range(value: str | None) -> tuple[PageRange | None, str | None]:
    if value is None or not value.strip():
        return None, None
    trimmed = value.strip()
    if "," in trimmed:
        return None, 'pages must be a single range like "1-5" or "3".'
    parts = [part.strip() for part in trimmed.split("-")]
    if len(parts) == 1:
        start, error = _parse_positive_int(parts[0], "pages")
        return (PageRange(start, start), None) if error is None else (None, error)
    if len(parts) == 2:
        start, start_error = _parse_positive_int(parts[0], "pages")
        if start_error is not None:
            return None, start_error
        end, end_error = _parse_positive_int(parts[1], "pages")
        if end_error is not None:
            return None, end_error
        if end < start:
            return None, "pages range end must be >= start."
        return PageRange(start, end), None
    return None, 'pages must be a single range like "1-5" or "3".'


def _parse_positive_int(value: str, label: str) -> tuple[int, str | None]:
    try:
        numeric = float(value)
    except ValueError:
        return 0, f"{label} must be a number."
    if not math.isfinite(numeric):
        return 0, f"{label} must be a number."
    integer = int(numeric)
    if integer < 1:
        return 0, f"{label} must be >= 1."
    return integer, None


IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".avif": "image/avif",
}


def _image_mime_type(suffix: str) -> str | None:
    return IMAGE_MIME_TYPES.get(suffix)


def _build_image_follow_up_message(path: Path, mime: str, data: bytes) -> dict[str, object]:
    encoded = base64.b64encode(data).decode("ascii")
    return {
        "role": "system",
        "content": [
            {
                "type": "input_text",
                "text": (
                    f"The read tool has loaded `{path.name}`. "
                    "Use the attached image content to answer the original request."
                ),
            },
            {
                "type": "input_image",
                "image_url": f"data:{mime};base64,{encoded}",
            },
        ],
    }


def _detect_line_endings(text: str) -> str:
    return "CRLF" if "\r\n" in text else "LF"


def _normalize_line_endings(text: str, line_endings: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "\r\n") if line_endings == "CRLF" else normalized


def _truncate_line(line: str) -> str:
    if len(line) <= MAX_LINE_LENGTH:
        return line
    return line[:MAX_LINE_LENGTH] + "... [truncated]"


def _truncate_output(output: str, max_chars: int = MAX_BASH_OUTPUT_CHARS) -> tuple[str, bool]:
    if len(output) <= max_chars:
        return output, False
    omitted = len(output) - max_chars
    return output[:max_chars] + f"\n... [truncated {omitted} chars]", True


def _read_captured_output(stream, *, marker: str | None = None) -> tuple[str, str, bool]:
    stream.flush()
    stream.seek(0)
    data = stream.read(MAX_BASH_CAPTURE_CHARS + 1)
    truncated = len(data) > MAX_BASH_CAPTURE_CHARS
    if truncated:
        data = data[:MAX_BASH_CAPTURE_CHARS]
    text, encoding = decode_shell_output(data, marker=marker)
    return text, encoding, truncated


def _build_shell_command(
    command: str,
    marker: str,
    *,
    shell_path: str | None = None,
    env: dict[str, str] | None = None,
    platform_name: str | None = None,
    os_name: str | None = None,
) -> ShellInvocation:
    resolved_shell = shell_path or _resolve_shell_path(env=env, os_name=os_name)
    runtime_environment = detect_runtime_environment(
        shell_path=resolved_shell,
        env=env,
        platform_name=platform_name,
        os_name=os_name,
    )
    process_env = _build_shell_process_env(runtime_environment, env)
    if runtime_environment.command_dialect == "powershell":
        return ShellInvocation(
            shell_path=resolved_shell,
            args=_build_powershell_args(command, marker),
            runtime_environment=runtime_environment,
            env=process_env,
        )
    if runtime_environment.command_dialect == "cmd":
        return ShellInvocation(
            shell_path=resolved_shell,
            args=_build_cmd_args(command, marker),
            runtime_environment=runtime_environment,
            env=process_env,
        )
    return ShellInvocation(
        shell_path=resolved_shell,
        args=_build_posix_shell_args(command, marker, resolved_shell),
        runtime_environment=runtime_environment,
        env=process_env,
    )


def _build_shell_process_env(
    runtime_environment: RuntimeEnvironment,
    env: dict[str, str] | None = None,
) -> dict[str, str] | None:
    if runtime_environment.os_family != "windows":
        return dict(env) if env is not None else None
    process_env = dict(os.environ if env is None else env)
    process_env.setdefault("PYTHONUTF8", "1")
    process_env.setdefault("PYTHONIOENCODING", "utf-8")
    return process_env


def _build_posix_shell_args(command: str, marker: str, shell_path: str) -> list[str]:
    normalized_command = rewrite_windows_null_redirect(command)
    parts = [
        part
        for part in (
            build_shell_init_command(shell_path),
            build_disable_extglob_command(shell_path),
            normalized_command,
            "__deepy_exit=$?",
            f'printf \'\\n{marker}CWD=%s\\n{marker}EXIT=%s\\n\' "$PWD" "$__deepy_exit"',
            "exit $__deepy_exit",
        )
        if part
    ]
    return ["-c", "{ " + "; ".join(parts) + "; } < /dev/null"]


def _build_powershell_args(command: str, marker: str) -> list[str]:
    script = "\n".join(
        [
            "$OutputEncoding = [System.Text.UTF8Encoding]::new($false)",
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)",
            "$global:LASTEXITCODE = $null",
            "try {",
            command,
            "    $__deepy_success = $?",
            "    $__deepy_last_exit = $global:LASTEXITCODE",
            "    if ($null -eq $__deepy_last_exit) {",
            "        if ($__deepy_success) { $__deepy_exit = 0 } else { $__deepy_exit = 1 }",
            "    } else {",
            "        $__deepy_exit = [int]$__deepy_last_exit",
            "    }",
            "} catch {",
            "    Write-Error $_",
            "    $__deepy_exit = 1",
            "}",
            "$__deepy_cwd = (Get-Location).ProviderPath",
            'Write-Output ""',
            f'Write-Output "{marker}CWD=$__deepy_cwd"',
            f'Write-Output "{marker}EXIT=$__deepy_exit"',
            "exit $__deepy_exit",
        ]
    )
    return ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script]


def _build_cmd_args(command: str, marker: str) -> list[str]:
    script = "\r\n".join(
        [
            command,
            'set "__deepy_exit=%ERRORLEVEL%"',
            "echo.",
            f"echo {marker}CWD=%CD%",
            f"echo {marker}EXIT=%__deepy_exit%",
            "exit /b %__deepy_exit%",
        ]
    )
    return ["/d", "/s", "/c", script]


def _resolve_shell_path(
    *,
    env: dict[str, str] | None = None,
    os_name: str | None = None,
) -> str:
    environment = env or os.environ
    resolved_os_name = os_name or os.name
    shell_path = environment.get("SHELL")
    if shell_path:
        return shell_path
    if resolved_os_name == "nt":
        if "PSModulePath" in environment:
            return (
                environment.get("POWERSHELL")
                or shutil.which("pwsh")
                or shutil.which("powershell")
                or "powershell.exe"
            )
        comspec = environment.get("COMSPEC") or environment.get("ComSpec")
        if comspec:
            return comspec
        return shutil.which("pwsh") or shutil.which("powershell") or "cmd.exe"
    return "/bin/zsh" if Path("/bin/zsh").exists() else "/bin/sh"


def _shell_metadata(
    cwd: Path,
    process_id: str | None,
    shell_invocation: ShellInvocation,
    *,
    exit_code: int | None = None,
    output_truncated: bool,
    capture_truncated: bool,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "cwd": str(cwd),
        "processId": process_id,
        "shellPath": shell_invocation.shell_path,
        "shellKind": shell_invocation.runtime_environment.shell_kind,
        "commandDialect": shell_invocation.runtime_environment.command_dialect,
        "pathStyle": shell_invocation.runtime_environment.path_style,
        "osFamily": shell_invocation.runtime_environment.os_family,
        "outputTruncated": output_truncated,
        "captureTruncated": capture_truncated,
    }
    if exit_code is not None:
        metadata["exitCode"] = exit_code
    return metadata


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except OSError:
        return


def _format_directory_entries(path: Path, project_root: Path) -> tuple[str, int, int]:
    lines: list[str] = []
    ignored_count = 0
    gitignore = _load_gitignore_matcher(project_root)
    for entry in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if _is_ignored_entry(entry, project_root, gitignore):
            ignored_count += 1
            continue
        suffix = "/" if entry.is_dir() else ""
        try:
            size = entry.stat().st_size
        except OSError:
            size = 0
        lines.append(f"{entry.name}{suffix}\t{size}")
    return "\n".join(lines), len(lines), ignored_count


def _normalize_relative_suffix(path: str) -> str:
    suffix = path.replace("\\", "/").strip("/")
    parts = [part for part in suffix.split("/") if part and part != "."]
    return "/".join(parts)


def _find_suffix_matches(root: Path, suffix: str) -> list[Path]:
    matches: list[Path] = []
    gitignore = _load_gitignore_matcher(root)
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not _is_ignored_entry(Path(current) / dirname, root, gitignore)
        ]
        current_path = Path(current)
        for filename in filenames:
            full_path = current_path / filename
            if _is_ignored_entry(full_path, root, gitignore):
                continue
            try:
                relative = full_path.relative_to(root).as_posix()
            except ValueError:
                continue
            if relative.endswith(suffix):
                matches.append(full_path.resolve())
    return matches


def _is_ignored_entry(
    path: Path,
    project_root: Path,
    gitignore: "GitignoreMatcher",
) -> bool:
    if path.name in IGNORED_DIRECTORY_ENTRIES:
        return True
    try:
        relative = path.relative_to(project_root).as_posix()
    except ValueError:
        return False
    return gitignore.ignores(relative, path.is_dir())


@dataclass(frozen=True)
class GitignorePattern:
    pattern: str
    negated: bool = False


@dataclass(frozen=True)
class GitignoreMatcher:
    patterns: tuple[GitignorePattern, ...]

    def ignores(self, relative_path: str, is_dir: bool) -> bool:
        normalized = relative_path.strip("/")
        if not normalized:
            return False
        ignored = False
        for item in self.patterns:
            if _gitignore_pattern_matches(item.pattern, normalized, is_dir):
                ignored = not item.negated
        return ignored


def _load_gitignore_matcher(project_root: Path) -> GitignoreMatcher:
    gitignore = project_root / ".gitignore"
    if not gitignore.is_file():
        return GitignoreMatcher(())
    patterns: list[GitignorePattern] = []
    for raw_line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:].strip()
        if line:
            patterns.append(GitignorePattern(line.replace("\\", "/"), negated))
    return GitignoreMatcher(tuple(patterns))


def _gitignore_pattern_matches(pattern: str, relative_path: str, is_dir: bool) -> bool:
    directory_only = pattern.endswith("/")
    normalized_pattern = pattern.strip("/")
    if not normalized_pattern:
        return False
    if directory_only and not is_dir:
        return relative_path.startswith(normalized_pattern + "/")
    if "/" in normalized_pattern:
        return fnmatch(relative_path, normalized_pattern) or relative_path.startswith(
            normalized_pattern + "/"
        )
    parts = relative_path.split("/")
    return any(fnmatch(part, normalized_pattern) for part in parts)


def _parse_ask_user_questions(value: object) -> tuple[list[AskUserQuestion], str | None]:
    if not isinstance(value, list) or not value:
        return [], '"questions" must be a non-empty array.'

    questions: list[AskUserQuestion] = []
    for index, raw_item in enumerate(value):
        item = _string_key_dict(raw_item)
        if item is None:
            return [], f"Question at index {index} must be an object."

        question = _trimmed_string(item.get("question"))
        if not question:
            return [], f'Question at index {index} is missing a non-empty "question" string.'

        raw_options = item.get("options")
        if not isinstance(raw_options, list) or not raw_options:
            return [], f'Question at index {index} must include a non-empty "options" array.'

        options: list[AskUserOption] = []
        for option_index, raw_option in enumerate(raw_options):
            option = _string_key_dict(raw_option)
            if option is None:
                return [], f"Option {option_index} for question {index} must be an object."

            label = _trimmed_string(option.get("label"))
            if not label:
                return (
                    [],
                    f'Option {option_index} for question {index} is missing a non-empty "label" string.',
                )

            parsed_option: AskUserOption = {"label": label}
            description = _trimmed_string(option.get("description"))
            if description:
                parsed_option["description"] = description
            options.append(parsed_option)

        parsed_question: AskUserQuestion = {
            "question": question,
            "options": options,
        }
        multi_select = item.get("multiSelect")
        if isinstance(multi_select, bool):
            parsed_question["multiSelect"] = multi_select
        questions.append(parsed_question)

    return questions, None


def _build_question_summary(questions: list[AskUserQuestion]) -> str:
    lines = ["Waiting for user input."]
    for index, item in enumerate(questions):
        lines.append("")
        lines.append(f"{index + 1}. {item['question']}")
        lines.append(f"   Mode: {'multi-select' if item.get('multiSelect') else 'single-select'}")
        for option in item["options"]:
            lines.append(f"   - {option['label']}")
            if option.get("description"):
                lines.append(f"     {option['description']}")
        lines.append("   - Other")
    return "\n".join(lines)


def _todo_tool_metadata(
    todos: list[TodoItem],
    *,
    changed: bool,
    read_only: bool,
) -> dict[str, object]:
    return {
        "kind": "todo_list",
        "todos": todo_items_to_payload(todos),
        "counts": todo_counts(todos),
        "changed": changed,
        "readOnly": read_only,
    }


def _todo_tool_output(
    todos: list[TodoItem],
    *,
    changed: bool,
    read_only: bool,
) -> str:
    counts = todo_counts(todos)
    if read_only:
        prefix = "Current todo list"
    elif changed:
        prefix = "Todo list updated"
    else:
        prefix = "Todo list unchanged"
    return (
        f"{prefix}: {counts['completed']}/{counts['total']} completed. "
        "Continue the task without narrating this internal progress update unless it helps the user."
    )


def _trimmed_string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _extract_bash_sentinel(stdout: str, marker: str) -> tuple[str, Path | None, int | None]:
    start = stdout.rfind(f"\n{marker}CWD=")
    if start == -1:
        return stdout, None, None
    visible = stdout[:start]
    tail = stdout[start + 1 :].splitlines()
    cwd: Path | None = None
    exit_code: int | None = None
    for line in tail:
        if line.startswith(f"{marker}CWD="):
            cwd = Path(line.removeprefix(f"{marker}CWD=")).resolve()
        elif line.startswith(f"{marker}EXIT="):
            raw = line.removeprefix(f"{marker}EXIT=")
            if raw.isdigit():
                exit_code = int(raw)
    return visible, cwd, exit_code
