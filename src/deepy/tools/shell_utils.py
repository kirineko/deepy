from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
import re
import sys


ShellKind = str
NUL_REDIRECT_RE = re.compile(r"(\d?&?>+\s*)[Nn][Uu][Ll](?=\s|$|[|&;)\n])")


@dataclass(frozen=True)
class RuntimeEnvironment:
    os_family: str
    shell_kind: ShellKind
    command_dialect: str
    path_style: str
    shell_path: str


def get_shell_kind(shell_path: str) -> ShellKind:
    executable = shell_path.replace("\\", "/").split("/")[-1].lower()
    if executable in {"pwsh", "pwsh.exe", "powershell", "powershell.exe"}:
        return "powershell"
    if executable in {"cmd", "cmd.exe"}:
        return "cmd"
    if executable in {"bash", "bash.exe"}:
        return "bash"
    if executable in {"zsh", "zsh.exe"}:
        return "zsh"
    return "unknown"


def detect_runtime_environment(
    *,
    shell_path: str | None = None,
    env: Mapping[str, str] | None = None,
    platform_name: str | None = None,
    os_name: str | None = None,
) -> RuntimeEnvironment:
    environment = env or os.environ
    resolved_platform = platform_name or sys.platform
    resolved_os_name = os_name or os.name
    os_family = _detect_os_family(resolved_platform, resolved_os_name)
    resolved_shell = shell_path or _detect_shell_path(environment, os_family)
    shell_kind = get_shell_kind(resolved_shell) if resolved_shell else "unknown"
    if shell_kind == "unknown" and os_family == "windows" and "PSModulePath" in environment:
        shell_kind = "powershell"
        resolved_shell = resolved_shell or "powershell.exe"
    command_dialect = _command_dialect(shell_kind)
    path_style = _path_style(os_family, shell_kind)
    return RuntimeEnvironment(
        os_family=os_family,
        shell_kind=shell_kind,
        command_dialect=command_dialect,
        path_style=path_style,
        shell_path=resolved_shell or "unknown",
    )


def _detect_os_family(platform_name: str, os_name: str) -> str:
    normalized = platform_name.lower()
    if os_name == "nt" or normalized.startswith(("win32", "cygwin", "msys")):
        return "windows"
    if normalized == "darwin":
        return "macos"
    if normalized.startswith("linux"):
        return "linux"
    return "unknown"


def _detect_shell_path(env: Mapping[str, str], os_family: str) -> str:
    shell = env.get("SHELL") or ""
    if shell:
        return shell
    if os_family == "windows" and "PSModulePath" in env:
        return env.get("POWERSHELL") or "powershell.exe"
    return env.get("COMSPEC") or env.get("ComSpec") or ""


def _command_dialect(shell_kind: ShellKind) -> str:
    if shell_kind == "powershell":
        return "powershell"
    if shell_kind == "cmd":
        return "cmd"
    if shell_kind in {"bash", "zsh"}:
        return "posix"
    return "unknown"


def _path_style(os_family: str, shell_kind: ShellKind) -> str:
    if shell_kind in {"bash", "zsh"}:
        return "posix"
    if os_family == "windows":
        return "windows"
    if os_family in {"linux", "macos"}:
        return "posix"
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
