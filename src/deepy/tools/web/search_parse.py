from __future__ import annotations

import gzip
import zlib

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
