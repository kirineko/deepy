from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from deepy.utils import json as json_utils

DEFAULT_PYPI_PACKAGE = "deepy-cli"
DEFAULT_TIMEOUT_SECONDS = 0.8

UrlOpen = Callable[..., Any]


@dataclass(frozen=True)
class VersionCandidate:
    version: str
    source: str
    url: str


@dataclass(frozen=True)
class VersionUpdate:
    current_version: str
    latest_version: str
    source: str
    url: str
    install_hint: str


def check_for_version_update(
    current_version: str,
    *,
    pypi_package: str = DEFAULT_PYPI_PACKAGE,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    urlopen: UrlOpen = urllib.request.urlopen,
) -> VersionUpdate | None:
    latest = fetch_latest_pypi_version(
        pypi_package,
        timeout_seconds=timeout_seconds,
        urlopen=urlopen,
    )
    if latest is None or compare_versions(latest.version, current_version) <= 0:
        return None
    return VersionUpdate(
        current_version=current_version,
        latest_version=latest.version,
        source=latest.source,
        url=latest.url,
        install_hint=f"uv tool upgrade {pypi_package}",
    )


def fetch_latest_pypi_version(
    package_name: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    urlopen: UrlOpen = urllib.request.urlopen,
) -> VersionCandidate | None:
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with urlopen(_request(url), timeout=timeout_seconds) as response:
            payload = _read_json_response(response)
    except (OSError, urllib.error.URLError, json_utils.JSONDecodeError):
        return None
    info = payload.get("info") if isinstance(payload, dict) else None
    version = info.get("version") if isinstance(info, dict) else None
    if not isinstance(version, str) or not version.strip():
        return None
    return VersionCandidate(version=version.strip(), source="PyPI", url=f"https://pypi.org/project/{package_name}/")


def compare_versions(a: str, b: str) -> int:
    left = _version_parts(a)
    right = _version_parts(b)
    width = max(len(left), len(right))
    for index in range(width):
        left_part = left[index] if index < len(left) else 0
        right_part = right[index] if index < len(right) else 0
        if left_part > right_part:
            return 1
        if left_part < right_part:
            return -1
    return 0


def _read_json_response(response: Any) -> dict[str, Any] | list[Any]:
    data = response.read()
    if isinstance(data, str):
        text = data
    else:
        text = data.decode("utf-8", errors="replace")
    parsed = json_utils.loads(text)
    return parsed if isinstance(parsed, (dict, list)) else {}


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Deepy update check",
        },
        method="GET",
    )


def _version_parts(value: str) -> list[int]:
    match = re.match(r"^\s*v?(\d+(?:\.\d+)*)", value, flags=re.IGNORECASE)
    if not match:
        return []
    return [int(part) for part in match.group(1).split(".")]
