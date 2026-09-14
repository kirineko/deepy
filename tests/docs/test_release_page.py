"""Protect published version and local documentation links on the landing page."""
from html.parser import HTMLParser
from pathlib import Path
import tomllib

from deepy import __version__

ROOT = Path(__file__).resolve().parents[2]


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(value for key, value in attrs if key in {"href", "src"} and value)


def test_release_page_matches_package_and_lock_versions():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    package = next(item for item in lock["package"] if item["name"] == "deepy-cli")
    assert metadata["project"]["version"] == package["version"] == __version__
    page = (ROOT / "index.html").read_text()
    assert f"Deepy {__version__}" in page
    assert f"v{__version__}" in page


def test_landing_page_assets_and_bilingual_context_links_exist():
    parser = PageLinks()
    parser.feed((ROOT / "index.html").read_text())
    prefix = "https://github.com/kirineko/deepy/blob/main/"
    for link in parser.links:
        if link.startswith(prefix):
            assert (ROOT / link.removeprefix(prefix)).is_file(), link
        elif not link.startswith(("https://", "http://", "#")):
            assert (ROOT / link).is_file(), link
    for language in ("", ".zh-CN"):
        assert prefix + f"docs/model-context{language}.md" in parser.links
