from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Mapping, Sequence, cast

from agents import ModelSettings
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from deepy.config import Settings
from deepy.llm.thinking import build_thinking_extra_body
from deepy.usage import TokenUsage, normalize_usage
from deepy.utils import log_debug_event
from deepy.utils import json as json_utils

INPUT_SUGGESTION_MODEL = "deepseek-v4-flash"
INPUT_SUGGESTION_DELAY_SECONDS = 0.3
MIN_ASSISTANT_REPLIES = 2
MAX_RECENT_HISTORY_ITEMS = 40

SUGGESTION_PROMPT = """[SUGGESTION MODE: Suggest what the user might naturally type next.]

FIRST: Read the LAST FEW LINES of the assistant's most recent message. Next-step
hints, tips, and actionable suggestions usually appear there. Then check the
user's recent messages and original request.

Predict what the user would type next, not what the assistant should do.

If the assistant's last message contains a hint like "Tip: type X" or
"type X to ...", extract X as the suggestion when it is natural.

Stay silent if the next step is not obvious from the conversation.

Format: 2-12 words, match the user's style. Or return an empty string.
Reply with ONLY the suggestion, no quotes or explanation."""

ALLOWED_SINGLE_WORDS = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "yea",
        "yup",
        "sure",
        "ok",
        "okay",
        "push",
        "commit",
        "deploy",
        "stop",
        "continue",
        "check",
        "exit",
        "quit",
        "no",
    }
)


@dataclass(frozen=True)
class InputSuggestion:
    text: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = INPUT_SUGGESTION_MODEL
    elapsed_ms: int = 0


@dataclass(frozen=True)
class InputSuggestionState:
    text: str | None = None
    visible: bool = False
    shown_at: float = 0.0


@dataclass
class InputSuggestionController:
    enabled: bool = True
    state: InputSuggestionState = field(default_factory=InputSuggestionState)
    last_accepted_method: Literal["tab", "right"] | None = None
    _version: int = 0

    def set_suggestion(self, text: str | None, *, visible: bool = True) -> None:
        if not self.enabled or not text:
            self.clear()
            return
        self._version += 1
        self.last_accepted_method = None
        self.state = InputSuggestionState(
            text=text,
            visible=visible,
            shown_at=time.time() if visible else 0.0,
        )

    async def set_suggestion_after_delay(self, text: str | None) -> None:
        if not text:
            self.clear()
            return
        self._version += 1
        version = self._version
        await asyncio.sleep(INPUT_SUGGESTION_DELAY_SECONDS)
        if version != self._version:
            return
        self.set_suggestion(text)

    def accept(self, method: Literal["tab", "right"] = "tab") -> str | None:
        if not self.state.text:
            return None
        text = self.state.text
        self._version += 1
        self.last_accepted_method = method
        self.state = InputSuggestionState(text=text, visible=False)
        return text

    def dismiss(self) -> None:
        self.clear()

    def hide(self) -> None:
        if self.state.text:
            self.state = InputSuggestionState(text=self.state.text, visible=False)

    def reveal(self) -> None:
        if self.enabled and self.state.text and not self.state.visible:
            self.state = InputSuggestionState(
                text=self.state.text,
                visible=True,
                shown_at=time.time(),
            )

    def clear(self) -> None:
        self._version += 1
        self.last_accepted_method = None
        self.state = InputSuggestionState()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.clear()


def input_suggestion_model_settings() -> ModelSettings:
    return ModelSettings(
        include_usage=True,
        store=False,
        extra_body=build_thinking_extra_body(False),
    )


def assistant_reply_count(items: Sequence[Mapping[str, Any]]) -> int:
    return sum(1 for item in items if _item_role(item) in {"assistant", "model"})


def is_eligible_for_input_suggestion(
    items: Sequence[Mapping[str, Any]],
    *,
    enabled: bool,
    interactive: bool = True,
    idle: bool = True,
    has_pending_questions: bool = False,
    turn_status: str = "completed",
) -> bool:
    return (
        enabled
        and interactive
        and idle
        and not has_pending_questions
        and turn_status == "completed"
        and assistant_reply_count(items) >= MIN_ASSISTANT_REPLIES
    )


