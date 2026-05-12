from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from deepy.utils import json as json_utils

DEFAULT_PYPI_PACKAGE = "deepy"
DEFAULT_GITHUB_REPO = "kirineko/deepy"
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
    github_repo: str = DEFAULT_GITHUB_REPO,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    urlopen: UrlOpen = urllib.request.urlopen,
) -> VersionUpdate | None:
    candidates = [
        candidate
        for candidate in (
            fetch_latest_pypi_version(pypi_package, timeout_seconds=timeout_seconds, urlopen=urlopen),
            fetch_latest_github_version(github_repo, timeout_seconds=timeout_seconds, urlopen=urlopen),
        )
        if candidate is not None
    ]
    latest = _latest_candidate(candidates)
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


def fetch_latest_github_version(
    repo: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    urlopen: UrlOpen = urllib.request.urlopen,
) -> VersionCandidate | None:
    release = _fetch_github_release_version(repo, timeout_seconds=timeout_seconds, urlopen=urlopen)
    if release is not None:
        return release
    return _fetch_github_tag_version(repo, timeout_seconds=timeout_seconds, urlopen=urlopen)


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


def _fetch_github_release_version(
    repo: str,
    *,
    timeout_seconds: float,
    urlopen: UrlOpen,
) -> VersionCandidate | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        with urlopen(_request(url), timeout=timeout_seconds) as response:
            payload = _read_json_response(response)
    except (OSError, urllib.error.URLError, json_utils.JSONDecodeError):
        return None
    tag = payload.get("tag_name") if isinstance(payload, dict) else None
    version = _normalize_tag_version(tag)
    if version is None:
        return None
    html_url = payload.get("html_url") if isinstance(payload, dict) else None
    return VersionCandidate(
        version=version,
        source="GitHub",
        url=html_url if isinstance(html_url, str) and html_url else f"https://github.com/{repo}/releases/latest",
    )


def _fetch_github_tag_version(
    repo: str,
    *,
    timeout_seconds: float,
    urlopen: UrlOpen,
) -> VersionCandidate | None:
    url = f"https://api.github.com/repos/{repo}/tags?per_page=1"
    try:
        with urlopen(_request(url), timeout=timeout_seconds) as response:
            payload = _read_json_response(response)
    except (OSError, urllib.error.URLError, json_utils.JSONDecodeError):
        return None
    if not isinstance(payload, list) or not payload:
        return None
    first = payload[0]
    tag = first.get("name") if isinstance(first, dict) else None
    version = _normalize_tag_version(tag)
    if version is None:
        return None
    return VersionCandidate(version=version, source="GitHub", url=f"https://github.com/{repo}/releases/tag/{tag}")


def _latest_candidate(candidates: list[VersionCandidate]) -> VersionCandidate | None:
    latest: VersionCandidate | None = None
    for candidate in candidates:
        if latest is None or compare_versions(candidate.version, latest.version) > 0:
            latest = candidate
    return latest


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


def _normalize_tag_version(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if stripped.startswith(("v", "V")):
        stripped = stripped[1:]
    return stripped if _version_parts(stripped) else None


def _version_parts(value: str) -> list[int]:
    match = re.match(r"^\s*v?(\d+(?:\.\d+)*)", value, flags=re.IGNORECASE)
    if not match:
        return []
    return [int(part) for part in match.group(1).split(".")]
