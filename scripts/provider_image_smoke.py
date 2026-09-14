"""Opt-in streamed image probe for the supported Responses model catalog."""

import argparse
import asyncio
import base64
import json
import os
import struct
import zlib
from dataclasses import replace

from agents import Agent, Runner
from deepy.config import Settings
from deepy.config.providers import PROVIDER_CATALOG
from deepy.llm.provider import build_provider_bundle
from deepy.llm.multimodal import UnsupportedImageInputError


def test_image():
    def chunk(kind, data):
        return (
            struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
        )

    rows = []
    for y in range(80):
        row = bytearray([0])
        for x in range(80):
            row.extend(
                ((255, 0, 0) if x < 40 else (0, 255, 0))
                if y < 40
                else ((0, 0, 255) if x < 40 else (255, 255, 0))
            )
        rows.append(bytes(row))
    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", 80, 80, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(data).decode()


async def main(model_filter=None):
    for info in PROVIDER_CATALOG:
        for model in info.models:
            if model_filter and model.name != model_filter:
                continue
            settings = Settings.from_mapping(
                {"active_provider": info.id, "providers": {info.id: {"model": model.name}}},
                env=os.environ,
            )
            if not settings.model.api_key:
                continue
            settings = replace(
                settings,
                model=replace(
                    settings.model,
                    thinking=info.id == "kimi",
                    reasoning_effort="low" if info.id == "kimi" else "none",
                ),
            )
            bundle = build_provider_bundle(settings)
            try:
                async with asyncio.timeout(60):
                    result = Runner.run_streamed(
                        Agent(
                            name="vision probe",
                            model=bundle.model,
                            model_settings=bundle.model_settings,
                        ),
                        [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": "Name the colors in the top-left, top-right, bottom-left, bottom-right quadrants, in that order. English only.",
                                    },
                                    {"type": "input_image", "image_url": test_image()},
                                ],
                            }
                        ],
                    )
                    count = 0
                    async for event in result.stream_events():
                        count += 1
                answer = str(result.final_output).lower()
                colors = ["red", "green", "blue", "yellow"]
                positions = [answer.find(color) for color in colors]
                passed = all(position >= 0 for position in positions) and positions == sorted(
                    positions
                )
                print(
                    json.dumps(
                        {
                            "provider": info.id,
                            "model": model.name,
                            "image_and_stream": "passed" if passed else "unverified",
                            "events": count,
                            "answer": answer[:300],
                        }
                    ),
                    flush=True,
                )
            except UnsupportedImageInputError:
                print(
                    json.dumps(
                        {
                            "provider": info.id,
                            "model": model.name,
                            "image_and_stream": "rejected_as_expected"
                            if not model.supports_image_input
                            else "failed",
                        }
                    ),
                    flush=True,
                )
            except Exception as exc:
                print(
                    json.dumps(
                        {
                            "provider": info.id,
                            "model": model.name,
                            "error": type(exc).__name__,
                            "message": str(exc).replace(settings.model.api_key, "[redacted]")[:400],
                        }
                    ),
                    flush=True,
                )
            finally:
                await bundle.client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--model")
    args = parser.parse_args()
    asyncio.run(main(args.model))
