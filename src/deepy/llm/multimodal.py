from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any

from deepy.config import Settings


SUPPORTED_IMAGE_MIME_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
    }
)
DEFAULT_MAX_IMAGE_BYTES = 50 * 1024 * 1024
UNSUPPORTED_IMAGE_INPUT_MESSAGE = "当前模型不支持图片输入，已忽略粘贴的图片。"
IMAGE_ONLY_DEFAULT_TEXT = "请描述这张图片的内容，不要执行工具或修改文件。"
IMAGE_DATA_URL_RE = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,", re.IGNORECASE)


class ImageAttachmentError(ValueError):
    pass


class UnsupportedImageInputError(RuntimeError):
    pass


@dataclass(frozen=True)
class PromptImageAttachment:
    label: str
    mime_type: str
    data_base64: str
    byte_size: int
    source: str = "clipboard"
    data_ref: str | None = None

    @property
    def display_label(self) -> str:
        return f"[{self.label}]"

    @property
    def data_url(self) -> str:
        return f"data:{self.mime_type};base64,{self.data_base64}"

    def to_input_image_block(self) -> dict[str, str]:
        return {"type": "input_image", "image_url": self.data_url}


def supports_image_input(settings: Settings) -> bool:
    return model_supports_image_input(settings.model.provider, settings.model.name)


def model_supports_image_input(provider: str, model: str) -> bool:
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip().lower()
    if normalized_provider == "xiaomi":
        return normalized_model == "mimo-v2.5"
    if normalized_provider == "openrouter":
        return normalized_model == "xiaomi/mimo-v2.5"
    if normalized_provider == "localhost":
        return normalized_model in {"gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"}
    return False


def validate_image_attachment(
    *,
    mime_type: str,
    byte_size: int,
    max_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
) -> None:
    normalized_mime = mime_type.strip().lower()
    if normalized_mime not in SUPPORTED_IMAGE_MIME_TYPES:
        raise ImageAttachmentError(f"不支持的图片格式：{mime_type or 'unknown'}")
    if byte_size <= 0:
        raise ImageAttachmentError("图片为空，已忽略粘贴的图片。")
    if byte_size > max_bytes:
        raise ImageAttachmentError("图片过大，已忽略粘贴的图片。")


def build_prompt_image_attachment(
    *,
    data: bytes,
    mime_type: str,
    index: int,
    source: str = "clipboard",
    max_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
) -> PromptImageAttachment:
    normalized_mime = mime_type.strip().lower()
    validate_image_attachment(
        mime_type=normalized_mime,
        byte_size=len(data),
        max_bytes=max_bytes,
    )
    return PromptImageAttachment(
        label=f"图片{index}",
        mime_type=normalized_mime,
        data_base64=base64.b64encode(data).decode("ascii"),
        byte_size=len(data),
        source=source,
    )


def image_attachment_labels(attachments: list[PromptImageAttachment]) -> str:
    return " ".join(attachment.display_label for attachment in attachments)


def format_user_prompt_display(prompt: str, attachments: list[PromptImageAttachment]) -> str:
    labels = image_attachment_labels(attachments)
    text = prompt.strip()
    if text and labels:
        return f"{text}\n{labels}"
    return text or labels


def build_user_input(
    prompt: str,
    attachments: list[PromptImageAttachment] | None = None,
) -> str | list[dict[str, Any]]:
    image_attachments = list(attachments or [])
    if not image_attachments:
        return prompt
    content: list[dict[str, str]] = []
    if prompt.strip():
        content.append({"type": "input_text", "text": prompt})
    content.extend(attachment.to_input_image_block() for attachment in image_attachments)
    return [{"role": "user", "content": content}]


def item_contains_image_content(item: Any) -> bool:
    if isinstance(item, dict):
        return _content_contains_image(item.get("content"))
    return _content_contains_image(getattr(item, "content", None))


