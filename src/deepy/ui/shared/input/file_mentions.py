from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document


DEFAULT_FILE_MENTION_LIMIT = 1000
DEFAULT_FILE_MENTION_REFRESH_INTERVAL = 2.0

_IGNORED_NAMES = frozenset(
    {
        ".DS_Store",
        ".bzr",
        ".git",
        ".hg",
        ".svn",
        ".build",
        ".cache",
        ".coverage",
        ".gradle",
        ".idea",
        ".ipynb_checkpoints",
        ".mypy_cache",
        ".next",
        ".nuxt",
        ".parcel-cache",
        ".pnpm-store",
        ".pytest_cache",
        ".ruff_cache",
        ".svelte-kit",
        ".tox",
        ".turbo",
        ".venv",
        ".vercel",
        ".vs",
        ".vscode",
        ".yarn",
        ".yarn-cache",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "node_modules",
        "out",
        "target",
        "tmp",
        "venv",
        "vendor",
    }
)
_IGNORED_PATTERNS = re.compile(
    r"|".join(
        (
            r".*_cache$",
            r".*-cache$",
            r".*\.egg-info$",
            r".*\.dist-info$",
            r".*\.py[co]$",
            r".*\.class$",
            r".*\.sw[po]$",
            r".*~$",
            r".*\.(?:tmp|bak)$",
        )
    ),
    re.IGNORECASE,
)
_TRIGGER_GUARDS = frozenset((".", "-", "_", "`", "'", '"', ":", "@", "#", "~"))


@dataclass(frozen=True)
class FileMentionFragment:
    fragment: str
    start: int


@dataclass(frozen=True)
class _CacheEntry:
    timestamp: float
    paths: tuple[str, ...]


def is_ignored_file_mention_name(name: str) -> bool:
    if not name:
        return True
    if name in _IGNORED_NAMES:
        return True
    return bool(_IGNORED_PATTERNS.fullmatch(name))


def extract_file_mention_fragment(text_before_cursor: str) -> FileMentionFragment | None:
    index = text_before_cursor.rfind("@")
    if index == -1:
        return None

    if index > 0:
        previous = text_before_cursor[index - 1]
        if previous.isalnum() or previous in _TRIGGER_GUARDS:
            return None

    fragment = text_before_cursor[index + 1 :]
    if any(char.isspace() for char in fragment):
        return None
    return FileMentionFragment(fragment=fragment, start=index + 1)


def rank_file_mention_candidates(paths: Iterable[str], fragment: str) -> list[str]:
    query = fragment.casefold()
    ranked: list[tuple[tuple[int, int, int], int, str]] = []

    for index, path in enumerate(paths):
        score = _candidate_score(path, query)
        if score is None:
            continue
        ranked.append((score, index, path))

    ranked.sort(key=lambda item: (item[0], item[1]))
    return [path for _, _, path in ranked]


