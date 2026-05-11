from __future__ import annotations

from .builtin import ToolRuntime


def build_function_tools(runtime: ToolRuntime) -> list[object]:
    from agents import function_tool

    @function_tool(name_override="bash")
    def bash(command: str, timeout_ms: int = 120_000) -> str:
        return runtime.bash(command, timeout_ms)

    @function_tool(name_override="read")
    def read(path: str, start_line: int = 1, limit: int | None = None) -> str:
        return runtime.read(path, start_line, limit)

    @function_tool(name_override="write")
    def write(path: str, content: str) -> str:
        return runtime.write(path, content)

    @function_tool(name_override="edit")
    def edit(path: str, old: str, new: str, replace_all: bool = False) -> str:
        return runtime.edit(path, old, new, replace_all)

    @function_tool(name_override="AskUserQuestion")
    def ask_user_question(question: str) -> str:
        return runtime.ask_user_question(question)

    @function_tool(name_override="WebSearch")
    def web_search(query: str) -> str:
        return runtime.web_search(query)

    return [bash, read, write, edit, ask_user_question, web_search]
