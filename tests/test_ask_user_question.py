from __future__ import annotations

import json

from deepy.ui.ask_user_question import find_pending_ask_user_question
from deepy.ui.ask_user_question import format_ask_user_question_answers
from deepy.ui.ask_user_question import format_ask_user_question_decline
from deepy.ui.ask_user_question import build_answer_for_question
from deepy.ui.ask_user_question import build_options
from deepy.ui.ask_user_question import OTHER_VALUE
from deepy.ui.ask_user_question import AskUserQuestionItem
from deepy.ui.ask_user_question import AskUserQuestionOption
from deepy.ui.ask_user_question import normalize_questions


def _message(content: object, *, visible: bool = True) -> dict[str, object]:
    now = "2026-04-29T00:00:00.000Z"
    return {
        "id": "tool-message",
        "session_id": "session-id",
        "role": "tool",
        "content": json.dumps(content),
        "visible": visible,
        "created_at": now,
    }


def test_find_pending_ask_user_question_returns_latest_pending_tool_message():
    pending = find_pending_ask_user_question(
        [
            _message({"ok": True, "name": "read"}),
            _message(
                {
                    "ok": True,
                    "name": "AskUserQuestion",
                    "awaitUserResponse": True,
                    "metadata": {
                        "kind": "ask_user_question",
                        "questions": [
                            {
                                "question": "Which package manager should we use?",
                                "options": [
                                    {
                                        "label": "npm",
                                        "description": "Use package-lock.json.",
                                    },
                                    {"label": "yarn"},
                                ],
                            }
                        ],
                    },
                }
            ),
        ],
        "waiting_for_user",
    )

    assert pending is not None
    assert pending.message_id == "tool-message"
    assert pending.questions[0].question == "Which package manager should we use?"
    assert pending.questions[0].options[0].description == "Use package-lock.json."


def test_find_pending_ask_user_question_preserves_multiple_questions_in_order():
    pending = find_pending_ask_user_question(
        [
            _message(
                {
                    "ok": True,
                    "name": "AskUserQuestion",
                    "awaitUserResponse": True,
                    "metadata": {
                        "kind": "ask_user_question",
                        "questions": [
                            {
                                "question": "Use default description?",
                                "options": [{"label": "Yes"}, {"label": "Custom"}],
                            },
                            {
                                "question": "Where should the project be created?",
                                "options": [
                                    {"label": "Current directory"},
                                    {"label": "Custom path"},
                                ],
                            },
                        ],
                    },
                }
            )
        ],
        "waiting_for_user",
    )

    assert pending is not None
    assert [question.question for question in pending.questions] == [
        "Use default description?",
        "Where should the project be created?",
    ]


def test_find_pending_ask_user_question_ignores_questions_unless_waiting():
    pending = find_pending_ask_user_question(
        [
            _message(
                {
                    "ok": True,
                    "name": "AskUserQuestion",
                    "awaitUserResponse": True,
                    "metadata": {
                        "kind": "ask_user_question",
                        "questions": [{"question": "Continue?", "options": [{"label": "Yes"}]}],
                    },
                }
            )
        ],
        "processing",
    )

    assert pending is None


def test_normalize_questions_drops_invalid_items():
    questions = normalize_questions(
        [
            {"question": "  Continue? ", "options": [{"label": " Yes "}]},
            {"question": "", "options": [{"label": "No"}]},
            {"question": "Missing options"},
        ]
    )

    assert len(questions) == 1
    assert questions[0].question == "Continue?"
    assert questions[0].options[0].label == "Yes"


def test_format_ask_user_question_answers_creates_model_readable_text():
    assert format_ask_user_question_answers(
        {
            "Which package manager?": "yarn",
            "Any notes?": "Use the existing lockfile",
        }
    ) == (
        'User has answered your questions: "Which package manager?"="yarn", '
        '"Any notes?"="Use the existing lockfile". '
        "You can now continue with the user's answers in mind."
    )


def test_format_ask_user_question_decline_creates_decline_text():
    assert "declined to answer" in format_ask_user_question_decline()


def test_build_options_appends_other_option():
    question = AskUserQuestionItem(
        question="Package manager?",
        options=[AskUserQuestionOption(label="npm", description="Use package-lock.json.")],
    )

    options = build_options(question)

    assert [(option.label, option.value, option.description, option.is_other) for option in options] == [
        ("npm", "npm", "Use package-lock.json.", False),
        ("Other / custom answer", OTHER_VALUE, None, True),
    ]


def test_build_answer_for_question_handles_single_select_and_other():
    question = AskUserQuestionItem(
        question="Package manager?",
        options=[AskUserQuestionOption(label="npm")],
    )
    options = build_options(question)

    assert build_answer_for_question(question, options[0], [], "") == "npm"
    assert build_answer_for_question(question, options[1], [], " yarn ") == "yarn"
    assert build_answer_for_question(question, options[1], [], "   ") is None
    assert build_answer_for_question(question, None, [], "") is None


def test_build_answer_for_question_handles_multi_select():
    question = AskUserQuestionItem(
        question="Features?",
        options=[AskUserQuestionOption(label="tests"), AskUserQuestionOption(label="docs")],
        multi_select=True,
    )

    assert build_answer_for_question(question, None, ["tests", "docs"], "") == "tests, docs"
    assert build_answer_for_question(question, None, ["tests", OTHER_VALUE], " lint ") == (
        "tests, lint"
    )
    assert build_answer_for_question(question, None, [OTHER_VALUE], "   ") is None
    assert build_answer_for_question(question, None, [], "") is None
