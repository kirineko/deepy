from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from deepy.utils import json as json_utils


OTHER_VALUE = "__other__"


@dataclass(frozen=True)
class AskUserQuestionOption:
    label: str
    description: str | None = None


@dataclass(frozen=True)
class AskUserQuestionItem:
    question: str
    options: list[AskUserQuestionOption]
    multi_select: bool | None = None


@dataclass(frozen=True)
class PendingAskUserQuestion:
    message_id: str
    session_id: str
    questions: list[AskUserQuestionItem]


@dataclass(frozen=True)
class AskUserQuestionOptionEntry:
    label: str
    value: str
    description: str | None = None
    is_other: bool = False


def build_options(question: AskUserQuestionItem | None) -> list[AskUserQuestionOptionEntry]:
    if question is None:
        return []
    custom_label, custom_description = _custom_answer_text(question.question)
    return [
        *[
            AskUserQuestionOptionEntry(
                label=option.label,
                value=option.label,
                description=option.description,
            )
            for option in question.options
        ],
        AskUserQuestionOptionEntry(
            label=custom_label,
            value=OTHER_VALUE,
            description=custom_description,
            is_other=True,
        ),
    ]


def build_answer_for_question(
    question: AskUserQuestionItem,
    focused_option: AskUserQuestionOptionEntry | None,
    selected_values: list[str],
    other_text: str,
) -> str | None:
    trimmed_other = other_text.strip()
    if question.multi_select:
        labels = [value.strip() for value in selected_values if value != OTHER_VALUE and value.strip()]
        if OTHER_VALUE in selected_values and not trimmed_other:
            return None
        if trimmed_other:
            labels.append(trimmed_other)
        return ", ".join(labels) if labels else None

    if focused_option is None:
        return None
    if focused_option.is_other:
        return trimmed_other or None
    return focused_option.label


def find_pending_ask_user_question(
    messages: list[Mapping[str, Any]],
    status: str | None,
) -> PendingAskUserQuestion | None:
    if status != "waiting_for_user":
        return None

    for message in reversed(messages):
        if message.get("role") != "tool" or message.get("visible") is False:
            continue
        questions = parse_ask_user_question_content(message.get("content"))
        if not questions:
            continue
        message_id = message.get("id")
        session_id = message.get("session_id") or message.get("sessionId")
        if not isinstance(message_id, str) or not isinstance(session_id, str):
            continue
        return PendingAskUserQuestion(
            message_id=message_id,
            session_id=session_id,
            questions=questions,
        )
    return None


def parse_ask_user_question_content(content: Any) -> list[AskUserQuestionItem]:
    if not isinstance(content, str) or not content:
        return []
    try:
        parsed = json_utils.loads(content)
    except json_utils.JSONDecodeError:
        return []
    if not isinstance(parsed, Mapping) or parsed.get("awaitUserResponse") is not True:
        return []
    metadata = parsed.get("metadata")
    if not isinstance(metadata, Mapping) or metadata.get("kind") != "ask_user_question":
        return []
    return normalize_questions(metadata.get("questions"))


def normalize_questions(raw: Any) -> list[AskUserQuestionItem]:
    if not isinstance(raw, list):
        return []

    questions: list[AskUserQuestionItem] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        question = _stripped_string(item.get("question"))
        raw_options = item.get("options")
        if not question or not isinstance(raw_options, list):
            continue
        options = [
            option
            for raw_option in raw_options
            if (option := normalize_option(raw_option)) is not None
        ]
        if not options:
            continue
        multi_select = item.get("multiSelect")
        questions.append(
            AskUserQuestionItem(
                question=question,
                options=options,
                multi_select=multi_select if isinstance(multi_select, bool) else None,
            )
        )
    return questions


def normalize_option(raw: Any) -> AskUserQuestionOption | None:
    if not isinstance(raw, Mapping):
        return None
    label = _stripped_string(raw.get("label"))
    if not label:
        return None
    description = _stripped_string(raw.get("description"))
    return AskUserQuestionOption(label=label, description=description or None)


def format_ask_user_question_answers(answers: Mapping[str, str]) -> str:
    answer_text = ", ".join(
        f'"{_escape_answer_part(question)}"="{_escape_answer_part(answer)}"'
        for question, answer in answers.items()
    )
    return (
        f"User has answered your questions: {answer_text}. "
        "You can now continue with the user's answers in mind."
    )


def format_ask_user_question_decline() -> str:
    return (
        "The user declined to answer the questions. Continue with the available context, "
        "or ask again if the information is required."
    )


def _stripped_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _custom_answer_text(question: str) -> tuple[str, str]:
    if _contains_cjk(question):
        return "自定义回答", "输入自己的答案。"
    return "Custom answer", "Type your own answer."


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _escape_answer_part(value: str) -> str:
    normalized = " ".join(value.split())
    return normalized.replace("\\", "\\\\").replace('"', '\\"')
