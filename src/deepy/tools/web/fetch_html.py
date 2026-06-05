from __future__ import annotations

import re
import urllib.parse
from html.parser import HTMLParser

from ..constants import MAX_WEB_FETCH_BYTES, MIN_USEFUL_WEB_FETCH_BODY_CHARS

class _ReadableHtmlParser(HTMLParser):
    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
    SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.description_candidates: dict[str, str] = {}
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized == "meta":
            self._record_meta_description(attrs)
            return
        if normalized in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if normalized == "title":
            self._in_title = True
            return
        if normalized in self.BLOCK_TAGS:
            self._append_newline()

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if normalized == "title":
            self._in_title = False
            return
        if normalized in self.BLOCK_TAGS:
            self._append_newline()

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
            return
        if self._skip_depth:
            return
        self.text_parts.append(text)

    def _append_newline(self) -> None:
        if self.text_parts and self.text_parts[-1] != "\n":
            self.text_parts.append("\n")

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def readable_text(self) -> str:
        raw = " ".join(self.text_parts)
        raw = re.sub(r"[ \t]*\n[ \t]*", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return "\n".join(line.strip() for line in raw.splitlines()).strip()

    @property
    def meta_description(self) -> str:
        for key in ("description", "og:description", "twitter:description"):
            text = self.description_candidates.get(key, "").strip()
            if text:
                return text
        return ""

    def _record_meta_description(self, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value for name, value in attrs if value is not None}
        raw_key = attr_map.get("name") or attr_map.get("property")
        content = attr_map.get("content", "")
        if not raw_key or not content:
            return
        key = raw_key.strip().lower()
        if key not in {"description", "og:description", "twitter:description"}:
            return
        normalized = " ".join(content.split()).strip()
        if normalized and key not in self.description_candidates:
            self.description_candidates[key] = normalized


def _validate_web_fetch_url(url: str) -> tuple[str | None, str | None]:
    stripped = url.strip()
    parsed = urllib.parse.urlparse(stripped)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None, "WebFetch requires a complete http or https URL."
    return stripped, None


def _charset_from_content_type(content_type: str) -> str:
    match = re.search(r"charset=([^\s;]+)", content_type, flags=re.IGNORECASE)
    return match.group(1).strip("\"'") if match else "utf-8"


def _is_html_response(content_type: str, text: str) -> bool:
    lowered = content_type.lower()
    if "html" in lowered:
        return True
    prefix = text[:500].lower()
    return "<html" in prefix or "<!doctype html" in prefix


def _extract_readable_html(html: str) -> tuple[str, str, str]:
    parser = _ReadableHtmlParser()
    parser.feed(html)
    parser.close()
    return parser.title, parser.readable_text, parser.meta_description


def _select_web_fetch_html_text(readable_text: str, metadata_text: str) -> str:
    stripped = readable_text.strip()
    if stripped and _is_useful_web_fetch_body_text(stripped):
        return stripped
    return metadata_text.strip() or stripped


def _is_useful_web_fetch_body_text(text: str) -> bool:
    normalized = " ".join(text.split()).strip().lower()
    if len(normalized) >= MIN_USEFUL_WEB_FETCH_BODY_CHARS:
        return True
    return normalized not in {
        "",
        "loading",
        "loading...",
        "please enable javascript",
        "you need to enable javascript to run this app.",
    }


def _format_web_fetch_output(
    *,
    url: str,
    final_url: str,
    content_type: str,
    title: str,
    text: str,
    bytes_truncated: bool,
) -> str:
    lines = [
        f"URL: {url}",
        f"Final URL: {final_url}",
    ]
    if title:
        lines.append(f"Title: {title}")
    if content_type:
        lines.append(f"Content-Type: {content_type}")
    if bytes_truncated:
        lines.append(f"Note: response body was truncated at {MAX_WEB_FETCH_BYTES:,} bytes.")
    lines.append("")
    lines.append(text.strip() if text.strip() else "[No readable text extracted.]")
    return "\n".join(lines).strip()

