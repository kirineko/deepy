from __future__ import annotations

import urllib.parse
import urllib.request
import uuid

from deepy.config import DEFAULT_WEB_SEARCH_SEARXNG_URL

from ..constants import (
    DEFAULT_WEB_SEARCH_RESULTS,
    DEFAULT_WEB_SEARCH_URL,
    MAX_WEB_FETCH_BYTES,
    MAX_WEB_FETCH_OUTPUT_CHARS,
    MAX_WEB_SEARCH_CALLS_PER_TURN,
    WEB_SEARCH_BROWSER_HEADERS,
)
from ..result import ToolResult
from ..shell_command import _now_iso, _truncate_output
from ..tool_dataclasses import WebSearchProviderFailure, WebSearchProviderResult
from ..web.fetch_html import (
    _charset_from_content_type,
    _extract_readable_html,
    _format_web_fetch_output,
    _is_html_response,
    _select_web_fetch_html_text,
    _validate_web_fetch_url,
)
from ..web.query import (
    _format_web_search_activity_label,
    _prepare_web_search_query_with_llm,
)
from ..web.search_parse import (
    _build_searxng_search_url,
    _decode_http_body,
    _format_provider_failures,
    _format_search_results,
    _mask_url_secrets,
    _parse_search_results,
    _parse_searxng_results,
    _response_header,
)
from .state import ToolRuntimeState


