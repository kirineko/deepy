from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileSnapshot:
    mtime_ns: int
    size: int


@dataclass
class FileState:
    _snapshots: dict[Path, FileSnapshot] = field(default_factory=dict)

    def mark_read(self, path: Path) -> None:
        resolved = path.resolve()
        stat = resolved.stat()
        self._snapshots[resolved] = FileSnapshot(mtime_ns=stat.st_mtime_ns, size=stat.st_size)

    def check_writable(self, path: Path, *, require_read: bool = True) -> tuple[bool, str | None]:
        resolved = path.resolve()
        snapshot = self._snapshots.get(resolved)
        if snapshot is None:
            if require_read and resolved.exists():
                return False, "File must be read before it can be modified."
            return True, None
        if not resolved.exists():
            return False, "File changed since it was read: it no longer exists."
        stat = resolved.stat()
        if stat.st_mtime_ns != snapshot.mtime_ns or stat.st_size != snapshot.size:
            return False, "File changed since it was read; read it again before editing."
        return True, None

    def mark_written(self, path: Path) -> None:
        if path.exists():
            self.mark_read(path)
