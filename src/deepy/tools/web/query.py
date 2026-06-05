from __future__ import annotations

import re

from deepy.config import Settings
from deepy.utils import json as json_utils

from ..tool_dataclasses import WebSearchPreparation

def _prepare_web_search_query(query: str) -> WebSearchPreparation:
    stripped = " ".join(query.split())
    contains_chinese = _contains_chinese_char(stripped)
    if contains_chinese:
        return WebSearchPreparation(
            original_query=query,
            resolved_query=stripped,
            dominant_language="zh",
            language_reason="The query contains Chinese characters.",
        )
    return WebSearchPreparation(
        original_query=query,
        resolved_query=stripped,
        dominant_language="en",
        language_reason="The query does not contain Chinese characters.",
    )


def _prepare_web_search_query_with_llm(
    query: str,
    settings: Settings,
) -> tuple[WebSearchPreparation, str | None]:
    stripped = " ".join(query.split())
    if not settings.model.api_key or not settings.model.base_url or not settings.model.name:
        return (
            _prepare_web_search_query(query),
            "WebSearch default mode requires a valid LLM configuration.",
        )
    try:
        decision = _decide_search_language_with_llm(stripped, settings)
        contains_chinese = _contains_chinese_char(stripped)
        if decision["dominant_language"] == "en" and contains_chinese:
            translated = _translate_search_query_with_llm(stripped, "English", settings)
            if translated:
                return (
                    WebSearchPreparation(
                        original_query=query,
                        resolved_query=translated,
                        dominant_language="en",
                        language_reason=decision["reason"],
                        translated=True,
                    ),
                    None,
                )
        if decision["dominant_language"] == "zh" and not contains_chinese:
            translated = _translate_search_query_with_llm(stripped, "Chinese", settings)
            if translated:
                return (
                    WebSearchPreparation(
                        original_query=query,
                        resolved_query=translated,
                        dominant_language="zh",
                        language_reason=decision["reason"],
                        translated=True,
                    ),
                    None,
                )
        return (
            WebSearchPreparation(
                original_query=query,
                resolved_query=stripped,
                dominant_language=decision["dominant_language"],
                language_reason=decision["reason"],
            ),
            None,
        )
    except Exception as exc:
        return _prepare_web_search_query(query), str(exc)


def _decide_search_language_with_llm(query: str, settings: Settings) -> dict[str, str]:
    prompt = (
        "Decide whether the topic below has more useful online material in English or Chinese.\n\n"
        "Topic:\n"
        "```text\n"
        f"{query}\n"
        "```\n\n"
        "Return strict JSON:\n"
        '{"dominant_language":"en"|"zh","reason":"one short sentence"}\n'
        "Do not include markdown or any extra text."
    )
    from .. import builtin

    parsed = _parse_json_response(builtin._web_search_chat(settings, prompt))
    dominant_language = parsed.get("dominant_language")
    if not isinstance(dominant_language, str) or dominant_language not in {"en", "zh"}:
        raise ValueError(f"Unexpected dominant language: {dominant_language}")
    reason = parsed.get("reason")
    return {
        "dominant_language": dominant_language,
        "reason": reason if isinstance(reason, str) else "",
    }


def _translate_search_query_with_llm(query: str, target_language: str, settings: Settings) -> str:
    prompt = (
        f"Translate the query text below into {target_language}.\n\n"
        "Requirements:\n"
        "- Preserve product names, library names, API names, versions, and abbreviations when appropriate.\n"
        "- Return only the translated query, without quotes or explanation.\n\n"
        "Query:\n"
        "```text\n"
        f"{query}\n"
        "```"
    )
    from .. import builtin

    return _strip_code_fence(builtin._web_search_chat(settings, prompt)).strip().strip("\"'")


def _web_search_chat(settings: Settings, prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.model.api_key, base_url=settings.model.base_url)
    response = client.chat.completions.create(
        model=settings.model.name,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            text = part.get("text") if isinstance(part, dict) else getattr(part, "text", "")
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts).strip()
    return ""


def _parse_json_response(text: str) -> dict[str, object]:
    cleaned = _strip_code_fence(text).strip()
    try:
        parsed = json_utils.loads(cleaned)
    except json_utils.JSONDecodeError:
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace < 0 or last_brace <= first_brace:
            raise ValueError(f"Failed to parse JSON response: {cleaned or '<empty>'}")
        parsed = json_utils.loads(cleaned[first_brace : last_brace + 1])
    if not isinstance(parsed, dict):
        raise ValueError("JSON response must be an object.")
    return parsed


def _strip_code_fence(text: str) -> str:
    trimmed = text.strip()
    match = re.match(r"^```(?:[\w-]+)?\n([\s\S]*?)\n```$", trimmed)
    return match.group(1) if match else trimmed


def _contains_chinese_char(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _format_web_search_activity_label(query: str) -> str:
    normalized = " ".join(query.split())
    if len(normalized) > 180:
        normalized = normalized[:177] + "..."
    return f"WebSearch: {normalized}"

