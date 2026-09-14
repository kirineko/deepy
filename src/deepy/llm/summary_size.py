"""Conservative encoded-body sizing for summary batch planning."""

from __future__ import annotations

from typing import Any

from deepy.utils import json as json_utils

from .cache_context import CachePrefixSnapshot, canonical_tool, canonical_mcp_server
from .response_images import MAX_REQUEST_BYTES

# Reserve room for SDK envelope fields and tool-schema conversion overhead.
SUMMARY_SERIALIZATION_HEADROOM = 64 * 1024


def summary_instructions(prefix: CachePrefixSnapshot | None) -> str:
    if prefix is not None and prefix.system_instructions:
        return (
            f"{prefix.system_instructions}\n\n"
            "Deepy context compaction task: create a compact continuation summary. "
            "Do not call tools."
        )
    return "Create a compact continuation summary. Do not call tools."


def summary_body_fits(
    input_value: Any,
    *,
    prefix: CachePrefixSnapshot | None = None,
    tools: list[Any] | None = None,
    mcp_servers: list[Any] | None = None,
) -> bool:
    # Include both snapshots and live definitions conservatively. The request
    # hook remains the final authority on the SDK's actual serialized body.
    payload = {
        "input": input_value,
        "instructions": summary_instructions(prefix),
        "tools": [canonical_tool(tool) for tool in tools or []],
        "mcp_tools": [canonical_mcp_server(server) for server in mcp_servers or []],
        "prefix_tools": list(prefix.tools) if prefix else [],
        "prefix_mcp_tools": list(prefix.mcp_tools) if prefix else [],
    }
    encoded = json_utils.dumps(payload).encode("utf-8")
    return len(encoded) + SUMMARY_SERIALIZATION_HEADROOM <= MAX_REQUEST_BYTES
