from __future__ import annotations

import gzip
import urllib.parse
import zlib
from html.parser import HTMLParser

from deepy.config import mask_secret
from deepy.utils import json as json_utils

from ..constants import DEFAULT_WEB_SEARCH_RESULTS
from ..tool_dataclasses import WebSearchProviderFailure, WebSearchResult

class _SearchResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[WebSearchResult] = []
        self._current_title: list[str] | None = None
        self._current_url: str = ""
        self._snippet_index: int | None = None
        self._snippet_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        if tag == "a" and "result__a" in classes:
            self._current_title = []
            self._current_url = _decode_search_result_url(values.get("href", ""))
            return
        if "result__snippet" in classes and self.results:
            self._snippet_index = len(self.results) - 1
            self._snippet_chunks = []

    def handle_data(self, data: str) -> None:
        if self._current_title is not None:
            self._current_title.append(data)
        elif self._snippet_index is not None:
            self._snippet_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_title is not None:
            title = " ".join("".join(self._current_title).split())
            if title and self._current_url:
                self.results.append(WebSearchResult(title=title, url=self._current_url))
            self._current_title = None
            self._current_url = ""
            return
        if self._snippet_index is not None and tag in {"a", "div", "td"}:
            snippet = " ".join("".join(self._snippet_chunks).split())
            if snippet:
                result = self.results[self._snippet_index]
                self.results[self._snippet_index] = WebSearchResult(
                    title=result.title,
                    url=result.url,
                    snippet=snippet,
                )
            self._snippet_index = None
            self._snippet_chunks = []


def _decode_search_result_url(href: str) -> str:
    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)
    target = query.get("uddg", [""])[0]
    if target:
        return target
    if parsed.scheme and parsed.netloc:
        return href
    return urllib.parse.urljoin("https://duckduckgo.com", href)


def _parse_search_results(html: str) -> list[WebSearchResult]:
    parser = _SearchResultParser()
    parser.feed(html)
    unique: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    for result in parser.results:
        if result.url in seen_urls:
            continue
        seen_urls.add(result.url)
        unique.append(result)
    return unique


def _format_search_results(query: str, results: list[WebSearchResult]) -> str:
    lines = [f"Web search results for: {query}", ""]
    for index, result in enumerate(results[:DEFAULT_WEB_SEARCH_RESULTS], start=1):
        lines.append(f"{index}. {result.title}")
        lines.append(f"   {result.url}")
        if result.snippet:
            lines.append(f"   {result.snippet}")
        lines.append("")
    return "\n".join(lines).strip()


def _parse_searxng_results(body: str) -> list[WebSearchResult]:
    payload = json_utils.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("SearXNG response must be a JSON object.")
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise ValueError("SearXNG response is missing a results array.")
    results: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(url, str) or not url.strip() or url in seen_urls:
            continue
        content = item.get("content")
        snippet = content if isinstance(content, str) else ""
        seen_urls.add(url)
        results.append(
            WebSearchResult(title=" ".join(title.split()), url=url, snippet=snippet.strip())
        )
    return results


def _build_searxng_search_url(base_url: str, query: str) -> str:
    stripped = base_url.strip()
    parsed = urllib.parse.urlparse(stripped)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("SearXNG URL must be a complete http or https URL.")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("SearXNG URL must use http or https.")
    path = parsed.path.rstrip("/")
    endpoint_path = parsed.path if path.endswith("/search") else f"{path}/search"
    parts = parsed._replace(path=endpoint_path or "/search")
    query_params = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query_params.extend([("q", query), ("format", "json")])
    return urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(query_params)))


def _decode_http_body(body: bytes, *, encoding: str | None, charset: str = "utf-8") -> str:
    normalized_encoding = (encoding or "").split(";", 1)[0].strip().lower()
    if normalized_encoding == "gzip":
        body = gzip.decompress(body)
    elif normalized_encoding == "deflate":
        try:
            body = zlib.decompress(body)
        except zlib.error:
            body = zlib.decompress(body, -zlib.MAX_WBITS)
    elif normalized_encoding not in {"", "identity"}:
        raise ValueError(f"Unsupported content encoding: {encoding}")
    return body.decode(charset, errors="replace")


def _response_header(response: object, name: str) -> str | None:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return None
    value = getter(name)
    return value if isinstance(value, str) else None


def _mask_url_secrets(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    sensitive_keys = {"api_key", "apikey", "key", "token", "access_token", "auth", "authorization"}
    masked = [
        (key, mask_secret(value) if key.lower() in sensitive_keys else value)
        for key, value in query_params
    ]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(masked)))


def _format_provider_failures(failures: list[WebSearchProviderFailure]) -> str:
    return "; ".join(f"{failure.provider}: {failure.error}" for failure in failures)