def recent_suggestion_messages(items: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    recent = list(items)[-MAX_RECENT_HISTORY_ITEMS:]
    messages: list[dict[str, str]] = []
    for item in recent:
        role = _item_role(item)
        if role not in {"user", "assistant", "model"}:
            continue
        content = _item_text(item).strip()
        if not content:
            continue
        messages.append(
            {
                "role": "assistant" if role == "model" else role,
                "content": content,
            }
        )
    return messages


async def generate_input_suggestion(
    settings: Settings,
    items: Sequence[Mapping[str, Any]],
    *,
    timeout_seconds: float = 10.0,
) -> InputSuggestion | None:
    if not settings.model.api_key:
        _log_input_suggestion_debug(settings, {"status": "skipped", "reason": "missing_api_key"})
        return None
    messages = recent_suggestion_messages(items)
    if not messages:
        _log_input_suggestion_debug(settings, {"status": "skipped", "reason": "empty_context"})
        return None
    request_messages = cast(
        list[ChatCompletionMessageParam],
        [
            *messages,
            {"role": "user", "content": SUGGESTION_PROMPT},
        ],
    )
    client = AsyncOpenAI(base_url=settings.model.base_url, api_key=settings.model.api_key)
    settings_payload = input_suggestion_model_settings()
    started_at = time.time()
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=INPUT_SUGGESTION_MODEL,
                messages=request_messages,
                temperature=0,
                max_tokens=64,
                extra_body=settings_payload.extra_body,
                store=settings_payload.store,
            ),
            timeout=timeout_seconds,
        )
    except Exception as exc:
        _log_input_suggestion_debug(
            settings,
            {"status": "failed", "reason": "api_error", "error": exc},
        )
        return None
    text = ""
    choices = getattr(response, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        text = content if isinstance(content, str) else ""
    suggestion = parse_suggestion_text(text)
    if not suggestion:
        _log_input_suggestion_debug(settings, {"status": "skipped", "reason": "empty_response"})
        return None
    filter_reason = get_filter_reason(suggestion)
    if filter_reason:
        _log_input_suggestion_debug(
            settings,
            {
                "status": "filtered",
                "reason": filter_reason,
                "suggestion": suggestion,
            },
        )
        return None
    usage = normalize_usage(getattr(response, "usage", None))
    _log_input_suggestion_debug(
        settings,
        {
            "status": "generated",
            "model": INPUT_SUGGESTION_MODEL,
            "suggestion": suggestion,
            "usage": usage.to_dict(),
        },
    )
    return InputSuggestion(
        text=suggestion,
        usage=usage,
        elapsed_ms=int((time.time() - started_at) * 1000),
    )


def parse_suggestion_text(text: str) -> str:
    stripped = text.strip().strip('"').strip("'").strip()
    if not stripped:
        return ""
    if stripped.startswith("{"):
        try:
            parsed = json_utils.loads(stripped)
        except Exception:
            return stripped
        if isinstance(parsed, dict):
            raw = parsed.get("suggestion")
            return raw.strip() if isinstance(raw, str) else ""
    return stripped


def get_filter_reason(suggestion: str) -> str | None:
    lower = suggestion.lower().strip()
    word_count = len(suggestion.strip().split())

    if lower == "done":
        return "done"
    if (
        lower in {"nothing found", "nothing found."}
        or lower.startswith("nothing to suggest")
        or lower.startswith("no suggestion")
        or "silence is" in lower
        or "stay silent" in lower
        or lower == "silence"
    ):
        return "meta_text"
    if lower.startswith(
        (
            "api error:",
            "prompt is too long",
            "request timed out",
            "invalid api key",
            "image was too large",
        )
    ):
        return "error_message"
    if suggestion.startswith(("(", "[")) and suggestion.endswith((")", "]")):
        return "meta_wrapped"
    if _has_prefixed_label(suggestion):
        return "prefixed_label"
    if "\n" in suggestion or "*" in suggestion or "**" in suggestion:
        return "has_formatting"
    if len(suggestion) >= 100:
        return "too_long"
    if suggestion.endswith("?") or "?" in suggestion:
        return "question"
    if _has_cjk(suggestion):
        if len(suggestion) < 2:
            return "too_few_words"
        if len(suggestion) > 30:
            return "too_many_words"
    else:
        if word_count < 2 and not suggestion.startswith("/") and lower not in ALLOWED_SINGLE_WORDS:
            return "too_few_words"
        if word_count > 12:
            return "too_many_words"
    if _has_multiple_sentences(suggestion):
        return "multiple_sentences"
    if _is_evaluative(lower):
        return "evaluative"
    if _is_ai_voice(suggestion):
        return "ai_voice"
    return None


def with_recorded_input_suggestion_usage(
    suggestion: InputSuggestion | None,
    *,
    usage: TokenUsage | None = None,
) -> InputSuggestion | None:
    if suggestion is None or usage is None:
        return suggestion
    return replace(suggestion, usage=usage)


def _item_role(item: Mapping[str, Any]) -> str:
    role = item.get("role")
    if isinstance(role, str):
        return role
    item_type = item.get("type")
    if item_type == "message":
        raw_role = item.get("role")
        return raw_role if isinstance(raw_role, str) else ""
    return item_type if isinstance(item_type, str) else ""


def _item_text(item: Mapping[str, Any]) -> str:
    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, Mapping):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    output = item.get("output")
    return output if isinstance(output, str) else ""


def _has_cjk(value: str) -> bool:
    return any(
        "\u4e00" <= char <= "\u9fff"
        or "\u3040" <= char <= "\u30ff"
        or "\uac00" <= char <= "\ud7af"
        for char in value
    )


def _has_prefixed_label(value: str) -> bool:
    prefix, sep, rest = value.partition(":")
    return bool(sep and prefix.replace("_", "").isalnum() and rest.startswith(" "))


def _has_multiple_sentences(value: str) -> bool:
    for index, char in enumerate(value[:-2]):
        if char in ".!?" and value[index + 1] == " " and value[index + 2].isupper():
            return True
    return False


def _is_evaluative(lower: str) -> bool:
    phrases = (
        "thanks",
        "thank you",
        "looks good",
        "sounds good",
        "that works",
        "that worked",
        "that's all",
        "nice",
        "great",
        "perfect",
        "makes sense",
        "awesome",
        "excellent",
    )
    return any(phrase in lower for phrase in phrases)


def _is_ai_voice(value: str) -> bool:
    lower = value.lower()
    prefixes = (
        "let me",
        "i'll",
        "i've",
        "i'm",
        "i can",
        "i would",
        "i think",
        "i notice",
        "here's",
        "here is",
        "here are",
        "that's",
        "this is",
        "this will",
        "you can",
        "you should",
        "you could",
        "sure,",
        "of course",
        "certainly",
    )
    return lower.startswith(prefixes)


def _log_input_suggestion_debug(settings: Settings, payload: dict[str, Any]) -> None:
    if not settings.logging.debug:
        return
    log_debug_event(
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "location": "deepy.input_suggestions.generate_input_suggestion",
            **payload,
        }
    )
