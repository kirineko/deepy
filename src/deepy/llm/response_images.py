"""Responses image normalization and validation shared by prompts and tools."""

from __future__ import annotations

import base64
import binascii
from typing import Any

import httpx

from deepy.utils import json as json_utils

from .multimodal import ImageAttachmentError, IMAGE_ONLY_DEFAULT_TEXT, validate_image_attachment

MAX_IMAGES_PER_TURN = 8
MAX_REQUEST_BYTES = 32 * 1024 * 1024


def _read_image_output(item: dict[str, Any]) -> dict[str, Any]:
    """Expand Read's stored JSON at the request boundary, preserving local history."""
    if item.get("type") != "function_call_output" or not isinstance(item.get("output"), str):
        return item
    try:
        result = json_utils.loads(item["output"])
    except (ValueError, TypeError):
        return item
    if not isinstance(result, dict) or result.get("name") != "Read":
        return item
    messages = result.pop("followUpMessages", None)
    if not isinstance(messages, list):
        return item
    parts = [
        part
        for message in messages
        if isinstance(message, dict)
        for part in message.get("content", [])
        if isinstance(part, dict)
    ]
    if not parts:
        return item
    return {**item, "output": [{"type": "input_text", "text": json_utils.dumps(result)}, *parts]}


def normalize_response_images(items: Any) -> Any:
    if not isinstance(items, list):
        return items
    output = []
    for item in items:
        if not isinstance(item, dict):
            output.append(item)
            continue
        item = _read_image_output(item)
        field = "output" if item.get("type") == "function_call_output" else "content"
        if not isinstance(item.get(field), list):
            output.append(item)
            continue
        parts = []
        image_count = 0
        for part in item[field]:
            if not isinstance(part, dict):
                parts.append(part)
                continue
            if part.get("type") not in {"image", "image_url", "input_image"}:
                parts.append({**part, "type": "input_text"} if part.get("type") == "text" else part)
                continue
            image_count += 1
            url = part.get("image_url")
            if isinstance(url, dict):
                url = url.get("url")
            if not isinstance(url, str) or not url.startswith("data:"):
                raise ImageAttachmentError("图片必须使用本地附件的 base64 data URL。")
            header, separator, encoded = url.partition(",")
            if not separator or not header.endswith(";base64"):
                raise ImageAttachmentError("图片 data URL 格式无效。")
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ImageAttachmentError("图片 base64 数据无效。") from exc
            validate_image_attachment(mime_type=header[5:-7], byte_size=len(data))
            parts.append({"type": "input_image", "image_url": url})
        if image_count > MAX_IMAGES_PER_TURN:
            raise ImageAttachmentError("每轮最多支持 8 张图片。")
        if image_count and not any(
            isinstance(p, dict) and p.get("text", "").strip() for p in parts
        ):
            parts.insert(0, {"type": "input_text", "text": IMAGE_ONLY_DEFAULT_TEXT})
        output.append({**item, field: parts})
    return output


async def validate_encoded_request(request: httpx.Request) -> None:
    if len(request.content) > MAX_REQUEST_BYTES:
        raise ImageAttachmentError("完整编码请求超过 32 MiB，请减少图片或压缩上下文。")
