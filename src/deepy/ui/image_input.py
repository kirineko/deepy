from __future__ import annotations

import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse

from deepy.llm.multimodal import (
    ImageAttachmentError,
    PromptImageAttachment,
    UNSUPPORTED_IMAGE_INPUT_MESSAGE,
    build_prompt_image_attachment,
    image_attachment_labels,
)


@dataclass(frozen=True)
class ClipboardImage:
    data: bytes
    mime_type: str


@dataclass(frozen=True)
class ImagePasteResult:
    handled: bool
    attachment: PromptImageAttachment | None = None
    notice: str = ""


ClipboardImageReader = Callable[[], ClipboardImage | None]
_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_PNG_HEADER = b"\x89PNG\r\n\x1a\n"
_JPEG_HEADER = b"\xff\xd8\xff"
_GIF_HEADERS = (b"GIF87a", b"GIF89a")
_WEBP_MARKER = b"WEBP"


@dataclass
class ImageAttachmentController:
    supports_image_input: bool
    clipboard_reader: ClipboardImageReader = field(default_factory=lambda: clipboard_image)
    attachments: list[PromptImageAttachment] = field(default_factory=list)
    status_message: str = ""

    def paste_from_clipboard(self) -> bool:
        return self.paste_image_from_clipboard().handled

    def paste_image_from_clipboard(self) -> ImagePasteResult:
        image = self.clipboard_reader()
        if image is None:
            return ImagePasteResult(handled=False)
        if not self.supports_image_input:
            self.status_message = ""
            return ImagePasteResult(handled=True, notice=UNSUPPORTED_IMAGE_INPUT_MESSAGE)
        try:
            attachment = self.attach_image(image.data, image.mime_type)
        except ImageAttachmentError as exc:
            self.status_message = ""
            return ImagePasteResult(handled=True, notice=str(exc))
        return ImagePasteResult(handled=True, attachment=attachment)

    def attach_image(self, data: bytes, mime_type: str) -> PromptImageAttachment:
        attachment = build_prompt_image_attachment(
            data=data,
            mime_type=mime_type,
            index=len(self.attachments) + 1,
        )
        self.attachments.append(attachment)
        self.status_message = ""
        return attachment

    def collect_and_reset(self) -> list[PromptImageAttachment]:
        attachments = list(self.attachments)
        self.attachments.clear()
        self.status_message = ""
        return attachments

    def collect_from_prompt_text(self, text: str) -> tuple[str, list[PromptImageAttachment]]:
        self.sync_to_prompt_text(text)
        attachments = list(self.attachments)
        cleaned_text = remove_image_attachment_labels(text, attachments).strip()
        self.clear()
        return cleaned_text, attachments

    def sync_to_prompt_text(self, text: str) -> bool:
        kept = [attachment for attachment in self.attachments if attachment.display_label in text]
        if len(kept) == len(self.attachments):
            return False
        self.attachments = kept
        return True

    def clear(self) -> None:
        self.attachments.clear()
        self.status_message = ""

    @property
    def labels(self) -> str:
        return image_attachment_labels(self.attachments)

    @property
    def display_status(self) -> str:
        return self.status_message


def remove_image_attachment_labels(
    text: str,
    attachments: list[PromptImageAttachment],
) -> str:
    cleaned = text
    for attachment in attachments:
        cleaned = cleaned.replace(attachment.display_label, "")
    return cleaned


def image_attachment_input_text(
    attachment: PromptImageAttachment,
    *,
    text_before_cursor: str = "",
    text_after_cursor: str = "",
) -> str:
    prefix = "" if not text_before_cursor or text_before_cursor[-1].isspace() else " "
    suffix = "" if not text_after_cursor or text_after_cursor[0].isspace() else " "
    return f"{prefix}{attachment.display_label}{suffix}"


def clipboard_image() -> ClipboardImage | None:
    system = platform.system()
    if system == "Darwin":
        return _macos_clipboard_image()
    if system == "Linux":
        return _linux_clipboard_image()
    if system == "Windows":
        return _windows_clipboard_image()
    return None


