from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Literal

import pathspec
import regex as regex_lib


SearchMode = Literal["literal", "regex"]
SearchOutputMode = Literal["content", "files", "count"]

DEFAULT_SEARCH_LIMIT = 100
MAX_SEARCH_LIMIT = 500
DEFAULT_SEARCH_PATH = "."
DEFAULT_SEARCH_MODE: SearchMode = "literal"
DEFAULT_SEARCH_OUTPUT_MODE: SearchOutputMode = "content"
DEFAULT_CONTEXT_LINES = 0
MAX_CONTEXT_LINES = 5
MAX_SEARCH_FILE_BYTES = 2 * 1024 * 1024
MAX_SEARCH_OUTPUT_CHARS = 30_000
REGEX_TIMEOUT_SECONDS = 0.2
BINARY_SAMPLE_BYTES = 4096
VCS_DIRECTORY_NAMES = {".git", ".hg", ".svn", ".jj", ".sl", ".bzr"}
NOISY_DIRECTORY_NAMES = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "wheels",
}
SENSITIVE_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".netrc",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}
UNSUPPORTED_SEARCH_SUFFIXES = {
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


class SearchErrorCode:
    INVALID_ARGUMENTS = "invalid_arguments"
    PATH_POLICY = "path_policy"
    PATH_NOT_FOUND = "path_not_found"
    INVALID_REGEX = "invalid_regex"
    REGEX_TIMEOUT = "regex_timeout"


@dataclass(frozen=True)
class SearchRequest:
    query: str
    path: str = DEFAULT_SEARCH_PATH
    glob: str | None = None
    mode: SearchMode = DEFAULT_SEARCH_MODE
    output_mode: SearchOutputMode = DEFAULT_SEARCH_OUTPUT_MODE
    case_sensitive: bool = True
    context: int = DEFAULT_CONTEXT_LINES
    limit: int = DEFAULT_SEARCH_LIMIT
    offset: int = 0
    include_ignored: bool = False


@dataclass(frozen=True)
class SearchSkippedFile:
    path: str
    reason: str


@dataclass(frozen=True)
class SearchLineMatch:
    path: str
    line_number: int
    line: str
    before: tuple[tuple[int, str], ...] = ()
    after: tuple[tuple[int, str], ...] = ()
    match_count: int = 1


@dataclass(frozen=True)
class SearchFileMatch:
    path: str
    match_count: int
    line_matches: tuple[SearchLineMatch, ...] = ()


@dataclass(frozen=True)
class SearchPage:
    output: str
    metadata: dict[str, object]


@dataclass
class _SearchAccumulator:
    file_matches: list[SearchFileMatch] = field(default_factory=list)
    skipped: list[SearchSkippedFile] = field(default_factory=list)
    searched_files: int = 0
    scanned_bytes: int = 0
    sensitive_filtered: int = 0
    timed_out: bool = False


@dataclass(frozen=True)
class _TextMetadata:
    content: str
    encoding: str
    line_endings: str


def search_project(project_root: Path, request: SearchRequest) -> SearchPage:
    root = project_root.resolve(strict=False)
    target, error = _resolve_search_target(root, request.path)
    base_metadata: dict[str, object] = {
        "engine": "python",
        "mode": request.mode,
        "outputMode": request.output_mode,
        "query": request.query,
        "path": request.path,
        "glob": request.glob,
    }
    if error is not None or target is None:
        policy_denied = bool(error and ("outside" in error or "current project" in error))
        return SearchPage(
            "",
            {
                **base_metadata,
                "error_code": (
                    SearchErrorCode.PATH_POLICY
                    if policy_denied
                    else SearchErrorCode.PATH_NOT_FOUND
                ),
                "path": str(target) if target else request.path,
                "policyDecision": "deny" if policy_denied else "allow",
            },
        )

    validation_error = _validate_request(request)
    if validation_error is not None:
        return SearchPage("", {**base_metadata, **validation_error})

    matcher = _Matcher.from_request(request)
    if matcher.error is not None:
        return SearchPage("", {**base_metadata, **matcher.error})

    accumulator = _SearchAccumulator()
    ignore_spec = _load_ignore_spec(root) if not request.include_ignored else None
    for path in _iter_search_files(root, target, request, ignore_spec, accumulator):
        _search_file(root, path, request, matcher, accumulator)
        if accumulator.timed_out:
            break

    return _format_search_page(request, accumulator, base_metadata)


def _resolve_search_target(root: Path, raw_path: str) -> tuple[Path | None, str | None]:
    raw = Path(raw_path or DEFAULT_SEARCH_PATH).expanduser()
    candidate = raw if raw.is_absolute() else root / raw
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        return None, f"Could not resolve search path: {exc}"
    if not _is_relative_to(resolved, root):
        return resolved, "Search path must stay within the current project."
    if not resolved.exists():
        return resolved, f"Search path does not exist: {raw_path}"
    if not (resolved.is_dir() or resolved.is_file()):
        return resolved, f"Search path is not a file or directory: {raw_path}"
    return resolved, None


def _validate_request(request: SearchRequest) -> dict[str, object] | None:
    if not request.query:
        return {
            "error_code": SearchErrorCode.INVALID_ARGUMENTS,
            "error": '"query" must be a non-empty string.',
        }
    if request.mode not in ("literal", "regex"):
        return {
            "error_code": SearchErrorCode.INVALID_ARGUMENTS,
            "error": 'mode must be "literal" or "regex".',
        }
    if request.output_mode not in ("content", "files", "count"):
        return {
            "error_code": SearchErrorCode.INVALID_ARGUMENTS,
            "error": 'output_mode must be "content", "files", or "count".',
        }
    if request.offset < 0:
        return {
            "error_code": SearchErrorCode.INVALID_ARGUMENTS,
            "error": "offset must be greater than or equal to zero.",
        }
    if request.limit < 0:
        return {
            "error_code": SearchErrorCode.INVALID_ARGUMENTS,
            "error": "limit must be greater than or equal to zero.",
        }
    return None


@dataclass(frozen=True)
class _Matcher:
    request: SearchRequest
    pattern: Any = None
    needle: str = ""
    error: dict[str, object] | None = None

    @classmethod
    def from_request(cls, request: SearchRequest) -> "_Matcher":
        if request.mode == "literal":
            needle = request.query if request.case_sensitive else request.query.casefold()
            return cls(request=request, needle=needle)
        flags = 0 if request.case_sensitive else regex_lib.IGNORECASE
        try:
            pattern = regex_lib.compile(request.query, flags)
        except regex_lib.error as exc:
            return cls(
                request=request,
                error={
                    "error_code": SearchErrorCode.INVALID_REGEX,
                    "error": f"Invalid regex pattern: {exc}",
                },
            )
        return cls(request=request, pattern=pattern)

    def count_in_line(self, line: str) -> tuple[int, bool]:
        if self.request.mode == "literal":
            haystack = line if self.request.case_sensitive else line.casefold()
            return _count_literal(haystack, self.needle), False
        if self.pattern is None:
            return 0, False
        try:
            return (
                sum(1 for _ in self.pattern.finditer(line, timeout=REGEX_TIMEOUT_SECONDS)),
                False,
            )
        except TimeoutError:
            return 0, True


def _count_literal(haystack: str, needle: str) -> int:
    if not needle:
        return 0
    count = 0
    start = 0
    while True:
        index = haystack.find(needle, start)
        if index < 0:
            return count
        count += 1
        start = index + len(needle)


def _iter_search_files(
    root: Path,
    target: Path,
    request: SearchRequest,
    ignore_spec: pathspec.PathSpec | None,
    accumulator: _SearchAccumulator,
):
    if target.is_file():
        if _file_is_searchable(root, target, request, ignore_spec, accumulator):
            yield target
        return

    for current, dirnames, filenames in target.walk():
        dirnames[:] = sorted(
            [
                dirname
                for dirname in dirnames
                if _directory_is_searchable(
                    root,
                    current / dirname,
                    request,
                    ignore_spec,
                    accumulator,
                )
            ],
            key=str.casefold,
        )
        for filename in sorted(filenames, key=str.casefold):
            path = current / filename
            if _file_is_searchable(root, path, request, ignore_spec, accumulator):
                yield path


def _directory_is_searchable(
    root: Path,
    path: Path,
    request: SearchRequest,
    ignore_spec: pathspec.PathSpec | None,
    accumulator: _SearchAccumulator,
) -> bool:
    if path.name in VCS_DIRECTORY_NAMES:
        return False
    if not request.include_ignored and path.name in NOISY_DIRECTORY_NAMES:
        return False
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        _skip(root, path, accumulator, "path_error")
        return False
    if not _is_relative_to(resolved, root):
        _skip(root, path, accumulator, "path_policy")
        return False
    if ignore_spec is not None and _ignored_by_spec(root, path, True, ignore_spec):
        return False
    return True


def _file_is_searchable(
    root: Path,
    path: Path,
    request: SearchRequest,
    ignore_spec: pathspec.PathSpec | None,
    accumulator: _SearchAccumulator,
) -> bool:
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        _skip(root, path, accumulator, "path_error")
        return False
    if not _is_relative_to(resolved, root):
        _skip(root, path, accumulator, "path_policy")
        return False
    if request.glob and not fnmatch(_relative_path(root, path), request.glob):
        return False
    if ignore_spec is not None and _ignored_by_spec(root, path, False, ignore_spec):
        return False
    if _is_sensitive_path(path):
        accumulator.sensitive_filtered += 1
        _skip(root, path, accumulator, "sensitive")
        return False
    if path.suffix.lower() in UNSUPPORTED_SEARCH_SUFFIXES:
        _skip(root, path, accumulator, "unsupported")
        return False
    try:
        size = path.stat().st_size
    except OSError:
        _skip(root, path, accumulator, "stat_error")
        return False
    if size > MAX_SEARCH_FILE_BYTES:
        _skip(root, path, accumulator, "too_large")
        return False
    return True


def _search_file(
    root: Path,
    path: Path,
    request: SearchRequest,
    matcher: _Matcher,
    accumulator: _SearchAccumulator,
) -> None:
    try:
        data = path.read_bytes()
    except OSError:
        _skip(root, path, accumulator, "read_error")
        return
    encoding = _detect_text_encoding(data)
    if _looks_binary(data) and encoding != "utf16le":
        _skip(root, path, accumulator, "binary")
        return

    metadata = _read_text_metadata(data, encoding=encoding)
    accumulator.searched_files += 1
    accumulator.scanned_bytes += len(data)
    lines = metadata.content.splitlines()
    line_matches: list[SearchLineMatch] = []
    match_count = 0

    for index, line in enumerate(lines):
        count, timed_out = matcher.count_in_line(line)
        if timed_out:
            accumulator.timed_out = True
            return
        if count == 0:
            continue
        match_count += count
        if request.output_mode == "content":
            before_start = max(0, index - _context_limit(request.context))
            after_end = min(len(lines), index + _context_limit(request.context) + 1)
            before = tuple(
                (line_index + 1, lines[line_index])
                for line_index in range(before_start, index)
            )
            after = tuple(
                (line_index + 1, lines[line_index])
                for line_index in range(index + 1, after_end)
            )
            line_matches.append(
                SearchLineMatch(
                    path=_relative_path(root, path),
                    line_number=index + 1,
                    line=line,
                    before=before,
                    after=after,
                    match_count=count,
                )
            )

    if match_count > 0:
        accumulator.file_matches.append(
            SearchFileMatch(
                path=_relative_path(root, path),
                match_count=match_count,
                line_matches=tuple(line_matches),
            )
        )


def _format_search_page(
    request: SearchRequest,
    accumulator: _SearchAccumulator,
    base_metadata: dict[str, object],
) -> SearchPage:
    entries = _entries_for_mode(request, accumulator.file_matches)
    total_entries = len(entries)
    limit = _limit_value(request.limit)
    offset = request.offset
    page_entries = entries[offset:] if limit == 0 else entries[offset : offset + limit]
    output, output_truncated, visible_count = _render_entries(request, page_entries)
    next_offset = None
    if offset + visible_count < total_entries:
        next_offset = offset + visible_count
    total_matches = sum(item.match_count for item in accumulator.file_matches)
    metadata: dict[str, object] = {
        **base_metadata,
        "resultCount": visible_count,
        "totalResults": total_entries,
        "matchedFileCount": len(accumulator.file_matches),
        "totalMatches": total_matches,
        "searchedFiles": accumulator.searched_files,
        "scannedBytes": accumulator.scanned_bytes,
        "skippedFiles": len(accumulator.skipped),
        "sensitiveFiltered": accumulator.sensitive_filtered,
        "truncated": output_truncated or next_offset is not None,
        "timedOut": accumulator.timed_out,
        "offset": offset,
        "limit": limit,
    }
    if next_offset is not None:
        metadata["nextOffset"] = next_offset
    if accumulator.skipped:
        metadata["skipped"] = [
            {"path": skipped.path, "reason": skipped.reason}
            for skipped in accumulator.skipped[:20]
        ]
    if accumulator.timed_out:
        metadata["warning"] = "Regex search timed out; partial results returned."
        if not output:
            metadata["error_code"] = SearchErrorCode.REGEX_TIMEOUT
            return SearchPage(output="", metadata=metadata)
    if not output:
        output = "No matches found"
    elif metadata["truncated"]:
        output = (
            f"{output}\n\n"
            f"[Search results truncated. Use offset={metadata.get('nextOffset', offset + visible_count)} "
            "to continue.]"
        )
    return SearchPage(output=output, metadata=metadata)


def _entries_for_mode(
    request: SearchRequest,
    file_matches: list[SearchFileMatch],
) -> list[SearchFileMatch | SearchLineMatch]:
    if request.output_mode in {"files", "count"}:
        return list(file_matches)
    return [line for item in file_matches for line in item.line_matches]


def _render_entries(
    request: SearchRequest,
    entries: list[SearchFileMatch | SearchLineMatch],
) -> tuple[str, bool, int]:
    lines: list[str] = []
    visible = 0
    for entry in entries:
        rendered = _render_entry(request, entry)
        candidate = [*lines, *rendered]
        if len("\n".join(candidate)) > MAX_SEARCH_OUTPUT_CHARS:
            return "\n".join(lines), True, visible
        lines.extend(rendered)
        visible += 1
    return "\n".join(lines), False, visible


def _render_entry(
    request: SearchRequest,
    entry: SearchFileMatch | SearchLineMatch,
) -> list[str]:
    if request.output_mode == "files" and isinstance(entry, SearchFileMatch):
        return [entry.path]
    if request.output_mode == "count" and isinstance(entry, SearchFileMatch):
        return [f"{entry.path}:{entry.match_count}"]
    if isinstance(entry, SearchLineMatch):
        lines: list[str] = []
        for line_number, line in entry.before:
            lines.append(f"{entry.path}-{line_number}-{_truncate_search_line(line)}")
        lines.append(f"{entry.path}:{entry.line_number}:{_truncate_search_line(entry.line)}")
        for line_number, line in entry.after:
            lines.append(f"{entry.path}-{line_number}-{_truncate_search_line(line)}")
        return lines
    return []


def _limit_value(value: int) -> int:
    if value == 0:
        return 0
    return min(max(value, 1), MAX_SEARCH_LIMIT)


def _context_limit(value: int) -> int:
    return min(max(value, 0), MAX_CONTEXT_LINES)


def _load_ignore_spec(root: Path) -> pathspec.PathSpec:
    lines: list[str] = []
    for name in (".gitignore", ".ignore"):
        candidate = root / name
        if candidate.is_file():
            try:
                lines.extend(candidate.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                continue
    return pathspec.PathSpec.from_lines("gitignore", lines)


def _ignored_by_spec(root: Path, path: Path, is_dir: bool, spec: pathspec.PathSpec) -> bool:
    relative = _relative_path(root, path)
    candidates = [relative]
    if is_dir:
        candidates.append(relative.rstrip("/") + "/")
    return any(spec.match_file(candidate) for candidate in candidates)


def _skip(root: Path, path: Path, accumulator: _SearchAccumulator, reason: str) -> None:
    accumulator.skipped.append(SearchSkippedFile(path=_relative_path_or_name(root, path), reason=reason))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _relative_path_or_name(root: Path, path: Path) -> str:
    try:
        return _relative_path(root, path)
    except ValueError:
        return path.name


def _is_sensitive_path(path: Path) -> bool:
    name = path.name
    lower_name = name.lower()
    if lower_name in SENSITIVE_FILE_NAMES:
        return True
    if lower_name.endswith(".pem") or lower_name.endswith(".key"):
        return True
    return False


def _looks_binary(data: bytes) -> bool:
    return b"\x00" in data[:BINARY_SAMPLE_BYTES]


def _read_text_metadata(data: bytes, *, encoding: str | None = None) -> _TextMetadata:
    encoding = encoding or _detect_text_encoding(data)
    text = data.decode(_python_text_encoding(encoding), errors="replace")
    return _TextMetadata(
        content=text,
        encoding=encoding,
        line_endings="CRLF" if "\r\n" in text else "LF",
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


def _truncate_search_line(line: str, max_length: int = 500) -> str:
    if len(line) <= max_length:
        return line
    return line[:max_length] + "... [truncated]"
