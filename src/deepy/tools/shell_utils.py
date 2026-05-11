from __future__ import annotations

import re


ShellKind = str
NUL_REDIRECT_RE = re.compile(r"(\d?&?>+\s*)[Nn][Uu][Ll](?=\s|$|[|&;)\n])")


def get_shell_kind(shell_path: str) -> ShellKind:
    executable = shell_path.replace("\\", "/").split("/")[-1].lower()
    if executable in {"bash", "bash.exe"}:
        return "bash"
    if executable in {"zsh", "zsh.exe"}:
        return "zsh"
    return "unknown"


def build_shell_init_command(shell_path: str) -> str | None:
    kind = get_shell_kind(shell_path)
    if kind == "zsh":
        return 'ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"; if [ -f "$ZSHRC" ]; then . "$ZSHRC"; fi'
    if kind == "bash":
        return 'BASHRC="${BASH_ENV:-$HOME/.bashrc}"; if [ -f "$BASHRC" ]; then . "$BASHRC"; fi'
    return None


def build_disable_extglob_command(shell_path: str) -> str | None:
    kind = get_shell_kind(shell_path)
    if kind == "bash":
        return "shopt -u extglob 2>/dev/null || true"
    if kind == "zsh":
        return "setopt NO_EXTENDED_GLOB 2>/dev/null || true"
    return None


def rewrite_windows_null_redirect(command: str) -> str:
    return NUL_REDIRECT_RE.sub(r"\1/dev/null", command)


def windows_path_to_posix_path(windows_path: str) -> str:
    if windows_path.startswith("\\\\"):
        return windows_path.replace("\\", "/")
    drive_match = re.match(r"^([A-Za-z]):[/\\]", windows_path)
    if drive_match:
        drive_letter = drive_match.group(1).lower()
        return f"/{drive_letter}{windows_path[2:].replace('\\', '/')}"
    return windows_path.replace("\\", "/")


def posix_path_to_windows_path(posix_path: str) -> str:
    if posix_path.startswith("//"):
        return posix_path.replace("/", "\\")

    cygdrive_match = re.match(r"^/cygdrive/([A-Za-z])(/|$)", posix_path)
    if cygdrive_match:
        drive_letter = cygdrive_match.group(1).upper()
        rest = posix_path[len(f"/cygdrive/{cygdrive_match.group(1)}") :]
        return f"{drive_letter}:{(rest or '\\').replace('/', '\\')}"

    drive_match = re.match(r"^/([A-Za-z])(/|$)", posix_path)
    if drive_match:
        drive_letter = drive_match.group(1).upper()
        rest = posix_path[2:]
        return f"{drive_letter}:{(rest or '\\').replace('/', '\\')}"

    return posix_path.replace("/", "\\")


def normalize_file_path(path: str, platform: str) -> str:
    if platform == "win32":
        return posix_path_to_windows_path(path)
    return path


def is_absolute_file_path(path: str, platform: str) -> bool:
    if platform == "win32":
        if re.match(r"^[A-Za-z]:[/\\]", path):
            return True
        if path.startswith("\\\\"):
            return True
        return bool(re.match(r"^/(?:cygdrive/)?[A-Za-z](?:/|$)", path))
    return path.startswith("/")