def _macos_clipboard_image() -> ClipboardImage | None:
    for reader in (
        _macos_clipboard_image_file,
        _macos_clipboard_png,
        _macos_clipboard_jpeg,
        _macos_clipboard_tiff_as_png,
    ):
        image = reader()
        if image is not None:
            return image
    return None


def _macos_clipboard_image_file() -> ClipboardImage | None:
    path = _macos_clipboard_file_path()
    if path is None:
        return None
    return _read_supported_image_file(path)


def _macos_clipboard_file_path() -> Path | None:
    completed = _run_osascript(
        [
            "try",
            "POSIX path of (the clipboard as alias)",
            "on error",
            'return ""',
            "end try",
        ],
        timeout=1.0,
    )
    if completed is None:
        return None
    path_text = completed.stdout.strip()
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_file() else None


def _read_supported_image_file(path: Path) -> ClipboardImage | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    detected = _detect_supported_image_mime(data)
    mime_type = detected or _IMAGE_MIME_BY_SUFFIX.get(path.suffix.lower())
    if mime_type is None:
        return None
    return ClipboardImage(data=data, mime_type=mime_type) if data else None


def _macos_clipboard_png() -> ClipboardImage | None:
    data = _macos_clipboard_data("PNGf")
    if data is None or not data.startswith(_PNG_HEADER):
        return None
    return ClipboardImage(data=data, mime_type="image/png")


def _macos_clipboard_jpeg() -> ClipboardImage | None:
    data = _macos_clipboard_data("JPEG")
    if data is None or not data.startswith(_JPEG_HEADER):
        return None
    return ClipboardImage(data=data, mime_type="image/jpeg")


def _macos_clipboard_tiff_as_png() -> ClipboardImage | None:
    data = _macos_clipboard_data("TIFF")
    if data is None:
        return None
    png = _convert_image_to_png_with_sips(data, ".tiff")
    if png is None:
        return None
    return ClipboardImage(data=png, mime_type="image/png")


def _macos_clipboard_data(class_code: str) -> bytes | None:
    completed = _run_osascript(
        [
            "try",
            f"the clipboard as «class {class_code}»",
            "on error",
            'return ""',
            "end try",
        ],
        timeout=1.0,
    )
    if completed is None:
        return None
    payload = completed.stdout.strip()
    if not payload:
        return None
    payload = re.sub(rf"^\s*«?data\s+{re.escape(class_code)}", "", payload, flags=re.IGNORECASE)
    match = re.search(r"([0-9A-Fa-f]{16,})", payload)
    if match is None:
        return None
    try:
        return bytes.fromhex(match.group(1))
    except ValueError:
        return None


def _run_osascript(lines: list[str], *, timeout: float) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["osascript", *[arg for line in lines for arg in ("-e", line)]],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return None


def _convert_image_to_png_with_sips(data: bytes, suffix: str) -> bytes | None:
    with tempfile.TemporaryDirectory(prefix="deepy-clipboard-image-") as tmp:
        input_path = Path(tmp) / f"clipboard{suffix}"
        output_path = Path(tmp) / "clipboard.png"
        try:
            input_path.write_bytes(data)
            completed = subprocess.run(
                ["sips", "-s", "format", "png", str(input_path), "--out", str(output_path)],
                check=False,
                capture_output=True,
                timeout=2.0,
            )
            if completed.returncode != 0 or not output_path.exists():
                return None
            png = output_path.read_bytes()
        except Exception:
            return None
    return png if png.startswith(_PNG_HEADER) else None


def _linux_clipboard_image() -> ClipboardImage | None:
    image = _linux_clipboard_image_file()
    if image is not None:
        return image
    return _linux_clipboard_image_data()


def _linux_clipboard_image_file() -> ClipboardImage | None:
    for command in _linux_clipboard_commands("text/uri-list"):
        completed = _run_clipboard_command(command, timeout=1.0)
        if completed is None or completed.returncode != 0 or not completed.stdout:
            continue
        path = _first_file_path_from_uri_list(completed.stdout.decode("utf-8", errors="ignore"))
        if path is None:
            continue
        image = _read_supported_image_file(path)
        if image is not None:
            return image
    return None


