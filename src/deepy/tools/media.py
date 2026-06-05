from __future__ import annotations

import base64
import math
import re
from pathlib import Path

from .constants import PDF_LARGE_PAGE_THRESHOLD, PDF_MAX_PAGE_RANGE
from .result import ToolResult
from .tool_dataclasses import PageRange


def _read_pdf(path: Path, pages: str | None, *, name: str) -> str:
    data = path.read_bytes()
    page_count = _count_pdf_pages(data)
    page_range, range_error = _parse_page_range(pages)
    if range_error is not None:
        return ToolResult.error_result(name, range_error, metadata={"path": str(path)}).to_json()

    if page_range is None and page_count is not None and page_count > PDF_LARGE_PAGE_THRESHOLD:
        return ToolResult.error_result(
            name,
            f'PDF has {page_count} pages; provide "pages" to read a range.',
            metadata={"path": str(path), "pageCount": page_count},
        ).to_json()
    if page_range is not None and page_range.count > PDF_MAX_PAGE_RANGE:
        return ToolResult.error_result(
            name,
            f"PDF page range exceeds {PDF_MAX_PAGE_RANGE} pages.",
            metadata={"path": str(path), "pageCount": page_count},
        ).to_json()
    if page_range is not None and page_count is not None and page_range.end > page_count:
        return ToolResult.error_result(
            name,
            f"PDF page range exceeds total page count ({page_count}).",
            metadata={"path": str(path), "pageCount": page_count},
        ).to_json()

    encoded = base64.b64encode(data).decode("ascii")
    return ToolResult.ok_result(
        name,
        f"data:application/pdf;base64,{encoded}",
        metadata={
            "path": str(path),
            "mime": "application/pdf",
            "encoding": "base64",
            "bytes": len(data),
            "pageCount": page_count,
            "pages": page_range.label() if page_range is not None else None,
        },
    ).to_json()


def _count_pdf_pages(data: bytes) -> int | None:
    try:
        text = data.decode("latin1", errors="ignore")
    except Exception:
        return None
    return len(re.findall(r"/Type\s*/Page\b(?!s)", text))


def _parse_page_range(value: str | None) -> tuple[PageRange | None, str | None]:
    if value is None or not value.strip():
        return None, None
    trimmed = value.strip()
    if "," in trimmed:
        return None, 'pages must be a single range like "1-5" or "3".'
    parts = [part.strip() for part in trimmed.split("-")]
    if len(parts) == 1:
        start, error = _parse_positive_int(parts[0], "pages")
        return (PageRange(start, start), None) if error is None else (None, error)
    if len(parts) == 2:
        start, start_error = _parse_positive_int(parts[0], "pages")
        if start_error is not None:
            return None, start_error
        end, end_error = _parse_positive_int(parts[1], "pages")
        if end_error is not None:
            return None, end_error
        if end < start:
            return None, "pages range end must be >= start."
        return PageRange(start, end), None
    return None, 'pages must be a single range like "1-5" or "3".'


def _parse_positive_int(value: str, label: str) -> tuple[int, str | None]:
    try:
        numeric = float(value)
    except ValueError:
        return 0, f"{label} must be a number."
    if not math.isfinite(numeric):
        return 0, f"{label} must be a number."
    integer = int(numeric)
    if integer < 1:
        return 0, f"{label} must be >= 1."
    return integer, None


IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".avif": "image/avif",
}


def _image_mime_type(suffix: str) -> str | None:
    return IMAGE_MIME_TYPES.get(suffix)


def _build_image_follow_up_message(path: Path, mime: str, data: bytes) -> dict[str, object]:
    encoded = base64.b64encode(data).decode("ascii")
    return {
        "role": "system",
        "content": [
            {
                "type": "input_text",
                "text": (
                    f"The read tool has loaded `{path.name}`. "
                    "Use the attached image content to answer the original request."
                ),
            },
            {
                "type": "input_image",
                "image_url": f"data:{mime};base64,{encoded}",
            },
        ],
    }