class FileMentionDiscovery:
    def __init__(
        self,
        root: Path,
        *,
        limit: int = DEFAULT_FILE_MENTION_LIMIT,
        refresh_interval: float = DEFAULT_FILE_MENTION_REFRESH_INTERVAL,
    ) -> None:
        self.root = root.resolve()
        self.limit = max(1, limit)
        self.refresh_interval = max(0.0, refresh_interval)
        self._top_cache: _CacheEntry | None = None
        self._deep_cache: dict[str, _CacheEntry] = {}

    def top_level_paths(self) -> list[str]:
        cached = self._valid_cache(self._top_cache)
        if cached is not None:
            return cached

        paths: list[str] = []
        try:
            entries = sorted(self.root.iterdir(), key=lambda path: path.name.casefold())
            for entry in entries:
                if len(paths) >= self.limit:
                    break
                name = entry.name
                if (
                    entry.is_symlink()
                    or _path_contains_whitespace(name)
                    or is_ignored_file_mention_name(name)
                ):
                    continue
                paths.append(_format_entry(self.root, entry))
        except OSError:
            paths = []

        self._top_cache = _CacheEntry(time.monotonic(), tuple(paths))
        return list(paths)

    def deep_paths(self, scope: str | None = None) -> list[str]:
        cache_key = scope or ""
        cached = self._valid_cache(self._deep_cache.get(cache_key))
        if cached is not None:
            return cached

        walk_root = self._resolve_scope(scope)
        if walk_root is None or not walk_root.is_dir():
            paths: list[str] = []
        else:
            paths = self._walk_paths(walk_root)

        self._deep_cache[cache_key] = _CacheEntry(time.monotonic(), tuple(paths))
        return list(paths)

    def is_existing_file(self, fragment: str) -> bool:
        candidate = fragment.rstrip("/")
        if not candidate:
            return False
        resolved = self._resolve_scope(candidate)
        if resolved is None:
            return False
        try:
            return resolved.is_file()
        except OSError:
            return False

    def _walk_paths(self, walk_root: Path) -> list[str]:
        paths: list[str] = []
        try:
            for current_root, dirs, files in os.walk(walk_root, followlinks=False):
                current_path = Path(current_root)
                dirs[:] = [
                    name
                    for name in sorted(dirs, key=str.casefold)
                    if self._include_directory(current_path / name)
                ]

                relative_root = current_path.resolve().relative_to(self.root)
                if relative_root.parts:
                    paths.append(relative_root.as_posix() + "/")
                    if len(paths) >= self.limit:
                        break

                for file_name in sorted(files, key=str.casefold):
                    if len(paths) >= self.limit:
                        break
                    file_path = current_path / file_name
                    if (
                        file_path.is_symlink()
                        or _path_contains_whitespace(file_name)
                        or is_ignored_file_mention_name(file_name)
                    ):
                        continue
                    relative = (relative_root / file_name).as_posix()
                    if relative:
                        paths.append(relative)

                if len(paths) >= self.limit:
                    break
        except (OSError, ValueError):
            return paths
        return paths

    def _include_directory(self, path: Path) -> bool:
        name = path.name
        if _path_contains_whitespace(name) or is_ignored_file_mention_name(name):
            return False
        try:
            return path.is_dir() and not path.is_symlink()
        except OSError:
            return False

    def _resolve_scope(self, scope: str | None) -> Path | None:
        try:
            target = (self.root / scope).resolve() if scope else self.root
            if not target.is_relative_to(self.root):
                return None
            return target
        except (OSError, ValueError):
            return None

    def _valid_cache(self, entry: _CacheEntry | None) -> list[str] | None:
        if entry is None:
            return None
        if time.monotonic() - entry.timestamp > self.refresh_interval:
            return None
        return list(entry.paths)


class FileMentionCompleter(Completer):
    def __init__(
        self,
        root: Path,
        *,
        limit: int = DEFAULT_FILE_MENTION_LIMIT,
        refresh_interval: float = DEFAULT_FILE_MENTION_REFRESH_INTERVAL,
    ) -> None:
        self._discovery = FileMentionDiscovery(
            root,
            limit=limit,
            refresh_interval=refresh_interval,
        )

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
    ) -> Iterable[Completion]:
        mention = extract_file_mention_fragment(document.text_before_cursor)
        if mention is None:
            return
        fragment = mention.fragment
        if self._discovery.is_existing_file(fragment):
            return

        paths = self._paths_for_fragment(fragment)
        for path in rank_file_mention_candidates(paths, fragment):
            yield Completion(
                path,
                start_position=-len(fragment),
                display=path,
                display_meta="dir" if path.endswith("/") else "file",
            )

    def _paths_for_fragment(self, fragment: str) -> list[str]:
        if "/" not in fragment and not fragment:
            return self._discovery.top_level_paths()
        scope = fragment.rsplit("/", 1)[0] if "/" in fragment else None
        return self._discovery.deep_paths(scope)


def _candidate_score(path: str, query: str) -> tuple[int, int, int] | None:
    if not query:
        return (0, path.count("/"), len(path))

    candidate = path.casefold()
    basename = candidate.rstrip("/").rsplit("/", 1)[-1]
    if "/" in query:
        if candidate.startswith(query):
            return (0, path.count("/"), len(path))
        if query in candidate:
            return (1, path.count("/"), len(path))
        if _is_subsequence(query, candidate):
            return (2, path.count("/"), len(path))
        return None

    if basename.startswith(query):
        return (0, path.count("/"), len(path))
    if query in basename:
        return (1, path.count("/"), len(path))
    if candidate.startswith(query):
        return (2, path.count("/"), len(path))
    if query in candidate:
        return (3, path.count("/"), len(path))
    if _is_subsequence(query, candidate):
        return (4, path.count("/"), len(path))
    return None


def _is_subsequence(needle: str, haystack: str) -> bool:
    if not needle:
        return True
    iterator = iter(haystack)
    return all(char in iterator for char in needle)


def _format_entry(root: Path, entry: Path) -> str:
    relative = entry.relative_to(root).as_posix()
    try:
        is_directory = entry.is_dir() and not entry.is_symlink()
    except OSError:
        is_directory = False
    return f"{relative}/" if is_directory else relative


def _path_contains_whitespace(value: str) -> bool:
    return any(char.isspace() for char in value)