def _linux_clipboard_image_data() -> ClipboardImage | None:
    for mime_type in ("image/png", "image/jpeg", "image/webp", "image/gif", "image"):
        for command in _linux_clipboard_commands(mime_type):
            completed = _run_clipboard_command(command, timeout=1.0)
            if completed is None or completed.returncode != 0 or not completed.stdout:
                continue
            detected = _detect_supported_image_mime(completed.stdout)
            if detected is not None:
                return ClipboardImage(data=completed.stdout, mime_type=detected)
    return None


def _linux_clipboard_commands(mime_type: str) -> tuple[list[str], ...]:
    wl_command = ["wl-paste", "-t", mime_type]
    xclip_command = ["xclip", "-selection", "clipboard", "-t", mime_type, "-o"]
    if platform.system() != "Linux":
        return ()
    if _linux_prefers_wayland():
        candidates = (wl_command, xclip_command)
    else:
        candidates = (xclip_command, wl_command)
    return tuple(command for command in candidates if shutil.which(command[0]) is not None)


def _linux_prefers_wayland() -> bool:
    return bool(_env("WAYLAND_DISPLAY"))


def _env(name: str) -> str | None:
    try:
        import os

        return os.getenv(name)
    except Exception:
        return None


def _run_clipboard_command(
    command: list[str],
    *,
    timeout: float,
) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=timeout,
        )
    except Exception:
        return None


def _first_file_path_from_uri_list(text: str) -> Path | None:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("file://"):
            parsed = urlparse(line)
            path = Path(unquote(parsed.path))
        else:
            path = Path(unquote(line))
        if path.is_file():
            return path
    return None


def _windows_clipboard_image() -> ClipboardImage | None:
    image = _windows_clipboard_image_file()
    if image is not None:
        return image
    return _windows_clipboard_png()


def _windows_clipboard_image_file() -> ClipboardImage | None:
    completed = _run_powershell(
        """
        Add-Type -AssemblyName System.Windows.Forms
        $files = [System.Windows.Forms.Clipboard]::GetFileDropList()
        foreach ($file in $files) { Write-Output $file }
        """,
        timeout=2.0,
    )
    if completed is None or completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        path = Path(line.strip())
        if not path.is_file():
            continue
        image = _read_supported_image_file(path)
        if image is not None:
            return image
    return None


def _windows_clipboard_png() -> ClipboardImage | None:
    with tempfile.TemporaryDirectory(prefix="deepy-clipboard-image-") as tmp:
        output_path = Path(tmp) / "clipboard.png"
        completed = _run_powershell(
            """
            Add-Type -AssemblyName System.Windows.Forms
            Add-Type -AssemblyName System.Drawing
            if ([System.Windows.Forms.Clipboard]::ContainsImage()) {
                $image = [System.Windows.Forms.Clipboard]::GetImage()
                if ($null -ne $image) {
                    $image.Save($args[0], [System.Drawing.Imaging.ImageFormat]::Png)
                    $image.Dispose()
                    Write-Output $args[0]
                }
            }
            """,
            str(output_path),
            timeout=2.0,
        )
        if completed is None or completed.returncode != 0 or not output_path.exists():
            return None
        try:
            data = output_path.read_bytes()
        except OSError:
            return None
    if not data.startswith(_PNG_HEADER):
        return None
    return ClipboardImage(data=data, mime_type="image/png")


def _run_powershell(
    script: str,
    *args: str,
    timeout: float,
) -> subprocess.CompletedProcess[str] | None:
    executable = _powershell_executable()
    if executable is None:
        return None
    command = [
        executable,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
    ]
    if Path(executable).name.lower() == "powershell.exe":
        command.append("-Sta")
    command.extend(["-Command", script, *args])
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return None


def _powershell_executable() -> str | None:
    for name in ("powershell.exe", "powershell", "pwsh"):
        executable = shutil.which(name)
        if executable is not None:
            return executable
    return None


def _detect_supported_image_mime(data: bytes) -> str | None:
    if data.startswith(_PNG_HEADER):
        return "image/png"
    if data.startswith(_JPEG_HEADER):
        return "image/jpeg"
    if data.startswith(_GIF_HEADERS):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == _WEBP_MARKER:
        return "image/webp"
    return None
