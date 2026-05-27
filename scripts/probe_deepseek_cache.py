#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from typing import Any


API_URL = "https://api.deepseek.com/chat/completions"


def main() -> int:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("DEEPSEEK_API_KEY is required.", file=sys.stderr)
        return 2
    model = os.environ.get("DEEPSEEK_PROBE_MODEL") or os.environ.get("DEEPY_MODEL") or "deepseek-v4-pro"

    stable_messages = [
        {"role": "system", "content": "You are a cache probe. Answer briefly."},
        {"role": "user", "content": "Remember this exact prefix: alpha beta gamma."},
    ]
    append_only = [*stable_messages, {"role": "user", "content": "Reply with one word: ok."}]
    mutated = [
        {"role": "system", "content": "You are a cache probe. Answer briefly!"},
        stable_messages[1],
        {"role": "user", "content": "Reply with one word: ok."},
    ]

    print("warming append-only prefix")
    warm = _chat(api_key, model, append_only)
    time.sleep(1.0)
    print("probing append-only prefix")
    repeat = _chat(api_key, model, append_only)
    time.sleep(1.0)
    print("probing mutated prefix")
    changed = _chat(api_key, model, mutated)

    for label, payload in (("warm", warm), ("append_only", repeat), ("mutated", changed)):
        usage = payload.get("usage") if isinstance(payload, dict) else None
        print(f"{label}: {_cache_line(usage)}")
    return 0


def _chat(api_key: str, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "thinking": {"type": "disabled"},
        },
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _cache_line(usage: Any) -> str:
    if not isinstance(usage, dict):
        return "usage=unknown"
    hit = _int_field(usage.get("prompt_cache_hit_tokens"))
    miss = _int_field(usage.get("prompt_cache_miss_tokens"))
    if miss == 0:
        prompt_tokens = _int_field(usage.get("prompt_tokens"))
        if prompt_tokens and hit:
            miss = max(prompt_tokens - hit, 0)
    total = hit + miss
    ratio = hit / total * 100 if total else 0.0
    return f"cache_hit={hit} cache_miss={miss} cache_hit_ratio={ratio:.1f}%"


def _int_field(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
