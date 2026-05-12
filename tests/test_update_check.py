from __future__ import annotations

from deepy.update_check import check_for_version_update
from deepy.update_check import compare_versions
from deepy.update_check import fetch_latest_github_version
from deepy.update_check import fetch_latest_pypi_version


class FakeResponse:
    def __init__(self, body: str):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body.encode("utf-8")


def test_compare_versions_orders_semantic_versions():
    assert compare_versions("0.1.1", "0.1.0") == 1
    assert compare_versions("0.2.0", "0.10.0") == -1
    assert compare_versions("v1.0.0", "1.0.0") == 0
    assert compare_versions("1.0.0-beta.1", "1.0.0") == 0


def test_fetch_latest_pypi_version_reads_info_version():
    def fake_urlopen(request, timeout):
        assert request.full_url == "https://pypi.org/pypi/deepy/json"
        assert timeout == 1.0
        return FakeResponse('{"info":{"version":"0.2.0"}}')

    candidate = fetch_latest_pypi_version("deepy", timeout_seconds=1.0, urlopen=fake_urlopen)

    assert candidate is not None
    assert candidate.version == "0.2.0"
    assert candidate.source == "PyPI"


def test_fetch_latest_github_version_prefers_release_tag():
    def fake_urlopen(request, timeout):
        assert request.full_url == "https://api.github.com/repos/kirineko/deepy/releases/latest"
        return FakeResponse('{"tag_name":"v0.3.0","html_url":"https://github.com/kirineko/deepy/releases/tag/v0.3.0"}')

    candidate = fetch_latest_github_version(
        "kirineko/deepy",
        timeout_seconds=1.0,
        urlopen=fake_urlopen,
    )

    assert candidate is not None
    assert candidate.version == "0.3.0"
    assert candidate.source == "GitHub"


def test_check_for_version_update_chooses_highest_candidate():
    def fake_urlopen(request, timeout):
        if request.full_url == "https://pypi.org/pypi/deepy/json":
            return FakeResponse('{"info":{"version":"0.2.0"}}')
        if request.full_url == "https://api.github.com/repos/kirineko/deepy/releases/latest":
            return FakeResponse('{"tag_name":"v0.3.0","html_url":"https://github.com/kirineko/deepy/releases/tag/v0.3.0"}')
        raise AssertionError(request.full_url)

    update = check_for_version_update("0.1.0", timeout_seconds=1.0, urlopen=fake_urlopen)

    assert update is not None
    assert update.latest_version == "0.3.0"
    assert update.source == "GitHub"
    assert update.install_hint == "uv tool upgrade deepy"


def test_check_for_version_update_returns_none_for_current_version():
    def fake_urlopen(request, timeout):
        if request.full_url == "https://pypi.org/pypi/deepy/json":
            return FakeResponse('{"info":{"version":"0.1.0"}}')
        if request.full_url == "https://api.github.com/repos/kirineko/deepy/releases/latest":
            return FakeResponse('{"tag_name":"v0.1.0"}')
        raise AssertionError(request.full_url)

    assert check_for_version_update("0.1.0", timeout_seconds=1.0, urlopen=fake_urlopen) is None
