from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


SnapshotStatus = Literal["missing", "full", "partial", "deleted", "stale"]


@dataclass
class FileSnapshot:
    mtime_ns: int
    size: int
    full_read: bool


@dataclass
class FileSnippet:
    id: str
    path: Path
    start_line: int
    end_line: int
    text: str


@dataclass
class FileState:
    _snapshots: dict[Path, FileSnapshot] = field(default_factory=dict)
    _snippets: dict[str, FileSnippet] = field(default_factory=dict)
    _next_snippet_id: int = 0

    def mark_read(self, path: Path, *, full: bool = True) -> None:
        resolved = path.resolve()
        stat = resolved.stat()
        existing = self._snapshots.get(resolved)
        self._snapshots[resolved] = FileSnapshot(
            mtime_ns=stat.st_mtime_ns,
            size=stat.st_size,
            full_read=full or bool(existing and existing.full_read),
        )

    def check_writable(
        self,
        path: Path,
        *,
        require_read: bool = True,
        allow_partial: bool = False,
    ) -> tuple[bool, str | None]:
        resolved = path.resolve()
        snapshot = self._snapshots.get(resolved)
        if snapshot is None:
            if require_read and resolved.exists():
                return False, "File must be read before it can be modified."
            return True, None
        if require_read and not snapshot.full_read and not allow_partial:
            return False, "File must be read before it can be modified."
        if not resolved.exists():
            return False, "File changed since it was read: it no longer exists."
        stat = resolved.stat()
        if stat.st_mtime_ns != snapshot.mtime_ns or stat.st_size != snapshot.size:
            return False, "File changed since it was read; read it again before editing."
        return True, None

    def snapshot_status(self, path: Path) -> SnapshotStatus:
        resolved = path.resolve()
        snapshot = self._snapshots.get(resolved)
        if snapshot is None:
            return "missing"
        if not resolved.exists():
            return "deleted"
        stat = resolved.stat()
        if stat.st_mtime_ns != snapshot.mtime_ns or stat.st_size != snapshot.size:
            return "stale"
        return "full" if snapshot.full_read else "partial"

    def mark_written(self, path: Path) -> None:
        if path.exists():
            self.mark_read(path)

    def create_snippet(
        self,
        path: Path,
        *,
        start_line: int,
        end_line: int,
        text: str,
    ) -> FileSnippet:
        self._next_snippet_id += 1
        snippet = FileSnippet(
            id=f"snippet_{self._next_snippet_id}",
            path=path.resolve(),
            start_line=start_line,
            end_line=end_line,
            text=text,
        )
        self._snippets[snippet.id] = snippet
        return snippet

    def get_snippet(self, snippet_id: str) -> FileSnippet | None:
        return self._snippets.get(snippet_id)
