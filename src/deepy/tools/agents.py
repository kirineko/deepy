from __future__ import annotations

from .builtin import ToolRuntime


def build_function_tools(runtime: ToolRuntime) -> list[object]:
    from agents import function_tool

    @function_tool(name_override="bash")
    def bash(command: str, timeout_ms: int = 120_000) -> str:
        """Run a shell command in the session working directory and return stdout/stderr JSON."""
        return runtime.bash(command, timeout_ms)

    @function_tool(name_override="read")
    def read(path: str, start_line: int = 1, limit: int | None = None) -> str:
        """Read a text file with line numbers or list a directory."""
        return runtime.read(path, start_line, limit)

    @function_tool(name_override="write")
    def write(path: str, content: str) -> str:
        """Create or replace a file after read-before-write checks."""
        return runtime.write(path, content)

    @function_tool(name_override="edit")
    def edit(path: str, old: str, new: str, replace_all: bool = False) -> str:
        """Replace exact text in a file after it has been read."""
        return runtime.edit(path, old, new, replace_all)

    @function_tool(name_override="AskUserQuestion")
    def ask_user_question(question: str) -> str:
        """Ask the user a blocking clarification question."""
        return runtime.ask_user_question(question)

    @function_tool(name_override="WebSearch")
    def web_search(query: str) -> str:
        """Search the web through the configured local command."""
        return runtime.web_search(query)

    return [bash, read, write, edit, ask_user_question, web_search]
