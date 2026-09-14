import pytest
import httpx
from openai import AsyncOpenAI
from agents import ModelSettings

from deepy.llm.multimodal import ImageAttachmentError, UnsupportedImageInputError
from deepy.llm.response_images import normalize_response_images, validate_encoded_request
from deepy.llm.provider import DeepyResponsesModel
from deepy.ui.shared.input.image_input import ImageAttachmentController

IMAGE = {"type": "input_image", "image_url": "data:image/png;base64,aW1hZ2U="}


def test_invalid_size_format_count_and_remote_url():
    for part in (
        {"type": "input_image", "image_url": "https://example.com/img.png"},
        {"type": "input_image", "image_url": "data:image/png;base64,???"},
        {"type": "input_image", "image_url": "data:image/bmp;base64,aW1hZ2U="},
    ):
        with pytest.raises(ImageAttachmentError):
            normalize_response_images([{"role": "user", "content": [part]}])
    with pytest.raises(ImageAttachmentError):
        normalize_response_images([{"role": "user", "content": [IMAGE] * 9}])


@pytest.mark.asyncio
async def test_full_encoded_body_limit():
    request = httpx.Request(
        "POST", "https://example.com/responses", content=b"x" * (32 * 1024 * 1024 + 1)
    )
    with pytest.raises(ImageAttachmentError):
        await validate_encoded_request(request)


def test_switching_preserves_draft_and_count_limit():
    controller = ImageAttachmentController(supports_image_input=True)
    for _ in range(8):
        controller.attach_image(b"image", "image/png")
    with pytest.raises(ImageAttachmentError):
        controller.attach_image(b"image", "image/png")
    controller.supports_image_input = False
    with pytest.raises(ImageAttachmentError):
        controller.collect_and_reset()
    assert len(controller.attachments) == 8


def test_request_blocks_unsupported_history_and_isolates_reasoning():
    client = AsyncOpenAI(api_key="test")
    model = DeepyResponsesModel(provider="mimo", model="mimo-v2.5-pro", openai_client=client)

    def prepare(items):
        return model._build_response_create_kwargs(
            system_instructions=None,
            input=items,
            model_settings=ModelSettings(store=False),
            tools=[],
            output_schema=None,
            handoffs=[],
        )

    with pytest.raises(UnsupportedImageInputError):
        prepare([{"role": "user", "content": [IMAGE]}])
    raw = [
        {
            "type": "reasoning",
            "id": "rs_1",
            "summary": [],
            "encrypted_content": "opaque",
            "deepy_provider": "cli_proxy",
        },
        {"role": "user", "content": "hello"},
    ]
    payload = prepare(raw)
    assert not any(item.get("type") == "reasoning" for item in payload["input"])
    assert raw[0]["encrypted_content"] == "opaque"


def test_model_command_can_recover_an_incompatible_image_draft():
    controller = ImageAttachmentController(supports_image_input=True)
    attachment = controller.attach_image(b"image", "image/png")
    controller.supports_image_input = False
    text, images = controller.collect_from_prompt_text(
        f"{attachment.display_label} /model provider deepseek"
    )
    assert text == "/model provider deepseek" and images == []
    assert controller.attachments == [attachment]
    controller.supports_image_input = True
    _, images = controller.collect_from_prompt_text(attachment.display_label)
    assert images == [attachment]
