"""Persist completed tool work after a rejected continuation without rerunning it."""
from __future__ import annotations

from typing import Any
from deepy.sessions import DeepySession


async def preserve_completed_items(session: DeepySession, result: Any, baseline: int) -> None:
    if result is None:
        return
    completed = [item.to_input_item() for item in getattr(result, "new_items", [])]
    current = await session.get_items()
    # SDK versions may already persist the tail before the next model invocation.
    # Preserve only the completed suffix not already written by that SDK.
    for count in range(min(len(current) - baseline, len(completed)), -1, -1):
        if count == 0 or current[-count:] == completed[:count]:
            await session.add_items(completed[count:])
            return
