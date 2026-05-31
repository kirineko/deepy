from __future__ import annotations

import pytest

from deepy.llm.context import estimate_tokens_for_item
from deepy.llm.multimodal import (
    ImageAttachmentError,
    build_prompt_image_attachment,
    build_user_input,
    format_user_prompt_display,
    redacted_content_text,
    validate_image_attachment,
)


def test_build_prompt_image_attachment_labels_and_data_url():
    attachment = build_prompt_image_attachment(
        data=b"image",
        mime_type="image/png",
        index=2,
    )

    assert attachment.label == "图片2"
    assert attachment.display_label == "[图片2]"
    assert attachment.data_url == "data:image/png;base64,aW1hZ2U="
    assert attachment.to_input_image_block() == {
        "type": "input_image",
        "image_url": "data:image/png;base64,aW1hZ2U=",
    }


def test_validate_image_attachment_rejects_unknown_mime_and_large_data():
    with pytest.raises(ImageAttachmentError):
        validate_image_attachment(mime_type="image/tiff", byte_size=10)
    with pytest.raises(ImageAttachmentError):
        validate_image_attachment(mime_type="image/png", byte_size=11, max_bytes=10)


def test_build_user_input_preserves_text_only_shape_and_builds_multimodal_shape():
    attachment = build_prompt_image_attachment(data=b"image", mime_type="image/png", index=1)

    assert build_user_input("hello", []) == "hello"
    assert build_user_input("inspect", [attachment]) == [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "inspect"},
                {"type": "input_image", "image_url": "data:image/png;base64,aW1hZ2U="},
            ],
        }
    ]
    assert build_user_input("", [attachment]) == [
        {
            "role": "user",
            "content": [
                {"type": "input_image", "image_url": "data:image/png;base64,aW1hZ2U="}
            ],
        }
    ]


def test_prompt_display_and_redaction_use_image_labels_without_base64():
    attachment = build_prompt_image_attachment(data=b"image", mime_type="image/png", index=1)
    content = [
        {"type": "input_text", "text": "inspect"},
        {"type": "input_image", "image_url": attachment.data_url},
    ]

    assert format_user_prompt_display("inspect", [attachment]) == "inspect\n[图片1]"
    assert redacted_content_text(content) == "inspect\n[图片1]"
    assert "aW1hZ2U" not in redacted_content_text(content)


def test_image_context_estimate_does_not_count_full_base64_payload():
    item = {
        "role": "user",
        "content": [
            {"type": "input_text", "text": "inspect"},
            {"type": "input_image", "image_url": "data:image/png;base64," + "a" * 100_000},
        ],
    }

    assert estimate_tokens_for_item(item) < 2000
