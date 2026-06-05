from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
from difflib import unified_diff
from pathlib import Path

from .constants import ATOMIC_RENAME_BACKOFF_SECONDS, ATOMIC_RENAME_RETRIES
from .shell_command import _detect_line_endings
from .tool_dataclasses import AtomicWriteResult, TextFileMetadata
from deepy.utils import json as json_utils


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


def _new_file_line_endings(path: Path, content: str) -> str:
    if "\r\n" in content:
        return "CRLF"
    if path.suffix.lower() in {".bat", ".cmd"}:
        return "CRLF"
    return "LF"


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

