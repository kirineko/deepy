from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


PNG_MIME = "image/png"
MAX_CLIPBOARD_BYTES = 32 * 1024 * 1024
IMAGE_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

RunBytes = Callable[[str, list[str]], bytes | None]
RunStatus = Callable[[str, list[str]], bool]


@dataclass(frozen=True)
class ClipboardImage:
    data_url: str
    mime_type: str


def buffer_to_data_url(data: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"


def is_image_file_path(value: str) -> bool:
    return Path(value.strip()).suffix.lower() in IMAGE_MIME_BY_EXT


def mime_type_for_path(value: str) -> str:
    return IMAGE_MIME_BY_EXT.get(Path(value.strip()).suffix.lower(), PNG_MIME)


def read_image_file(file_path: str | Path) -> ClipboardImage | None:
    path = Path(file_path).expanduser()
    if not is_image_file_path(str(path)):
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data:
        return None
    mime_type = mime_type_for_path(str(path))
    return ClipboardImage(data_url=buffer_to_data_url(data, mime_type), mime_type=mime_type)


def read_clipboard_image(
    *,
    platform: str | None = None,
    run_bytes: RunBytes | None = None,
    run_status: RunStatus | None = None,
) -> ClipboardImage | None:
    platform_name = platform or _platform_name()
    bytes_runner = run_bytes or _try_run_bytes
    status_runner = run_status or _try_run_status
    if platform_name == "darwin":
        return _read_macos_clipboard_image(bytes_runner, status_runner)
    if platform_name == "linux":
        return _read_linux_clipboard_image(bytes_runner)
    if platform_name == "win32":
        return _read_windows_clipboard_image(bytes_runner)
    return None


def _read_macos_clipboard_image(
    run_bytes: RunBytes,
    run_status: RunStatus,
) -> ClipboardImage | None:
    pngpaste = run_bytes("pngpaste", ["-"])
    if pngpaste:
        return ClipboardImage(data_url=buffer_to_data_url(pngpaste, PNG_MIME), mime_type=PNG_MIME)

    temp_dir = Path(tempfile.mkdtemp(prefix="deepy-clipboard-"))
    screenshot_path = temp_dir / "clipboard.png"
    try:
        saved = run_status(
            "osascript",
            [
                "-e",
                "set png_data to (the clipboard as «class PNGf»)",
                "-e",
                f'set fp to open for access POSIX file "{screenshot_path}" with write permission',
                "-e",
                "write png_data to fp",
                "-e",
                "close access fp",
            ],
        )
        if saved:
            image = read_image_file(screenshot_path)
            if image is not None:
                return image

        file_url = run_bytes(
            "osascript",
            ["-e", "get POSIX path of (the clipboard as «class furl»)"],
        )
        file_path = file_url.decode("utf-8", errors="replace").strip() if file_url else ""
        if file_path:
            return read_image_file(file_path)
        return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _read_linux_clipboard_image(run_bytes: RunBytes) -> ClipboardImage | None:
    xclip = run_bytes("xclip", ["-selection", "clipboard", "-t", "image/png", "-o"])
    if xclip:
        return ClipboardImage(data_url=buffer_to_data_url(xclip, PNG_MIME), mime_type=PNG_MIME)
    wl_paste = run_bytes("wl-paste", ["--type", "image/png"])
    if wl_paste:
        return ClipboardImage(data_url=buffer_to_data_url(wl_paste, PNG_MIME), mime_type=PNG_MIME)
    return None


def _read_windows_clipboard_image(run_bytes: RunBytes) -> ClipboardImage | None:
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$img = [System.Windows.Forms.Clipboard]::GetImage();"
        "if ($img) { $ms = New-Object System.IO.MemoryStream;"
        "$img.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png);"
        "[Console]::OpenStandardOutput().Write($ms.ToArray(), 0, $ms.Length); }"
    )
    output = run_bytes("powershell", ["-NoProfile", "-Command", script])
    if output:
        return ClipboardImage(data_url=buffer_to_data_url(output, PNG_MIME), mime_type=PNG_MIME)
    return None


def _try_run_bytes(command: str, args: list[str]) -> bytes | None:
    try:
        completed = subprocess.run(
            [command, *args],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0 or not completed.stdout:
        return None
    return completed.stdout[:MAX_CLIPBOARD_BYTES]


def _try_run_status(command: str, args: list[str]) -> bool:
    try:
        completed = subprocess.run(
            [command, *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _platform_name() -> str:
    import sys

    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform == "win32":
        return "win32"
    return sys.platform
