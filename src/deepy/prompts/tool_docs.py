from __future__ import annotations

from importlib import resources


TOOL_DOC_FILES = (
    "shell.md",
    "task_list.md",
    "task_output.md",
    "task_stop.md",
    "test_shell.md",
    "Search.md",
    "Read.md",
    "Write.md",
    "Update.md",
    "AskUserQuestion.md",
    "WebSearch.md",
    "WebFetch.md",
    "todo_write.md",
)


def load_tool_docs() -> str:
    docs = resources.files("deepy.data.tools")
    sections: list[str] = []
    for filename in TOOL_DOC_FILES:
        sections.append(docs.joinpath(filename).read_text(encoding="utf-8").strip())
    return "\n\n".join(sections)
