from __future__ import annotations

import json
import shlex
import sys

from deepy.tools import ToolRuntime


def decode(payload: str) -> dict:
    return json.loads(payload)


def read_v3(
    runtime: ToolRuntime,
    path: str,
    start_line: int = 1,
    limit: int | None = None,
    pages: str | None = None,
) -> str:
    request: dict[str, object] = {"path": path}
    if start_line != 1:
        request["offset"] = start_line
    if limit is not None:
        request["limit"] = limit
    if pages is not None:
        request["pages"] = pages
    return runtime.read(request)


def write_v3(
    runtime: ToolRuntime,
    path: str,
    content: object,
    *,
    overwrite: bool = True,
    **_: object,
) -> str:
    return runtime.write_v3(path, content, overwrite=overwrite)


def update_v3(
    runtime: ToolRuntime,
    path: str | None,
    old: str,
    new: str,
    replace_all: bool = False,
    expected_occurrences: int | None = None,
    **_: object,
) -> str:
    request: dict[str, object] = {
        "path": path,
        "old": old,
        "new": new,
        "replace_all": replace_all,
    }
    if expected_occurrences is not None:
        request["expected_occurrences"] = expected_occurrences
    return runtime.update(request)


def preflight_v3(runtime: ToolRuntime, name: str, arguments: dict[str, object]) -> dict:
    return runtime.preflight_file_mutation(name, json.dumps(arguments))


def repeat_x_command(count: int) -> str:
    return f"{shlex.quote(sys.executable)} -c \"import sys; sys.stdout.write('x' * {count})\""


def write_encoded_stdout_command(text: str, encoding: str) -> str:
    payload = repr(text.encode(encoding))
    return shlex.join([sys.executable, "-c", f"import sys; sys.stdout.buffer.write({payload})"])
