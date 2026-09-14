"""Read images must reach the next SDK request as images, including batch reads."""

import json

import httpx
import pytest
from agents import Agent, Runner
from openai import AsyncOpenAI

from deepy.config import Settings
from deepy.config.providers import PROVIDER_CATALOG
from deepy.llm.provider import DeepyResponsesModel
from deepy.llm.thinking import build_model_settings
from deepy.tools.agents import build_function_tools
from deepy.tools.builtin import ToolRuntime


@pytest.mark.parametrize("info", PROVIDER_CATALOG, ids=lambda p: p.id)
@pytest.mark.asyncio
async def test_read_images_in_second_request(tmp_path, info):
    (tmp_path / "a.png").write_bytes(b"image-a")
    (tmp_path / "b.png").write_bytes(b"image-b")
    settings = Settings.from_mapping({"active_provider": info.id})
    runtime = ToolRuntime(cwd=tmp_path, settings=settings)
    calls = []

    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        output = (
            [
                {
                    "type": "function_call",
                    "id": "fc_1",
                    "call_id": "call_1",
                    "name": "Read",
                    "arguments": json.dumps({"files": [{"path": "a.png"}, {"path": "b.png"}]}),
                    "status": "completed",
                }
            ]
            if len(calls) == 1
            else [
                {
                    "type": "message",
                    "id": "msg_1",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "seen", "annotations": []}],
                }
            ]
        )
        return httpx.Response(
            200,
            json={
                "id": f"resp_{len(calls)}",
                "object": "response",
                "created_at": 1,
                "model": info.default_model,
                "status": "completed",
                "output": output,
            },
        )

    async with AsyncOpenAI(
        api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    ) as client:
        agent = Agent(
            name="test",
            model=DeepyResponsesModel(
                provider=info.id, model=info.default_model, openai_client=client
            ),
            model_settings=build_model_settings(settings),
            tools=build_function_tools(runtime, include_tools={"Read"}),
        )
        result = await Runner.run(agent, "Read both images")
    assert result.final_output == "seen"
    output = next(
        item["output"] for item in calls[1]["input"] if item.get("type") == "function_call_output"
    )
    images = [p for p in output if p["type"] == "input_image"]
    assert [p["image_url"] for p in images] == [
        "data:image/png;base64,aW1hZ2UtYQ==",
        "data:image/png;base64,aW1hZ2UtYg==",
    ]
    assert all("base64" not in p["text"] for p in output if p["type"] == "input_text")


def test_read_rejects_text_only_model_and_oversize(tmp_path):
    image = tmp_path / "a.png"
    image.write_bytes(b"image")
    settings = Settings.from_mapping(
        {"active_provider": "mimo", "providers": {"mimo": {"model": "mimo-v2.5-pro"}}}
    )
    result = json.loads(ToolRuntime(cwd=tmp_path, settings=settings).read({"path": "a.png"}))
    assert not result["ok"] and "不支持图片" in result["error"]
    with image.open("wb") as stream:
        stream.truncate(10 * 1024 * 1024 + 1)
    result = json.loads(ToolRuntime(cwd=tmp_path, settings=Settings()).read({"path": "a.png"}))
    assert not result["ok"]


@pytest.mark.parametrize("image_count", [8, 9])
def test_read_image_batch_limit_with_text_targets(tmp_path, image_count):
    from deepy.llm.response_images import normalize_response_images

    for index in range(image_count):
        (tmp_path / f"{index}.png").write_bytes(b"image")
    (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")
    output = ToolRuntime(cwd=tmp_path, settings=Settings()).read(
        {
            "files": [
                {"path": "notes.txt"},
                *[{"path": f"{index}.png"} for index in range(image_count)],
            ]
        }
    )
    result = json.loads(output)
    normalized = normalize_response_images(
        [{"type": "function_call_output", "call_id": "read_1", "output": output}]
    )
    if image_count == 8:
        assert result["ok"]
        assert "notes" in result["output"]
        images = [part for part in normalized[0]["output"] if part["type"] == "input_image"]
        assert len(images) == 8
        assert [item["path"] for item in result["metadata"]["targets"]] == [
            str(tmp_path / "notes.txt"),
            *[str(tmp_path / f"{index}.png") for index in range(8)],
        ]
    else:
        assert not result["ok"]
        assert "8" in result["error"] and "smaller" in result["error"]
        assert "followUpMessages" not in result
        assert "base64" not in output
        assert normalized[0]["output"] == output


@pytest.mark.asyncio
async def test_agent_recovers_from_oversized_read_batch(tmp_path):
    for index in range(9):
        (tmp_path / f"{index}.png").write_bytes(b"image")
    requests = []

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        turn = len(requests)
        if turn <= 2:
            if turn == 2:
                result = next(
                    item for item in body["input"] if item.get("type") == "function_call_output"
                )
                assert not json.loads(result["output"])["ok"]
            output = [
                {
                    "type": "function_call",
                    "id": f"fc_{turn}",
                    "call_id": f"call_{turn}",
                    "name": "Read",
                    "status": "completed",
                    "arguments": json.dumps(
                        {
                            "files": [
                                {"path": f"{index}.png"} for index in range(9 if turn == 1 else 1)
                            ]
                        }
                    ),
                }
            ]
        else:
            result = next(
                item
                for item in body["input"]
                if item.get("call_id") == "call_2" and item.get("type") == "function_call_output"
            )
            assert any(part["type"] == "input_image" for part in result["output"])
            output = [
                {
                    "type": "message",
                    "id": "msg_1",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "recovered", "annotations": []}],
                }
            ]
        return httpx.Response(
            200,
            json={
                "id": f"resp_{turn}",
                "object": "response",
                "created_at": 1,
                "model": "deepseek-flash",
                "status": "completed",
                "output": output,
            },
        )

    async with AsyncOpenAI(
        api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    ) as client:
        runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
        result = await Runner.run(
            Agent(
                name="test",
                model=DeepyResponsesModel(
                    provider="deepseek", model="deepseek-flash", openai_client=client
                ),
                tools=build_function_tools(runtime, include_tools={"Read"}),
            ),
            "Read the images",
            max_turns=3,
        )
    assert result.final_output == "recovered"
    assert len(requests) == 3