def items_contain_image_content(items: list[Any]) -> bool:
    return any(item_contains_image_content(item) for item in items)


def strip_image_content_from_items(items: list[Any]) -> list[Any]:
    stripped: list[Any] = []
    for item in items:
        cleaned = strip_image_content_from_item(item)
        if cleaned is not None:
            stripped.append(cleaned)
    return stripped


def strip_image_content_from_item(item: Any) -> Any | None:
    if not isinstance(item, dict) or "content" not in item:
        return item
    cleaned = dict(item)
    content = _strip_image_content(item.get("content"))
    if content is None:
        return None
    cleaned["content"] = content
    return cleaned


def redacted_content_text(value: Any) -> str:
    if isinstance(value, str):
        return _redact_data_urls(value)
    if isinstance(value, list):
        parts: list[str] = []
        image_index = 1
        for part in value:
            if not isinstance(part, dict):
                continue
            if _part_is_image(part):
                parts.append(f"[图片{image_index}]")
                image_index += 1
                continue
            text = _text_part(part)
            if text:
                parts.append(_redact_data_urls(text))
        return "\n".join(parts)
    if isinstance(value, dict):
        if _part_is_image(value):
            return "[图片1]"
        text = _text_part(value)
        return _redact_data_urls(text) if text else ""
    return "" if value is None else _redact_data_urls(str(value))


def redact_image_data_urls(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_data_urls(value)
    if isinstance(value, list):
        return [redact_image_data_urls(item) for item in value]
    if isinstance(value, dict):
        redacted = {key: redact_image_data_urls(item) for key, item in value.items()}
        if _part_is_image(redacted):
            if isinstance(redacted.get("image_url"), str):
                redacted["image_url"] = "[图片]"
            elif isinstance(redacted.get("image_url"), dict):
                image_url = dict(redacted["image_url"])
                image_url["url"] = "[图片]"
                redacted["image_url"] = image_url
        return redacted
    return value


def normalize_multimodal_content_blocks(content: Any) -> Any:
    if not isinstance(content, list):
        return content
    normalized: list[Any] = []
    has_text = False
    has_image = False
    for part in content:
        if not isinstance(part, dict):
            normalized.append(part)
            continue
        part_type = part.get("type")
        if part_type == "input_text":
            text = part.get("text")
            if text is None:
                text = part.get("input_text")
            text_value = text if isinstance(text, str) else ""
            has_text = has_text or bool(text_value.strip())
            normalized.append({"type": "text", "text": text_value})
            continue
        if part_type == "input_image":
            image_url = part.get("image_url")
            has_image = True
            normalized.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url if isinstance(image_url, str) else "",
                    },
                }
            )
            continue
        if _part_is_image(part):
            has_image = True
        elif (text := _text_part(part)).strip():
            has_text = True
        normalized.append(part)
    if has_image and not has_text:
        normalized.insert(0, {"type": "text", "text": IMAGE_ONLY_DEFAULT_TEXT})
    return normalized


def _content_contains_image(content: Any) -> bool:
    if isinstance(content, list):
        return any(isinstance(part, dict) and _part_is_image(part) for part in content)
    return isinstance(content, dict) and _part_is_image(content)


def _strip_image_content(content: Any) -> Any | None:
    if isinstance(content, list):
        parts = [
            part
            for part in content
            if not (isinstance(part, dict) and _part_is_image(part))
        ]
        return parts or None
    if isinstance(content, dict) and _part_is_image(content):
        return None
    return content


def _part_is_image(part: dict[str, Any]) -> bool:
    part_type = part.get("type")
    return part_type in {"input_image", "image", "image_url"} or "image_url" in part


def _text_part(part: dict[str, Any]) -> str:
    for key in ("text", "input_text", "output_text", "refusal"):
        value = part.get(key)
        if isinstance(value, str):
            return value
    return ""


def _redact_data_urls(text: str) -> str:
    return IMAGE_DATA_URL_RE.sub("data:image/...;base64,", text)
