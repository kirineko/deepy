from __future__ import annotations

from typing import Any

from deepy.utils import json as json_utils


COMPACT_PROMPT_BASE = """Your task is to create a detailed summary of the conversation so far, paying close attention to the user's explicit requests and your previous actions.
This summary should be thorough in capturing technical details, code patterns, and architectural decisions that would be essential for continuing development work without losing context.

Before providing your final summary, wrap your analysis in <analysis> tags to organize your thoughts and ensure you've covered all necessary points. In your analysis process:

1. Chronologically analyze each message and section of the conversation. For each section thoroughly identify:
   - The user's explicit requests and intents
   - Your approach to addressing the user's requests
   - Key decisions, technical concepts and code patterns
   - Specific details like:
     - file names
     - full code snippets
     - function signatures
     - file edits
   - Errors that you ran into and how you fixed them
   - Pay special attention to specific user feedback that you received, especially if the user told you to do something differently.
2. Double-check for technical accuracy and completeness, addressing each required element thoroughly.

Your summary should include the following sections:

1. Primary Request and Intent: Capture all of the user's explicit requests and intents in detail
2. Key Technical Concepts: List all important technical concepts, technologies, and frameworks discussed.
3. Files and Code Sections: Enumerate specific files and code sections examined, modified, or created. Pay special attention to the most recent messages and include full code snippets where applicable and include a summary of why this file read or edit is important.
4. Errors and fixes: List all errors that you ran into, and how you fixed the error. Pay special attention to specific user feedback that you received, especially if the user told you to do something differently.
5. Problem Solving: Document problems solved and any ongoing troubleshooting efforts.
6. All user messages: List ALL user messages that are not tool results. These are critical for understanding the users' feedback and changing intent.
7. Pending Tasks: Outline any pending tasks that you have explicitly been asked to work on.
8. Current Work: Describe in detail precisely what was being worked on immediately before this summary request, paying special attention to the most recent messages from both user and assistant. Include file names and code snippets where applicable.
9. Optional Next Step: List the next step that you will take that is related to the most recent work you were doing. IMPORTANT: ensure that this step is DIRECTLY in line with the user's most recent explicit requests and the task you were working on immediately before this summary request. If your last task was concluded, then only list next steps if they are explicitly in line with the user's request. Do not start on tangential requests or old requests that were already completed without confirming with the user first.

Output structure:

<analysis>
[Your thought process, ensuring all points are covered thoroughly and accurately]
</analysis>

<summary>
1. Primary Request and Intent:
   [Detailed description]

2. Key Technical Concepts:
   - [Concept 1]
   - [Concept 2]

3. Files and Code Sections:
   - [File Name 1]
      - [Summary of why this file is important]
      - [Summary of the changes made to this file, if any]
      - [Important Code Snippet]

4. Errors and fixes:
   - [Detailed description of error 1]:
      - [How you fixed the error]
      - [User feedback on the error if any]

5. Problem Solving:
   [Description of solved problems and ongoing troubleshooting]

6. All user messages:
   - [Detailed non-tool user message]

7. Pending Tasks:
   - [Task 1]

8. Current Work:
   [Precise description of current work]

9. Optional Next Step:
   [Optional next step to take]
</summary>"""


COMPACT_MESSAGE_KEYS = (
    "id",
    "role",
    "content",
    "type",
    "name",
    "tool_calls",
    "tool_call_id",
    "output",
    "created_at",
)


def build_compact_prompt(
    session_messages: list[dict[str, Any]],
    *,
    focus_instruction: str | None = None,
) -> str:
    jsonl = "\n".join(_compact_message_json(message) for message in session_messages)
    focus = ""
    if focus_instruction and focus_instruction.strip():
        focus = (
            "\n\nUser focus instruction:\n"
            "The user explicitly requested this focus for compaction. Prioritize it without "
            "dropping current task state:\n"
            f"{focus_instruction.strip()}"
        )
    return f"{COMPACT_PROMPT_BASE}{focus}\n\nconversation below:\n\n```jsonl\n{jsonl}\n```"


def build_compact_summary_message(summary: str) -> dict[str, str]:
    stripped = strip_compact_analysis(summary).strip()
    return {
        "role": "user",
        "content": (
            "Previous context has been compacted by Deepy. Continue from this summary:\n\n"
            f"{stripped}"
        ),
    }


def strip_compact_analysis(text: str) -> str:
    result = text
    while True:
        start = result.find("<analysis>")
        end = result.find("</analysis>")
        if start == -1 or end == -1 or end < start:
            break
        result = result[:start] + result[end + len("</analysis>") :]
    summary_start = result.find("<summary>")
    summary_end = result.find("</summary>")
    if summary_start != -1 and summary_end != -1 and summary_end > summary_start:
        result = result[summary_start + len("<summary>") : summary_end]
    return result.strip()


def _compact_message_json(message: dict[str, Any]) -> str:
    payload = {key: message[key] for key in COMPACT_MESSAGE_KEYS if key in message}
    return json_utils.dumps(payload)
