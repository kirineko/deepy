from __future__ import annotations

import base64
from pathlib import Path

from deepy.ui.clipboard import ClipboardImage
from deepy.ui.clipboard import buffer_to_data_url
from deepy.ui.clipboard import is_image_file_path
from deepy.ui.clipboard import mime_type_for_path
from deepy.ui.clipboard import read_clipboard_image
from deepy.ui.clipboard import read_image_file


def test_buffer_to_data_url_encodes_bytes():
    assert buffer_to_data_url(b"fakepng", "image/png") == (
        f"data:image/png;base64,{base64.b64encode(b'fakepng').decode('ascii')}"
    )


def test_image_path_helpers_handle_supported_extensions():
    assert is_image_file_path("/tmp/a.PNG")
    assert is_image_file_path("/tmp/a.jpeg")
    assert not is_image_file_path("/tmp/a.txt")
    assert mime_type_for_path("/tmp/a.webp") == "image/webp"
    assert mime_type_for_path("/tmp/a.unknown") == "image/png"


def test_read_image_file_returns_none_for_missing_or_non_image(tmp_path):
    assert read_image_file(tmp_path / "missing.png") is None
    text = tmp_path / "a.txt"
    text.write_text("hello", encoding="utf-8")
    assert read_image_file(text) is None


def test_read_image_file_builds_data_url(tmp_path):
    image = tmp_path / "a.png"
    image.write_bytes(b"fakepng")

    result = read_image_file(image)

    assert result == ClipboardImage(
        data_url=buffer_to_data_url(b"fakepng", "image/png"),
        mime_type="image/png",
    )


def test_read_clipboard_image_returns_none_when_no_helpers():
    assert read_clipboard_image(
        platform="linux",
        run_bytes=lambda _command, _args: None,
    ) is None


def test_read_clipboard_image_uses_pngpaste_on_macos():
    def run_bytes(command: str, args: list[str]) -> bytes | None:
        if command == "pngpaste" and args == ["-"]:
            return b"fakepng"
        return None

    result = read_clipboard_image(
        platform="darwin",
        run_bytes=run_bytes,
        run_status=lambda _command, _args: False,
    )

    assert result == ClipboardImage(
        data_url=buffer_to_data_url(b"fakepng", "image/png"),
        mime_type="image/png",
    )


def test_read_clipboard_image_uses_osascript_fallback_on_macos():
    def run_status(command: str, args: list[str]) -> bool:
        assert command == "osascript"
        for arg in args:
            if "POSIX file" in arg:
                path = arg.split('"')[1]
                Path(path).write_bytes(b"fakepng")
                return True
        return False

    result = read_clipboard_image(
        platform="darwin",
        run_bytes=lambda _command, _args: None,
        run_status=run_status,
    )

    assert result == ClipboardImage(
        data_url=buffer_to_data_url(b"fakepng", "image/png"),
        mime_type="image/png",
    )


def test_read_clipboard_image_uses_file_url_fallback_on_macos(tmp_path):
    image = tmp_path / "clipboard.jpg"
    image.write_bytes(b"fakejpg")

    def run_bytes(command: str, args: list[str]) -> bytes | None:
        if command == "osascript" and args == ["-e", "get POSIX path of (the clipboard as «class furl»)"]:
            return str(image).encode("utf-8")
        return None

    result = read_clipboard_image(
        platform="darwin",
        run_bytes=run_bytes,
        run_status=lambda _command, _args: False,
    )

    assert result == ClipboardImage(
        data_url=buffer_to_data_url(b"fakejpg", "image/jpeg"),
        mime_type="image/jpeg",
    )


def test_read_clipboard_image_uses_linux_helpers_in_order():
    calls: list[str] = []

    def run_bytes(command: str, _args: list[str]) -> bytes | None:
        calls.append(command)
        return b"fakepng" if command == "wl-paste" else None

    result = read_clipboard_image(platform="linux", run_bytes=run_bytes)

    assert calls == ["xclip", "wl-paste"]
    assert result == ClipboardImage(
        data_url=buffer_to_data_url(b"fakepng", "image/png"),
        mime_type="image/png",
    )


def test_read_clipboard_image_uses_windows_powershell():
    def run_bytes(command: str, args: list[str]) -> bytes | None:
        assert command == "powershell"
        assert args[:2] == ["-NoProfile", "-Command"]
        return b"fakepng"

    result = read_clipboard_image(platform="win32", run_bytes=run_bytes)

    assert result == ClipboardImage(
        data_url=buffer_to_data_url(b"fakepng", "image/png"),
        mime_type="image/png",
    )
