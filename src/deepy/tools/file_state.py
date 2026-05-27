from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


SnapshotStatus = Literal["missing", "full", "partial", "deleted", "stale"]


@dataclass
class FileSnapshot:
    id: str
    token: int
    mtime_ns: int
    size: int
    content_hash: str
    full_read: bool
    encoding: str | None = None
    line_endings: str | None = None


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
    _next_snapshot_id: int = 0

    def mark_read(
        self,
        path: Path,
        *,
        full: bool = True,
        encoding: str | None = None,
        line_endings: str | None = None,
    ) -> FileSnapshot:
        resolved = path.resolve()
        stat = resolved.stat()
        existing = self._snapshots.get(resolved)
        self._next_snapshot_id += 1
        snapshot = FileSnapshot(
            id=f"snapshot_{self._next_snapshot_id}",
            token=self._next_snapshot_id,
            mtime_ns=stat.st_mtime_ns,
            size=stat.st_size,
            content_hash=_file_sha256(resolved),
            full_read=full or bool(existing and existing.full_read),
            encoding=encoding,
            line_endings=line_endings,
        )
        self._snapshots[resolved] = snapshot
        return snapshot

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
        if (
            stat.st_mtime_ns != snapshot.mtime_ns
            or stat.st_size != snapshot.size
            or _file_sha256(resolved) != snapshot.content_hash
        ):
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
        if (
            stat.st_mtime_ns != snapshot.mtime_ns
            or stat.st_size != snapshot.size
            or _file_sha256(resolved) != snapshot.content_hash
        ):
            return "stale"
        return "full" if snapshot.full_read else "partial"

    def mark_written(
        self,
        path: Path,
        *,
        encoding: str | None = None,
        line_endings: str | None = None,
    ) -> FileSnapshot | None:
        if path.exists():
            return self.mark_read(path, encoding=encoding, line_endings=line_endings)
        return None

    def discard_snapshot(self, path: Path) -> None:
        self._snapshots.pop(path.resolve(), None)

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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
