from __future__ import annotations

from typing import cast

from deepy.todos import normalize_todo_items, todo_items_to_payload

from ..result import ToolResult
from ..search import SearchMode, SearchOutputMode, SearchRequest, search_project
from ..shell_command import (
    _build_question_summary,
    _parse_ask_user_questions,
    _todo_tool_metadata,
    _todo_tool_output,
)
from .state import ToolRuntimeState


class InteractionToolsMixin(ToolRuntimeState):
    def search(
        self,
        query: str,
        *,
        path: str = ".",
        glob: str | None = None,
        mode: str = "literal",
        output_mode: str = "content",
        case_sensitive: bool = True,
        context: int = 0,
        limit: int = 100,
        offset: int = 0,
        include_ignored: bool = False,
    ) -> str:
        name = "Search"
        request = SearchRequest(
            query=query,
            path=path,
            glob=glob,
            mode=cast(SearchMode, mode),
            output_mode=cast(SearchOutputMode, output_mode),
            case_sensitive=case_sensitive,
            context=context,
            limit=limit,
            offset=offset,
            include_ignored=include_ignored,
        )
        page = search_project(self.cwd, request)
        error = page.metadata.get("error")
        error_code = page.metadata.get("error_code")
        if isinstance(error, str) and error_code:
            return ToolResult.error_result(name, error, metadata=page.metadata).to_json()
        if error_code and not page.output:
            return ToolResult.error_result(
                name,
                "Search failed.",
                metadata=page.metadata,
            ).to_json()
        return ToolResult.ok_result(name, page.output, metadata=page.metadata).to_json()
    def ask_user_question(self, questions: object) -> str:
        parsed_questions, error = _parse_ask_user_questions(questions)
        if error is not None:
            return ToolResult.error_result("AskUserQuestion", error).to_json()
        return ToolResult(
            ok=True,
            name="AskUserQuestion",
            output=_build_question_summary(parsed_questions),
            metadata={"kind": "ask_user_question", "questions": parsed_questions},
            awaitUserResponse=True,
        ).to_json()
    def todo_write(self, todos: object | None = None) -> str:
        name = "todo_write"
        if todos is None:
            return ToolResult.ok_result(
                name,
                _todo_tool_output(self.todo_items, changed=False, read_only=True),
                metadata=_todo_tool_metadata(self.todo_items, changed=False, read_only=True),
            ).to_json()
        parsed, error = normalize_todo_items(todos)
        if error is not None or parsed is None:
            return ToolResult.error_result(
                name,
                error or "Invalid todo list.",
                metadata={"kind": "todo_list_error"},
            ).to_json()
        previous = todo_items_to_payload(self.todo_items)
        current = todo_items_to_payload(parsed)
        changed = previous != current
        self.todo_items = parsed
        return ToolResult.ok_result(
            name,
            _todo_tool_output(parsed, changed=changed, read_only=False),
            metadata=_todo_tool_metadata(parsed, changed=changed, read_only=False),
        ).to_json()
    def load_skill(self, name: str) -> str:
        from deepy.skills import find_skill, read_skill_body

        skill = find_skill(self.cwd, name)
        if skill is None:
            return ToolResult.error_result("load_skill", f"Skill not found: {name}").to_json()
        body = read_skill_body(skill)
        if not body:
            return ToolResult.error_result("load_skill", f"Skill is empty: {skill.name}").to_json()
        root = skill.path.parent
        output = (
            f"# Skill: {skill.name}\n\n"
            f"Description: {skill.description or '(no description)'}\n\n"
            f"Scope: {skill.scope}\n\n"
            f"Skill root: {root}\n\n"
            "All scripts, references, and assets in this skill are relative to the skill root.\n\n"
            "---\n\n"
            f"{body}"
        )
        return ToolResult.ok_result(
            "load_skill",
            output,
            metadata={
                "name": skill.name,
                "description": skill.description,
                "scope": skill.scope,
                "path": str(skill.path),
                "root": str(root),
            },
        ).to_json()