class WebToolsMixin(ToolRuntimeState):
    def web_search(self, query: str) -> str:
        name = "WebSearch"
        if not query.strip():
            return ToolResult.error_result(name, 'Missing required "query" string.').to_json()
        self.web_search_calls += 1
        if self.web_search_calls > MAX_WEB_SEARCH_CALLS_PER_TURN:
            return ToolResult.error_result(
                name,
                (
                    f"WebSearch call limit reached for this turn "
                    f"({MAX_WEB_SEARCH_CALLS_PER_TURN}). Stop searching and answer from the "
                    "results already gathered, or use WebFetch only for a specific URL that is "
                    "essential."
                ),
                metadata={
                    "callLimit": MAX_WEB_SEARCH_CALLS_PER_TURN,
                    "callCount": self.web_search_calls,
                },
            ).to_json()
        return self._web_search_builtin(query)

    def web_fetch(self, url: str) -> str:
        name = "WebFetch"
        target_url, validation_error = _validate_web_fetch_url(url)
        if validation_error is not None or target_url is None:
            return ToolResult.error_result(
                name, validation_error or 'Missing required "url" string.'
            ).to_json()

        activity_label = f"WebFetch: {target_url}"
        activity_id = f"web-fetch-{uuid.uuid4().hex}"
        self.running_processes[activity_id] = {
            "startTime": _now_iso(),
            "command": activity_label,
        }
        request = urllib.request.Request(
            target_url,
            headers={
                **WEB_SEARCH_BROWSER_HEADERS,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                final_url = response.geturl()
                content_type = _response_header(response, "Content-Type") or ""
                content_encoding = _response_header(response, "Content-Encoding")
                body = response.read(MAX_WEB_FETCH_BYTES + 1)
        except Exception as exc:
            return ToolResult.error_result(
                name,
                f"WebFetch request failed: {exc}",
                metadata={
                    "url": target_url,
                    "activityLabel": activity_label,
                },
            ).to_json()
        finally:
            self.running_processes.pop(activity_id, None)

        bytes_truncated = len(body) > MAX_WEB_FETCH_BYTES
        body = body[:MAX_WEB_FETCH_BYTES]
        charset = _charset_from_content_type(content_type)
        try:
            decoded = _decode_http_body(body, encoding=content_encoding, charset=charset)
        except Exception as exc:
            return ToolResult.error_result(
                name,
                f"WebFetch response decode failed: {exc}",
                metadata={
                    "url": target_url,
                    "finalUrl": final_url,
                    "contentType": content_type,
                    "contentEncoding": content_encoding,
                    "charset": charset,
                    "activityLabel": activity_label,
                },
            ).to_json()
        if _is_html_response(content_type, decoded):
            title, readable_text, metadata_text = _extract_readable_html(decoded)
            readable_text = _select_web_fetch_html_text(readable_text, metadata_text)
        else:
            title = ""
            readable_text = decoded.strip()
        output = _format_web_fetch_output(
            url=target_url,
            final_url=final_url,
            content_type=content_type,
            title=title,
            text=readable_text,
            bytes_truncated=bytes_truncated,
        )
        output, output_truncated = _truncate_output(output, MAX_WEB_FETCH_OUTPUT_CHARS)
        return ToolResult.ok_result(
            name,
            output,
            metadata={
                "url": target_url,
                "finalUrl": final_url,
                "contentType": content_type,
                "charset": charset,
                "byteCount": len(body),
                "bodyTruncated": bytes_truncated,
                "outputTruncated": output_truncated,
                "activityLabel": activity_label,
            },
        ).to_json()

    def _web_search_builtin(self, query: str) -> str:
        name = "WebSearch"
        prepared, prepare_error = _prepare_web_search_query_with_llm(query, self.settings)
        activity_label = _format_web_search_activity_label(prepared.resolved_query)
        activity_id = f"web-search-{uuid.uuid4().hex}"
        self.running_processes[activity_id] = {
            "startTime": _now_iso(),
            "command": activity_label,
        }
        failures: list[WebSearchProviderFailure] = []
        query_metadata = {
            **prepared.metadata(),
            "activityLabel": activity_label,
            **({"queryPreparationWarning": prepare_error} if prepare_error else {}),
        }
        try:
            searxng_url = (
                self.settings.tools.web_search.searxng_url or DEFAULT_WEB_SEARCH_SEARXNG_URL
            )
            result, failure = self._try_searxng_search(prepared.resolved_query, searxng_url)
            if result is not None:
                return ToolResult.ok_result(
                    name,
                    _format_search_results(prepared.resolved_query, result.results),
                    metadata={
                        **query_metadata,
                        "backend": result.provider,
                        "provider": result.provider,
                        "searchUrl": _mask_url_secrets(result.search_url),
                        "providerAttempts": [{**item.metadata(), "ok": False} for item in failures]
                        + [{"provider": result.provider, "ok": True}],
                        "resultCount": min(len(result.results), DEFAULT_WEB_SEARCH_RESULTS),
                    },
                ).to_json()
            if failure is not None:
                failures.append(failure)

            result, failure = self._try_duckduckgo_search(prepared.resolved_query)
            if result is not None:
                return ToolResult.ok_result(
                    name,
                    _format_search_results(prepared.resolved_query, result.results),
                    metadata={
                        **query_metadata,
                        "backend": result.provider,
                        "provider": result.provider,
                        "searchUrl": _mask_url_secrets(result.search_url),
                        "providerAttempts": [{**item.metadata(), "ok": False} for item in failures]
                        + [{"provider": result.provider, "ok": True}],
                        "resultCount": min(len(result.results), DEFAULT_WEB_SEARCH_RESULTS),
                    },
                ).to_json()
            if failure is not None:
                failures.append(failure)

            return ToolResult.error_result(
                name,
                "WebSearch failed: " + _format_provider_failures(failures),
                metadata={
                    **query_metadata,
                    "backend": "provider_chain",
                    "providerAttempts": [{**item.metadata(), "ok": False} for item in failures],
                },
            ).to_json()
        finally:
            self.running_processes.pop(activity_id, None)

    def _try_duckduckgo_search(
        self,
        query: str,
    ) -> tuple[WebSearchProviderResult | None, WebSearchProviderFailure | None]:
        provider = "duckduckgo_html"
        search_url = (
            DEFAULT_WEB_SEARCH_URL + "?" + urllib.parse.urlencode({"q": query}, doseq=False)
        )
        request = urllib.request.Request(
            search_url,
            headers={
                **WEB_SEARCH_BROWSER_HEADERS,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = _decode_http_body(
                    response.read(),
                    encoding=_response_header(response, "Content-Encoding"),
                )
        except Exception as exc:
            return None, WebSearchProviderFailure(
                provider=provider,
                error=f"request failed: {exc}",
                search_url=search_url,
            )
        results = _parse_search_results(body)
        if not results:
            return None, WebSearchProviderFailure(
                provider=provider,
                error="no parseable results",
                search_url=search_url,
            )
        return WebSearchProviderResult(
            provider=provider, search_url=search_url, results=results
        ), None

    def _try_searxng_search(
        self,
        query: str,
        base_url: str,
    ) -> tuple[WebSearchProviderResult | None, WebSearchProviderFailure | None]:
        provider = "searxng_json"
        try:
            search_url = _build_searxng_search_url(base_url, query)
        except ValueError as exc:
            return None, WebSearchProviderFailure(provider=provider, error=str(exc))
        request = urllib.request.Request(
            search_url,
            headers=WEB_SEARCH_BROWSER_HEADERS,
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = _decode_http_body(
                    response.read(),
                    encoding=_response_header(response, "Content-Encoding"),
                )
            results = _parse_searxng_results(body)
        except Exception as exc:
            return None, WebSearchProviderFailure(
                provider=provider,
                error=f"request failed: {exc}",
                search_url=search_url,
            )
        if not results:
            return None, WebSearchProviderFailure(
                provider=provider,
                error="no parseable results",
                search_url=search_url,
            )
        return WebSearchProviderResult(
            provider=provider, search_url=search_url, results=results
        ), None
