from __future__ import annotations

from rich.console import Console

from deepy.ui.shared.input.ask_user_question import OTHER_VALUE
from deepy.ui.shared.input.ask_user_question import AskUserQuestionItem
from deepy.ui.shared.input.ask_user_question import AskUserQuestionOptionEntry
from deepy.ui.shared.input.ask_user_question import build_answer_for_question
from deepy.ui.shared.input.ask_user_question import build_options
from deepy.ui.shared.input.ask_user_question import format_ask_user_question_answers
from deepy.ui.shared.input.ask_user_question import format_ask_user_question_decline
from deepy.ui.shared.input.ask_user_question import normalize_questions
from deepy.ui.classic.terminal_types import InputFunc

def _collect_pending_question_response(
    console: Console,
    pending_questions: list[dict[str, object]],
    input_func: InputFunc | None = None,
) -> str:
    questions = normalize_questions(pending_questions)
    if not questions:
        return ""
    answers: dict[str, str] = {}
    chooser = input_func or (lambda prompt: console.input(f"{prompt}: "))
    for question in questions:
        answer = _prompt_for_question(console, question, chooser)
        if answer is None:
            return format_ask_user_question_decline()
        answers[question.question] = answer
    return format_ask_user_question_answers(answers)


def _prompt_for_question(
    console: Console,
    question: AskUserQuestionItem,
    input_func: InputFunc,
) -> str | None:
    options = build_options(question)
    console.print(f"\n[bold]Question:[/bold] {question.question}")
    for index, option in enumerate(options, 1):
        detail = f" - {option.description}" if option.description else ""
        console.print(f"{index}. {option.label}{detail}")
    prompt = (
        "Answer numbers separated by commas, custom text, or empty to decline"
        if question.multi_select
        else "Answer number, custom text, or empty to decline"
    )
    raw_answer = input_func(prompt).strip()
    if not raw_answer:
        return None
    direct_option = None if question.multi_select else _option_from_token(options, raw_answer)
    if direct_option is not None and direct_option.is_other:
        custom_answer = input_func(_custom_answer_prompt(direct_option)).strip()
        return build_answer_for_question(question, direct_option, [], custom_answer)
    if question.multi_select and _multi_select_needs_custom_text(options, raw_answer):
        custom_answer = input_func(_custom_answer_prompt(options[-1])).strip()
        raw_answer = f"{raw_answer}, {custom_answer}" if custom_answer else raw_answer
    return _answer_question_from_text(question, raw_answer)


def _answer_question_from_text(question: AskUserQuestionItem, raw_answer: str) -> str | None:
    options = build_options(question)
    if question.multi_select:
        selected_values: list[str] = []
        custom_values: list[str] = []
        for token in [part.strip() for part in raw_answer.split(",") if part.strip()]:
            option = _option_from_token(options, token)
            if option is not None:
                selected_values.append(option.value)
            else:
                custom_values.append(token)
        if custom_values:
            selected_values.append(OTHER_VALUE)
        return build_answer_for_question(
            question,
            None,
            selected_values,
            ", ".join(custom_values),
        )

    option = _option_from_token(options, raw_answer)
    if option is None:
        option = next((item for item in options if item.value == OTHER_VALUE), None)
    other_text = raw_answer if option is not None and option.is_other else ""
    return build_answer_for_question(question, option, [], other_text)


def _multi_select_needs_custom_text(
    options: list[AskUserQuestionOptionEntry],
    raw_answer: str,
) -> bool:
    tokens = [part.strip() for part in raw_answer.split(",") if part.strip()]
    saw_other = False
    saw_custom_text = False
    for token in tokens:
        option = _option_from_token(options, token)
        if option is not None and option.is_other:
            saw_other = True
        elif option is None:
            saw_custom_text = True
    return saw_other and not saw_custom_text


def _custom_answer_prompt(option: AskUserQuestionOptionEntry) -> str:
    return "自定义回答" if option.label.startswith("自定义") else "Custom answer"


def _option_from_token(
    options: list[AskUserQuestionOptionEntry],
    token: str,
) -> AskUserQuestionOptionEntry | None:
    if token.isdigit():
        index = int(token) - 1
        if 0 <= index < len(options):
            return options[index]
    lowered = token.casefold()
    return next((option for option in options if option.label.casefold() == lowered), None)
