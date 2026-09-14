from __future__ import annotations

import urllib.request
import uuid


from ..constants import (
    MAX_WEB_FETCH_BYTES,
    MAX_WEB_FETCH_OUTPUT_CHARS,
    MAX_WEB_SEARCH_CALLS_PER_TURN,
    WEB_SEARCH_BROWSER_HEADERS,
)
from ..result import ToolResult
from ..shell_command import _now_iso, _truncate_output
from ..web.fetch_html import (
    _charset_from_content_type,
    _extract_readable_html,
    _format_web_fetch_output,
    _is_html_response,
    _select_web_fetch_html_text,
    _validate_web_fetch_url,
)
from ..web.search_parse import _decode_http_body, _response_header
from ..web.deepseek_search import search
from .state import ToolRuntimeState


class WebToolsMixin(ToolRuntimeState):
    async def web_search(self, query: str) -> str:
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
        activity_id = f"web-search-{uuid.uuid4().hex}"
        self.running_processes[activity_id] = {"startTime": _now_iso(), "command": f"WebSearch: {query}"}
        try:
            result = await search(self.settings, query)
            if self.record_search_usage:
                self.record_search_usage(result.metadata)
            return result.to_json()
        finally:
            self.running_processes.pop(activity_id, None)

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
