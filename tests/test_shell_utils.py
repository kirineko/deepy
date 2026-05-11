from __future__ import annotations

from deepy.tools.shell_utils import build_disable_extglob_command
from deepy.tools.shell_utils import build_shell_init_command
from deepy.tools.shell_utils import get_shell_kind
from deepy.tools.shell_utils import is_absolute_file_path
from deepy.tools.shell_utils import normalize_file_path
from deepy.tools.shell_utils import posix_path_to_windows_path
from deepy.tools.shell_utils import rewrite_windows_null_redirect
from deepy.tools.shell_utils import windows_path_to_posix_path


def test_windows_paths_convert_to_git_bash_posix_paths():
    assert windows_path_to_posix_path(r"C:\Users\foo") == "/c/Users/foo"
    assert windows_path_to_posix_path(r"d:\IdeaProjects\guesswho-api") == (
        "/d/IdeaProjects/guesswho-api"
    )
    assert windows_path_to_posix_path(r"\\server\share\dir") == "//server/share/dir"


def test_git_bash_posix_paths_convert_to_native_windows_paths():
    assert posix_path_to_windows_path("/c/Users/foo") == r"C:\Users\foo"
    assert posix_path_to_windows_path("/cygdrive/d/IdeaProjects/guesswho-api") == (
        r"D:\IdeaProjects\guesswho-api"
    )
    assert posix_path_to_windows_path("//server/share/dir") == r"\\server\share\dir"


def test_windows_nul_redirects_are_rewritten_for_posix_bash():
    assert rewrite_windows_null_redirect("cmd >nul") == "cmd >/dev/null"
    assert rewrite_windows_null_redirect("cmd 2>NUL && next") == "cmd 2>/dev/null && next"
    assert rewrite_windows_null_redirect("cmd &>nul\nnext") == "cmd &>/dev/null\nnext"
    assert rewrite_windows_null_redirect("echo nullable") == "echo nullable"


def test_shell_kind_detection_supports_windows_bash_paths():
    assert get_shell_kind(r"C:\Program Files\Git\bin\bash.exe") == "bash"
    assert get_shell_kind("/bin/zsh") == "zsh"
    assert get_shell_kind("/usr/bin/fish") == "unknown"
    assert build_disable_extglob_command(r"C:\Program Files\Git\bin\bash.exe") == (
        "shopt -u extglob 2>/dev/null || true"
    )
    assert build_disable_extglob_command("/bin/zsh") == "setopt NO_EXTENDED_GLOB 2>/dev/null || true"


def test_shell_init_command_sources_bash_or_zsh_rc():
    assert build_shell_init_command("/bin/zsh") is not None
    assert ".zshrc" in build_shell_init_command("/bin/zsh")
    assert build_shell_init_command("/bin/bash") is not None
    assert ".bashrc" in build_shell_init_command("/bin/bash")
    assert build_shell_init_command("/usr/bin/fish") is None


def test_file_path_normalization_converts_git_bash_drive_paths_on_windows():
    assert normalize_file_path("/d/IdeaProjects/guesswho-api/API_DOCUMENTATION.md", "win32") == (
        r"D:\IdeaProjects\guesswho-api\API_DOCUMENTATION.md"
    )
    assert normalize_file_path("/cygdrive/c/Users/foo/file.txt", "win32") == (
        r"C:\Users\foo\file.txt"
    )
    assert normalize_file_path("/dev/null", "win32") == r"\dev\null"


def test_file_absolute_checks_accept_git_bash_drive_paths_on_windows():
    assert is_absolute_file_path("/d/IdeaProjects/guesswho-api/API_DOCUMENTATION.md", "win32")
    assert is_absolute_file_path("D:/IdeaProjects/guesswho-api/API_DOCUMENTATION.md", "win32")
    assert not is_absolute_file_path("/dev/null", "win32")
    assert not is_absolute_file_path("./API_DOCUMENTATION.md", "win32")
    assert is_absolute_file_path("/tmp/file", "linux")
