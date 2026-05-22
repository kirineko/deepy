from __future__ import annotations

import asyncio
import ast
import gzip
import json
import os
import shlex
import sys
import time

import deepy.tools.search as search_module
from deepy.background_tasks import BackgroundTaskLimitError
from deepy.config import Settings
from deepy.config.settings import (
    DEFAULT_WEB_SEARCH_SEARXNG_URL,
    ModelConfig,
    ToolsConfig,
    WebSearchToolConfig,
)
from deepy.tools import ToolResult, ToolRuntime
from deepy.tools.agents import build_function_tools, make_mimo_compatible_tool_schema
from deepy.tools.builtin import (
    DEFAULT_LINE_LIMIT,
    MAX_BASH_OUTPUT_CHARS,
    MAX_LINE_LENGTH,
    MAX_WEB_SEARCH_CALLS_PER_TURN,
    _build_shell_command,
    _extract_bash_sentinel,
)


def decode(payload: str) -> dict:
    return json.loads(payload)


def repeat_x_command(count: int) -> str:
    return f"{shlex.quote(sys.executable)} -c \"import sys; sys.stdout.write('x' * {count})\""


def write_encoded_stdout_command(text: str, encoding: str) -> str:
    payload = repr(text.encode(encoding))
    return shlex.join([sys.executable, "-c", f"import sys; sys.stdout.buffer.write({payload})"])


def test_tool_result_shape_is_stable():
    payload = decode(ToolResult.ok_result("read_file", "hello").to_json())

    assert payload == {
        "ok": True,
        "name": "read_file",
        "output": "hello",
        "error": None,
        "metadata": {},
        "awaitUserResponse": False,
    }


def test_todo_write_updates_reads_and_clears_state(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    todos = [
        {"id": "inspect", "content": "Inspect code", "status": "completed"},
        {"id": "implement", "content": "Implement todo tool", "status": "in_progress"},
        {"id": "verify", "content": "Run tests", "status": "pending"},
    ]

    written = decode(runtime.todo_write(todos))

    assert written["ok"] is True
    assert written["name"] == "todo_write"
    assert written["metadata"]["kind"] == "todo_list"
    assert written["metadata"]["counts"] == {
        "total": 3,
        "pending": 1,
        "in_progress": 1,
        "completed": 1,
    }
    assert written["metadata"]["changed"] is True

    read = decode(runtime.todo_write())
    assert read["ok"] is True
    assert read["metadata"]["readOnly"] is True
    assert read["metadata"]["todos"] == todos

    unchanged = decode(runtime.todo_write(todos))
    assert unchanged["metadata"]["changed"] is False

    cleared = decode(runtime.todo_write([]))
    assert cleared["ok"] is True
    assert cleared["metadata"]["todos"] == []


def test_todo_write_rejects_invalid_updates_and_preserves_previous_state(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    first = [{"id": "one", "content": "One", "status": "in_progress"}]
    assert decode(runtime.todo_write(first))["ok"] is True

    failed = decode(
        runtime.todo_write(
            [
                {"id": "one", "content": "One", "status": "in_progress"},
                {"id": "two", "content": "Two", "status": "in_progress"},
            ]
        )
    )

    assert failed["ok"] is False
    assert "only one todo item may be in_progress" in failed["error"]
    assert decode(runtime.todo_write())["metadata"]["todos"] == first


def test_build_function_tools_registers_todo_write(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    tools = build_function_tools(runtime)

    todo_tool = next(tool for tool in tools if tool.name == "todo_write")
    schema = todo_tool.params_json_schema

    assert schema["properties"]["todos"]["items"]["required"] == ["id", "content", "status"]
    assert schema["properties"]["todos"]["items"]["properties"]["status"]["enum"] == [
        "pending",
        "in_progress",
        "completed",
    ]


def test_function_tool_repairs_unquoted_snapshot_id_arguments(tmp_path):
    target = tmp_path / "index.html"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    read_payload = decode(runtime.read_file("index.html"))
    tool = next(tool for tool in build_function_tools(runtime) if tool.name == "write_file")

    payload = decode(
        asyncio.run(
            tool.on_invoke_tool(
                None,
                (
                    '{"file_path":"index.html","content":"new\\n","overwrite":true,'
                    f'"snapshot_id":{read_payload["metadata"]["snapshot_id"]},'
                    '"snapshot_token":null,"expected_hash":null}'
                ),
            )
        )
    )

    assert payload["ok"] is True
    assert payload["name"] == "write_file"
    assert payload["metadata"]["argumentRepair"] is True
    assert payload["metadata"]["repairApplied"] is True
    assert "quote_tool_ids" in payload["metadata"]["repairOperations"]
    assert target.read_text(encoding="utf-8") == "new\n"


def test_function_tool_rejects_unsafe_malformed_content_arguments(tmp_path):
    target = tmp_path / "index.html"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    tool = next(tool for tool in build_function_tools(runtime) if tool.name == "write_file")

    payload = decode(
        asyncio.run(
            tool.on_invoke_tool(
                None,
                '{"file_path":"index.html","content":new\\n,"overwrite":true,'
                '"snapshot_id":null,"snapshot_token":null,"expected_hash":null}',
            )
        )
    )

    assert payload["ok"] is False
    assert payload["name"] == "write_file"
    assert payload["metadata"]["error_code"] == "invalid_arguments"
    assert payload["metadata"]["retryable"] is True
    assert payload["metadata"]["repairApplied"] is False
    assert target.read_text(encoding="utf-8") == "old\n"


def test_read_marks_file_and_edit_requires_prior_read(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    denied = decode(runtime.edit("a.txt", "one", "ONE"))
    assert denied["ok"] is False
    assert "read before" in denied["error"]

    read_payload = decode(runtime.read_file("a.txt"))
    assert read_payload["ok"] is True
    assert "1: one" in read_payload["output"]

    edited = decode(runtime.edit("a.txt", "one", "ONE"))
    assert edited["ok"] is True
    assert "-one" in edited["metadata"]["diff"]
    assert "+ONE" in edited["metadata"]["diff"]
    assert edited["metadata"]["diff_preview"] == edited["metadata"]["diff"]
    assert target.read_text(encoding="utf-8") == "ONE\ntwo\n"


def test_read_directory_lists_entries(tmp_path):
    (tmp_path / "dir").mkdir()
    (tmp_path / "reference").mkdir()
    (tmp_path / "spec").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / ".venv").mkdir()
    (tmp_path / "dist").mkdir()
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("."))

    assert payload["ok"] is True
    assert payload["metadata"]["kind"] == "directory"
    assert "dir/" in payload["output"]
    assert "reference/" in payload["output"]
    assert "spec/" in payload["output"]
    assert "a.txt" in payload["output"]
    assert ".git/" not in payload["output"]
    assert ".venv/" not in payload["output"]
    assert "dist/" not in payload["output"]
    assert payload["metadata"]["entryCount"] == 8
    assert payload["metadata"]["visibleEntryCount"] == 5
    assert payload["metadata"]["ignoredEntryCount"] == 3


def test_read_directory_respects_gitignore(tmp_path):
    (tmp_path / ".gitignore").write_text(
        "ignored.log\nignored_dir/\nspec/\nreference/\n", encoding="utf-8"
    )
    (tmp_path / "ignored.log").write_text("secret", encoding="utf-8")
    (tmp_path / "ignored_dir").mkdir()
    (tmp_path / "visible.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "spec").mkdir()
    (tmp_path / "reference").mkdir()
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("."))

    assert payload["ok"] is True
    assert "visible.txt" in payload["output"]
    assert "spec/" not in payload["output"]
    assert "reference/" not in payload["output"]
    assert "ignored.log" not in payload["output"]
    assert "ignored_dir/" not in payload["output"]
    assert payload["metadata"]["ignoredEntryCount"] == 4


def test_read_resolves_unique_relative_suffix(tmp_path):
    target_dir = tmp_path / "src" / "deepy"
    target_dir.mkdir(parents=True)
    target_dir.joinpath("settings.py").write_text("value = 1\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("settings.py"))

    assert payload["ok"] is True
    assert payload["metadata"]["path"] == str(target_dir / "settings.py")
    assert "1: value = 1" in payload["output"]


def test_read_suffix_matching_ignores_gitignored_candidates(tmp_path):
    (tmp_path / ".gitignore").write_text("generated/\n", encoding="utf-8")
    source_dir = tmp_path / "src"
    generated_dir = tmp_path / "generated"
    source_dir.mkdir()
    generated_dir.mkdir()
    source_dir.joinpath("settings.py").write_text("value = 1\n", encoding="utf-8")
    generated_dir.joinpath("settings.py").write_text("value = 2\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("settings.py"))

    assert payload["ok"] is True
    assert payload["metadata"]["path"] == str(source_dir / "settings.py")
    assert "value = 1" in payload["output"]


def test_read_rejects_ambiguous_relative_suffix(tmp_path):
    first = tmp_path / "src" / "a"
    second = tmp_path / "tests" / "a"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    first.joinpath("settings.py").write_text("one\n", encoding="utf-8")
    second.joinpath("settings.py").write_text("two\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("settings.py"))

    assert payload["ok"] is False
    assert "ambiguous" in payload["error"]
    assert str(first / "settings.py") in payload["error"]
    assert str(second / "settings.py") in payload["error"]


def test_read_notebook_returns_textual_cells_and_outputs(tmp_path):
    notebook = tmp_path / "demo.ipynb"
    notebook.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "source": ["# Title\n", "intro"],
                    },
                    {
                        "cell_type": "code",
                        "source": "print('hi')\n",
                        "outputs": [
                            {"output_type": "stream", "text": ["hi\n"]},
                            {
                                "output_type": "display_data",
                                "data": {
                                    "text/plain": "'value'",
                                    "image/png": "abcd",
                                },
                            },
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("demo.ipynb"))

    assert payload["ok"] is True
    assert payload["metadata"]["kind"] == "notebook"
    assert payload["metadata"]["trackedForWrite"] is False
    assert "1: # Cell 1 (markdown)" in payload["output"]
    assert "2: # Title" in payload["output"]
    assert "5: print('hi')" in payload["output"]
    assert "7: hi" in payload["output"]
    assert "10: [image/png 4 chars]" in payload["output"]


def test_read_invalid_notebook_returns_parse_error(tmp_path):
    notebook = tmp_path / "broken.ipynb"
    notebook.write_text("{not json", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("broken.ipynb"))

    assert payload["ok"] is False
    assert "Failed to parse notebook JSON" in payload["error"]


def test_read_image_returns_follow_up_message(tmp_path):
    image = tmp_path / "pixel.png"
    image.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010804000000b51c0c020000000b4944415478da63fcff1f0003030200eed9d17f0000000049454e44ae426082"
        )
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("pixel.png"))

    assert payload["ok"] is True
    assert payload["output"] == "File loaded."
    assert payload["metadata"]["mime"] == "image/png"
    assert payload["metadata"]["bytes"] == image.stat().st_size
    assert len(payload["followUpMessages"]) == 1
    follow_up = payload["followUpMessages"][0]
    assert follow_up["role"] == "system"
    assert "pixel.png" in follow_up["content"][0]["text"]
    assert "contentParams" not in follow_up
    assert follow_up["content"][1]["type"] == "input_image"
    assert follow_up["content"][1]["image_url"].startswith("data:image/png;base64,")


def _write_fake_pdf(path, page_count: int):
    pages = "\n".join(f"{idx} 0 obj << /Type /Page >> endobj" for idx in range(1, page_count + 1))
    path.write_bytes(f"%PDF-1.4\n{pages}\ntrailer << /Type /Pages >>\n%%EOF".encode("latin1"))


def test_read_pdf_returns_base64_with_metadata(tmp_path):
    pdf = tmp_path / "small.pdf"
    _write_fake_pdf(pdf, 2)
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("small.pdf"))

    assert payload["ok"] is True
    assert payload["output"].startswith("data:application/pdf;base64,")
    assert payload["metadata"]["mime"] == "application/pdf"
    assert payload["metadata"]["encoding"] == "base64"
    assert payload["metadata"]["pageCount"] == 2
    assert payload["metadata"]["pages"] is None


def test_read_large_pdf_requires_page_range(tmp_path):
    pdf = tmp_path / "large.pdf"
    _write_fake_pdf(pdf, 11)
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("large.pdf"))

    assert payload["ok"] is False
    assert 'provide "pages" to read a range' in payload["error"]
    assert payload["metadata"]["pageCount"] == 11


def test_read_pdf_accepts_page_range_metadata(tmp_path):
    pdf = tmp_path / "large.pdf"
    _write_fake_pdf(pdf, 11)
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("large.pdf", pages="2-3"))

    assert payload["ok"] is True
    assert payload["metadata"]["pageCount"] == 11
    assert payload["metadata"]["pages"] == "2-3"


def test_read_pdf_rejects_invalid_page_range(tmp_path):
    pdf = tmp_path / "small.pdf"
    _write_fake_pdf(pdf, 2)
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    too_many = decode(runtime.read_file("small.pdf", pages="1-21"))
    assert too_many["ok"] is False
    assert "exceeds 20 pages" in too_many["error"]

    out_of_bounds = decode(runtime.read_file("small.pdf", pages="3"))
    assert out_of_bounds["ok"] is False
    assert "exceeds total page count" in out_of_bounds["error"]


def test_read_limits_large_files_by_default(tmp_path):
    target = tmp_path / "large.txt"
    target.write_text(
        "".join(f"line {idx}\n" for idx in range(DEFAULT_LINE_LIMIT + 5)),
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("large.txt"))

    assert payload["ok"] is True
    assert payload["metadata"]["lineCount"] == DEFAULT_LINE_LIMIT
    assert payload["metadata"]["lineLimit"] == DEFAULT_LINE_LIMIT
    assert payload["metadata"]["totalLines"] == DEFAULT_LINE_LIMIT + 5
    assert payload["metadata"]["truncated"] is True
    assert payload["metadata"]["trackedForWrite"] is False
    assert f"{DEFAULT_LINE_LIMIT + 1}: line" not in payload["output"]

    denied = decode(runtime.write("large.txt", "changed"))
    assert denied["ok"] is False
    assert "read before" in denied["error"]


def test_read_truncates_long_lines(tmp_path):
    target = tmp_path / "long.txt"
    target.write_text("x" * (MAX_LINE_LENGTH + 5), encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("long.txt"))

    assert payload["ok"] is True
    assert "... [truncated]" in payload["output"]
    assert payload["metadata"]["truncated"] is True
    assert payload["metadata"]["trackedForWrite"] is False


def test_partial_read_does_not_unlock_existing_file_for_edit(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("a.txt", start_line=2, limit=1))
    denied = decode(runtime.edit("a.txt", "two", "TWO"))
    denied_edit_text = decode(
        runtime.edit_text("a.txt", "two", "TWO", auto_read_if_missing_snapshot=False)
    )

    assert payload["ok"] is True
    assert payload["metadata"]["trackedForWrite"] is False
    assert denied["ok"] is False
    assert "read before" in denied["error"]
    assert denied_edit_text["ok"] is False
    assert "read before" in denied_edit_text["error"]


def test_partial_read_returns_snippet_metadata(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("a.txt", start_line=2, limit=1))

    assert payload["ok"] is True
    assert payload["metadata"]["trackedForWrite"] is False
    assert payload["metadata"]["snippet"]["id"] == "snippet_1"
    assert payload["metadata"]["snippet"]["filePath"] == str(target)
    assert payload["metadata"]["snippet"]["startLine"] == 2
    assert payload["metadata"]["snippet"]["endLine"] == 2


def test_edit_can_scope_replacement_by_snippet_id(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text(
        "\n".join(["alpha", "target = 1", "omega", "beta", "target = 1", "done"]),
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    read_payload = decode(runtime.read_file("sample.txt", start_line=4, limit=2))
    snippet_id = read_payload["metadata"]["snippet"]["id"]
    edit_payload = decode(runtime.edit(None, "target = 1", "target = 2", snippet_id=snippet_id))

    assert edit_payload["ok"] is True
    assert edit_payload["metadata"]["read_scope_type"] == "snippet"
    assert edit_payload["metadata"]["scope"]["startLine"] == 4
    assert edit_payload["metadata"]["scope"]["endLine"] == 5
    assert edit_payload["metadata"]["line_endings"] == "LF"
    assert "+target = 2" in edit_payload["metadata"]["diff_preview"]
    assert target.read_text(encoding="utf-8") == "\n".join(
        ["alpha", "target = 1", "omega", "beta", "target = 2", "done"]
    )


def test_edit_rejects_unknown_snippet_id(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.edit(None, "old", "new", snippet_id="snippet_404"))

    assert payload["ok"] is False
    assert "Unknown snippet_id" in payload["error"]


def test_edit_text_treats_string_null_snippet_id_as_absent(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.edit_text("a.txt", "old", "new", snippet_id="null"))

    assert payload["ok"] is True
    assert payload["metadata"]["autoReadBeforeEdit"] is True
    assert target.read_text(encoding="utf-8") == "new\n"


def test_edit_text_can_recover_snapshot_id_passed_as_snippet_id(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    read_payload = decode(runtime.read_file("a.txt"))

    payload = decode(
        runtime.edit_text(
            None,
            "old",
            "new",
            snippet_id=read_payload["metadata"]["snapshot_id"],
        )
    )

    assert payload["ok"] is True
    assert payload["metadata"]["inferredFromSnapshotId"] == read_payload["metadata"]["snapshot_id"]
    assert target.read_text(encoding="utf-8") == "new\n"


def test_edit_text_auto_promotes_partial_read_to_full_file_edit(tmp_path):
    target = tmp_path / "styles.css"
    target.write_text(
        ".navbar {\n  display: flex;\n}\n\n.lang-toggle {\n  color: #5a67d8;\n}\n",
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    read_payload = decode(runtime.read_file("styles.css", start_line=1, limit=3))
    payload = decode(
        runtime.edit_text(
            "styles.css",
            ".lang-toggle {\n  color: #5a67d8;\n}",
            ".lang-toggle {\n  color: #fff;\n}",
        )
    )

    assert read_payload["metadata"]["trackedForWrite"] is False
    assert payload["ok"] is True
    assert payload["metadata"]["autoReadBeforeEdit"] is True
    assert payload["metadata"]["autoReadReason"] == "partial"
    assert payload["metadata"]["read_scope_type"] == "full"
    assert target.read_text(encoding="utf-8").endswith(".lang-toggle {\n  color: #fff;\n}\n")


def test_edit_text_falls_back_to_full_file_when_snippet_scope_misses(tmp_path):
    target = tmp_path / "styles.css"
    target.write_text(
        ".navbar {\n  display: flex;\n}\n\n.lang-toggle {\n  color: #5a67d8;\n}\n",
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    read_payload = decode(runtime.read_file("styles.css", start_line=1, limit=3))
    snippet_id = read_payload["metadata"]["snippet"]["id"]
    payload = decode(
        runtime.edit_text(
            "styles.css",
            ".lang-toggle {\n  color: #5a67d8;\n}",
            ".lang-toggle {\n  color: #fff;\n}",
            snippet_id=snippet_id,
        )
    )

    assert payload["ok"] is True
    assert payload["metadata"]["read_scope_type"] == "full"
    assert payload["metadata"]["fallbackFromSnippetId"] == snippet_id
    assert target.read_text(encoding="utf-8").endswith(".lang-toggle {\n  color: #fff;\n}\n")


def test_edit_returns_candidate_snippets_when_old_text_is_not_unique(tmp_path):
    target = tmp_path / "duplicate.txt"
    target.write_text("city\ncity\nsalary\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("duplicate.txt"))
    payload = decode(runtime.edit("duplicate.txt", "city", "location"))

    assert payload["ok"] is False
    assert (
        payload["error"]
        == "old_string is not unique; use snippet_id, replace_all, or provide more context."
    )
    assert payload["metadata"]["match_count"] == 2
    assert payload["metadata"]["scope"]["type"] == "full"
    assert len(payload["metadata"]["candidates"]) == 2
    assert payload["metadata"]["candidates"][0]["snippet_id"] == "snippet_1"
    assert payload["metadata"]["candidates"][0]["start_line"] == 1
    assert "city" in payload["metadata"]["candidates"][0]["preview"]


def test_edit_candidate_snippet_can_scope_follow_up_edit(tmp_path):
    target = tmp_path / "duplicate.txt"
    target.write_text("city\ncity\nsalary\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("duplicate.txt"))
    duplicate = decode(runtime.edit("duplicate.txt", "city", "location"))
    snippet_id = duplicate["metadata"]["candidates"][1]["snippet_id"]
    edited = decode(runtime.edit("duplicate.txt", "city", "location", snippet_id=snippet_id))

    assert edited["ok"] is True
    assert edited["metadata"]["read_scope_type"] == "snippet"
    assert target.read_text(encoding="utf-8") == "city\nlocation\nsalary\n"


def test_edit_uses_loose_escape_match_when_quotes_are_overescaped(tmp_path):
    target = tmp_path / "quotes.py"
    target.write_text('print("hello")\n', encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("quotes.py"))
    payload = decode(runtime.edit("quotes.py", 'print(\\"hello\\")', 'print("hi")'))

    assert payload["ok"] is True
    assert payload["metadata"]["matched_via"] == "loose_escape"
    assert target.read_text(encoding="utf-8") == 'print("hi")\n'


def test_edit_uses_llm_escape_correction_when_configured(tmp_path, monkeypatch):
    target = tmp_path / "query.py"
    target.write_text("params['city_json'] = f'\"{city}\"'\n", encoding="utf-8")
    runtime = ToolRuntime(
        cwd=tmp_path,
        settings=Settings(
            model=ModelConfig(
                api_key="sk-test",
                base_url="https://api.deepseek.com",
                name="deepseek-chat",
            )
        ),
    )
    prompts: list[tuple[str, str, str, str]] = []

    def fake_correction_chat(settings, snippet_text, old, new, matched_text):
        prompts.append((snippet_text, old, new, matched_text))
        return (
            "<response>"
            "<corrected_old_string><![CDATA[params['city_json'] = f'\"{city}\"']]></corrected_old_string>"
            "<corrected_new_string><![CDATA[params['city_json'] = city]]></corrected_new_string>"
            "</response>"
        )

    monkeypatch.setattr("deepy.tools.builtin._edit_correction_chat", fake_correction_chat)

    decode(runtime.read_file("query.py"))
    payload = decode(
        runtime.edit(
            "query.py",
            "params['city_json'] = f'\\\\\"{city}\\\\\"'",
            "params['city_json'] = city",
        )
    )

    assert payload["ok"] is True
    assert payload["metadata"]["matched_via"] == "llm_escape_correction"
    assert target.read_text(encoding="utf-8") == "params['city_json'] = city\n"
    assert prompts[0][3] == "params['city_json'] = f'\"{city}\"'"


def test_edit_returns_closest_match_metadata_when_old_text_is_missing(tmp_path):
    target = tmp_path / "near.txt"
    target.write_text("alpha\nbeta = 1\ngamma\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("near.txt"))
    payload = decode(runtime.edit("near.txt", "bet = 1", "beta = 2"))

    assert payload["ok"] is False
    assert payload["error"] == "old_string not found in file."
    closest = payload["metadata"]["closest_match"]
    assert closest["snippet_id"] == "snippet_1"
    assert closest["start_line"] == 2
    assert closest["end_line"] == 2
    assert closest["strategy"] == "fuzzy_window"
    assert closest["similarity"] >= 0.45
    assert "beta = 1" in closest["preview"]


def test_edit_detects_mtime_change_after_read(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("one\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("a.txt"))
    target.write_text("changed\n", encoding="utf-8")
    os.utime(target, ns=(target.stat().st_atime_ns, target.stat().st_mtime_ns + 1_000_000))

    payload = decode(runtime.edit("a.txt", "changed", "updated"))

    assert payload["ok"] is False
    assert "changed since it was read" in payload["error"]


def test_edit_text_preserves_stale_protection_after_read(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("one\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("a.txt"))
    target.write_text("changed\n", encoding="utf-8")
    os.utime(target, ns=(target.stat().st_atime_ns, target.stat().st_mtime_ns + 1_000_000))

    payload = decode(runtime.edit_text("a.txt", "changed", "updated"))

    assert payload["ok"] is False
    assert "changed since it was read" in payload["error"]
    assert target.read_text(encoding="utf-8") == "changed\n"


def test_write_allows_new_file_but_existing_file_requires_read(tmp_path):
    existing = tmp_path / "existing.txt"
    existing.write_text("old", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    created = decode(runtime.write("new.txt", "hello"))
    assert created["ok"] is True
    assert "+hello" in created["metadata"]["diff"]
    assert created["metadata"]["diff_preview"] == created["metadata"]["diff"]

    denied = decode(runtime.write("existing.txt", "changed"))
    assert denied["ok"] is False
    assert "read before" in denied["error"]


def test_write_file_creates_new_files_and_edit_text_edits_existing_files(tmp_path):
    target = tmp_path / "existing.txt"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    created = decode(runtime.write_file("new.txt", "hello\n"))
    assert created["ok"] is True
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "hello\n"

    denied = decode(runtime.write_file("existing.txt", "changed\n"))
    assert denied["ok"] is False
    assert "overwrite" in denied["error"]

    edited = decode(runtime.edit_text("existing.txt", "old", "new"))

    assert edited["ok"] is True
    assert edited["metadata"]["autoReadBeforeEdit"] is True
    assert "-old" in edited["metadata"]["diff"]
    assert "+new" in edited["metadata"]["diff"]
    assert edited["metadata"]["diff_preview"] == edited["metadata"]["diff"]
    assert target.read_text(encoding="utf-8") == "new\n"


def test_read_file_returns_snapshot_hash_and_edit_text_enforces_expected_count(tmp_path):
    target = tmp_path / "existing.txt"
    target.write_text("old\nold\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    read_payload = decode(runtime.read_file("existing.txt"))

    assert read_payload["ok"] is True
    assert read_payload["name"] == "read_file"
    assert read_payload["metadata"]["snapshot_id"].startswith("snapshot_")
    assert len(read_payload["metadata"]["content_hash"]) == 64

    mismatch = decode(
        runtime.edit_text(
            "existing.txt",
            "old",
            "new",
            replace_all=True,
            expected_occurrences=1,
        )
    )
    assert mismatch["ok"] is False
    assert mismatch["metadata"]["error_code"] == "expected_count_mismatch"
    assert mismatch["metadata"]["expectedOccurrences"] == 1
    assert mismatch["metadata"]["actualOccurrences"] == 2

    edited = decode(
        runtime.edit_text(
            "existing.txt",
            "old",
            "new",
            replace_all=True,
            expected_occurrences=2,
        )
    )

    assert edited["ok"] is True
    assert edited["name"] == "edit_text"
    assert edited["metadata"]["occurrences"] == 2
    assert target.read_text(encoding="utf-8") == "new\nnew\n"


def test_write_file_requires_overwrite_intent_and_snapshot_for_existing_file(tmp_path):
    target = tmp_path / "existing.txt"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    created = decode(runtime.write_file("new.txt", "hello\n"))
    assert created["ok"] is True
    assert created["name"] == "write_file"
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "hello\n"

    denied = decode(runtime.write_file("existing.txt", "changed\n"))
    assert denied["ok"] is False
    assert denied["metadata"]["error_code"] == "invalid_arguments"

    read_payload = decode(runtime.read_file("existing.txt"))
    assert isinstance(read_payload["metadata"]["snapshot_token"], int)
    replaced = decode(
        runtime.write_file(
            "existing.txt",
            "changed\n",
            overwrite=True,
            snapshot_token=read_payload["metadata"]["snapshot_token"],
        )
    )

    assert replaced["ok"] is True
    assert target.read_text(encoding="utf-8") == "changed\n"


def test_write_file_rejects_mismatched_snapshot_token(tmp_path):
    target = tmp_path / "existing.txt"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    read_payload = decode(runtime.read_file("existing.txt"))

    rejected = decode(
        runtime.write_file(
            "existing.txt",
            "changed\n",
            overwrite=True,
            snapshot_token=read_payload["metadata"]["snapshot_token"] + 1,
        )
    )

    assert rejected["ok"] is False
    assert rejected["metadata"]["error_code"] == "stale_snapshot"
    assert rejected["metadata"]["expectedSnapshotToken"] == read_payload["metadata"]["snapshot_token"] + 1
    assert target.read_text(encoding="utf-8") == "old\n"


def test_edit_text_enforces_expected_occurrences_without_modify_alias(tmp_path):
    target = tmp_path / "existing.txt"
    target.write_text("old\nold\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.edit_text(
            "existing.txt",
            "old",
            "new",
            replace_all=True,
            expected_occurrences=1,
        )
    )

    assert payload["ok"] is False
    assert payload["name"] == "edit_text"
    assert payload["metadata"]["error_code"] == "expected_count_mismatch"
    assert target.read_text(encoding="utf-8") == "old\nold\n"


def test_edit_text_rejects_noop_with_structured_error(tmp_path):
    target = tmp_path / "existing.txt"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("existing.txt"))
    payload = decode(runtime.edit_text("existing.txt", "old", "old"))

    assert payload["ok"] is False
    assert payload["metadata"]["error_code"] == "no_op"


def test_mutation_rejects_workspace_escape_and_symlink_escape(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    outside = decode(runtime.write_file("../outside.txt", "no\n"))
    assert outside["ok"] is False
    assert outside["metadata"]["error_code"] == "path_policy"

    external_dir = tmp_path.parent / f"{tmp_path.name}-external"
    external_dir.mkdir()
    link = tmp_path / "escape"
    link.symlink_to(external_dir, target_is_directory=True)

    escaped = decode(runtime.write_file("escape/file.txt", "no\n"))
    assert escaped["ok"] is False
    assert escaped["metadata"]["error_code"] in {"path_policy", "symlink_policy"}


def test_sensitive_file_policy_requires_approval_without_writing(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.write_file(".env", "TOKEN=secret\n"))

    assert payload["ok"] is False
    assert payload["metadata"]["error_code"] == "approval_required"
    assert payload["metadata"]["policyDecision"] == "requires_approval"
    assert not (tmp_path / ".env").exists()


def test_apply_patch_add_update_delete_and_move(tmp_path):
    target = tmp_path / "existing.txt"
    target.write_text("old\n", encoding="utf-8")
    moved = tmp_path / "move_me.txt"
    moved.write_text("move\n", encoding="utf-8")
    delete = tmp_path / "delete_me.txt"
    delete.write_text("delete\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    decode(runtime.read_file("existing.txt"))
    decode(runtime.read_file("move_me.txt"))
    decode(runtime.read_file("delete_me.txt"))

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "create_file",
                    "file_path": "created.txt",
                    "content": "created\n",
                },
                {
                    "type": "replace_block",
                    "file_path": "existing.txt",
                    "old_text": "old\n",
                    "new_text": "new\n",
                    "expected_occurrences": 1,
                },
                {
                    "type": "move_file",
                    "file_path": "move_me.txt",
                    "destination_path": "moved.txt",
                },
                {
                    "type": "delete_file",
                    "file_path": "delete_me.txt",
                },
            ]
        )
    )

    assert payload["ok"] is True
    assert payload["name"] == "apply_patch"
    assert (tmp_path / "created.txt").read_text(encoding="utf-8") == "created\n"
    assert target.read_text(encoding="utf-8") == "new\n"
    assert not moved.exists()
    assert (tmp_path / "moved.txt").read_text(encoding="utf-8") == "move\n"
    assert not delete.exists()
    assert str(tmp_path / "created.txt") in payload["metadata"]["changedFiles"]
    delete_op = next(
        item for item in payload["metadata"]["operations"] if item["operation"] == "delete_file"
    )
    assert delete_op["backupCreated"] is True
    assert (tmp_path / ".deepy" / "backups").is_dir()
    assert "-old" in payload["metadata"]["diff"]
    assert "+new" in payload["metadata"]["diff"]


def test_apply_patch_returns_full_multi_file_diff_preview(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "create_file",
                    "file_path": "index.html",
                    "content": "".join(f"<p>index {index}</p>\n" for index in range(50)),
                },
                {
                    "type": "create_file",
                    "file_path": "styles.css",
                    "content": "".join(
                        f".item-{index} {{ color: red; }}\n" for index in range(50)
                    ),
                },
                {
                    "type": "create_file",
                    "file_path": "main.js",
                    "content": "".join(f"console.log({index});\n" for index in range(50)),
                },
                {
                    "type": "create_file",
                    "file_path": "README.md",
                    "content": "".join(f"line {index}\n" for index in range(50)),
                },
            ]
        )
    )

    assert payload["ok"] is True
    assert payload["metadata"]["path"] == "4 files"
    assert len(payload["metadata"]["changedFiles"]) == 4
    assert "index 49" in payload["metadata"]["diff"]
    assert "line 49" in payload["metadata"]["diff"]
    preview = payload["metadata"]["diff_preview"]
    assert preview == payload["metadata"]["diff"]
    assert "index 49" in preview
    assert "line 49" in preview
    assert "truncated" not in preview


def test_apply_patch_preflight_failure_leaves_files_unchanged(tmp_path):
    target = tmp_path / "existing.txt"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    decode(runtime.read_file("existing.txt"))

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "create_file",
                    "file_path": "created.txt",
                    "content": "created\n",
                },
                {
                    "type": "replace_block",
                    "file_path": "existing.txt",
                    "old_text": "missing\n",
                    "new_text": "new\n",
                    "expected_occurrences": 1,
                },
            ]
        )
    )

    assert payload["ok"] is False
    assert payload["metadata"]["error_code"] == "patch_apply_error"
    assert payload["metadata"]["preflightFailed"] is True
    assert target.read_text(encoding="utf-8") == "old\n"
    assert not (tmp_path / "created.txt").exists()


def test_apply_patch_rejects_patch_string_payload(tmp_path):
    target = tmp_path / "src" / "app.rs"
    target.parent.mkdir()
    target.write_text("fn old() {}\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.apply_patch(
            """```text
*** Begin Patch
*** Update File: a/src/app.rs
--- a/src/app.rs
+++ b/src/app.rs
@@
-fn old() {}
+fn new() {}
*** End Patch
```"""
        )
    )

    assert payload["ok"] is False
    assert payload["metadata"]["error_code"] == "patch_parse_error"
    assert payload["metadata"]["expectedProtocol"] == "structured_operations"
    assert target.read_text(encoding="utf-8") == "fn old() {}\n"


def test_apply_patch_create_file_uses_literal_structured_path(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "create_file",
                    "file_path": "src/new.rs",
                    "content": "fn main() {}\n",
                }
            ]
        )
    )

    assert payload["ok"] is True
    assert (tmp_path / "src" / "new.rs").read_text(encoding="utf-8") == "fn main() {}\n"


def test_apply_patch_replace_block_matches_eof_without_trailing_newline(tmp_path):
    target = tmp_path / "README.md"
    target.write_text("title", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "replace_block",
                    "file_path": "README.md",
                    "old_text": "title\n",
                    "new_text": "heading\n",
                    "expected_occurrences": 1,
                }
            ]
        )
    )

    assert payload["ok"] is True
    assert target.read_text(encoding="utf-8") == "heading"


def test_apply_patch_replace_block_handles_yaml_list_text(tmp_path):
    target = tmp_path / "items.yml"
    target.write_text("- old\n- keep\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "replace_block",
                    "file_path": "items.yml",
                    "old_text": "- old\n- keep\n",
                    "new_text": "- new\n- keep\n",
                    "expected_occurrences": 1,
                }
            ]
        )
    )

    assert payload["ok"] is True
    assert target.read_text(encoding="utf-8") == "- new\n- keep\n"


def test_apply_patch_accepts_unprefixed_replacement_pair_hunks(tmp_path):
    target = tmp_path / "src" / "main.rs"
    target.parent.mkdir()
    target.write_text(
        """fn main() {
    let test_cases = vec![
        ("III", 3),
        ("IV", 4),
        ("IX", 9),
        ("LVIII", 58),
    ];

    for (roman, expected) in &test_cases {
        println!("{roman} {expected}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic() {
        assert_eq!(1, 1);
    }

    #[test]
    fn test_extra() {
        assert_eq!(2, 2);
    }
}
""",
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "replace_block",
                    "file_path": str(target),
                    "old_text": """    let test_cases = vec![
        ("III", 3),
        ("IV", 4),
        ("IX", 9),
        ("LVIII", 58),
    ];
""",
                    "new_text": """    let test_cases = vec![
        ("III", 3),
        ("IV", 4),
    ];
""",
                    "expected_occurrences": 1,
                },
                {
                    "type": "replace_block",
                    "file_path": str(target),
                    "old_text": """    #[test]
    fn test_basic() {
        assert_eq!(1, 1);
    }

    #[test]
    fn test_extra() {
        assert_eq!(2, 2);
    }
""",
                    "new_text": """    #[test]
    fn test_examples() {
        assert_eq!(1, 1);
    }
""",
                    "expected_occurrences": 1,
                },
            ]
        )
    )

    assert payload["ok"] is True
    updated = target.read_text(encoding="utf-8")
    assert '        ("IX", 9),' not in updated
    assert "fn test_basic()" not in updated
    assert "fn test_extra()" not in updated
    assert "fn test_examples()" in updated
    assert payload["metadata"]["changedFiles"] == [str(target)]


def test_apply_patch_accepts_css_replacement_blocks_with_selector_prefixes(tmp_path):
    target = tmp_path / "styles.css"
    target.write_text(
        """:root {
--accent: #3b82f6;
}

.about-text p {
    margin-bottom: 1rem;
    color: #555;
}

.about-stats {
    display: grid;
    gap: 1rem;
}
""",
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "replace_block",
                    "file_path": "styles.css",
                    "old_text": """:root {
--accent: #3b82f6;
}

.about-text p {
    margin-bottom: 1rem;
    color: #555;
}

.about-stats {
    display: grid;
    gap: 1rem;
}
""",
                    "new_text": """:root {
--accent: #10b981;
}

.about-text p {
    margin-bottom: 1rem;
    color: #444;
}

.about-skills {
    display: grid;
    gap: 0.75rem;
}

.dot {
    width: 8px;
    height: 8px;
}
""",
                    "expected_occurrences": 1,
                }
            ]
        )
    )

    assert payload["ok"] is True
    updated = target.read_text(encoding="utf-8")
    assert "--accent: #10b981" in updated
    assert ".about-skills" in updated
    assert ".dot" in updated
    assert ".about-stats" not in updated


def test_apply_patch_insert_after_anchor(tmp_path):
    target = tmp_path / "index.html"
    target.write_text(
        """<section id="about">

  <p>Old bio</p>
</section>
""",
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "insert_after",
                    "file_path": "index.html",
                    "anchor": "  <p>Old bio</p>\n",
                    "content": "  <p>New bio</p>\n",
                    "expected_occurrences": 1,
                }
            ]
        )
    )

    assert payload["ok"] is True
    assert target.read_text(encoding="utf-8") == """<section id="about">

  <p>Old bio</p>
  <p>New bio</p>
</section>
"""


def test_apply_patch_replace_all_returns_actual_count(tmp_path):
    target = tmp_path / "index.html"
    target.write_text(
        """<p>Old bio</p>
<p>Old bio</p>
""",
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "replace_all",
                    "file_path": "index.html",
                    "old_text": "Old bio",
                    "new_text": "New bio",
                }
            ]
        )
    )

    assert payload["ok"] is True
    assert payload["metadata"]["operations"][0]["actualOccurrences"] == 2
    assert target.read_text(encoding="utf-8") == """<p>New bio</p>
<p>New bio</p>
"""


def test_apply_patch_insert_before_anchor(tmp_path):
    target = tmp_path / "styles.css"
    target.write_text(".about {\n  display: grid;\n}\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "insert_before",
                    "file_path": "styles.css",
                    "anchor": ".about {\n",
                    "content": ".about-tags {\n  display: flex;\n}\n\n",
                    "expected_occurrences": 1,
                }
            ]
        )
    )

    assert payload["ok"] is True
    assert target.read_text(encoding="utf-8").startswith(
        ".about-tags {\n  display: flex;\n}\n\n.about {\n"
    )


def test_apply_patch_replace_file_requires_freshness_token(tmp_path):
    target = tmp_path / "README.md"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    rejected = decode(
        runtime.apply_patch(
            [
                {
                    "type": "replace_file",
                    "file_path": "README.md",
                    "content": "new\n",
                    "overwrite": True,
                }
            ]
        )
    )
    assert rejected["ok"] is False
    assert rejected["metadata"]["failures"][0]["error_code"] == "stale_snapshot"

    read_payload = decode(runtime.read_file("README.md"))
    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "replace_file",
                    "file_path": "README.md",
                    "content": "new\n",
                    "overwrite": True,
                    "snapshot_token": read_payload["metadata"]["snapshot_token"],
                }
            ]
        )
    )

    assert payload["ok"] is True
    assert target.read_text(encoding="utf-8") == "new\n"


def test_apply_patch_rejects_invalid_structured_operation_fields(tmp_path):
    target = tmp_path / "README.md"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "delete_file",
                    "file_path": "README.md",
                    "content": "unexpected",
                }
            ]
        )
    )

    assert payload["ok"] is False
    assert payload["metadata"]["error_code"] == "patch_parse_error"
    assert payload["metadata"]["failures"][0]["invalidFields"] == ["content"]
    assert target.exists()


def test_apply_patch_expected_occurrences_mismatch_leaves_file_unchanged(tmp_path):
    target = tmp_path / "README.md"
    target.write_text("same\nsame\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "replace_block",
                    "file_path": "README.md",
                    "old_text": "same\n",
                    "new_text": "changed\n",
                    "expected_occurrences": 1,
                }
            ]
        )
    )

    assert payload["ok"] is False
    assert payload["metadata"]["error_code"] == "patch_apply_error"
    assert payload["metadata"]["failures"][0]["error_code"] == "expected_count_mismatch"
    assert target.read_text(encoding="utf-8") == "same\nsame\n"


def test_bat_and_cmd_new_files_default_to_crlf_without_bom(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    bat = decode(runtime.write_file("script.bat", "echo hello\n"))
    cmd = decode(runtime.write_file("script.cmd", "echo hello\n"))

    assert bat["ok"] is True
    assert cmd["ok"] is True
    assert (tmp_path / "script.bat").read_bytes() == b"echo hello\r\n"
    assert (tmp_path / "script.cmd").read_bytes() == b"echo hello\r\n"


def test_write_preserves_existing_crlf_line_endings(tmp_path):
    target = tmp_path / "windows.txt"
    target.write_text("alpha\r\nbeta\r\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("windows.txt"))
    payload = decode(runtime.write("windows.txt", "one\ntwo\n"))

    assert payload["ok"] is True
    assert payload["metadata"]["line_endings"] == "CRLF"
    assert target.read_bytes() == b"one\r\ntwo\r\n"


def test_write_does_not_double_translate_existing_crlf_bytes(tmp_path):
    target = tmp_path / "windows.txt"
    target.write_bytes(b"alpha\r\nbeta\r\n")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    decode(runtime.read_file("windows.txt"))
    payload = decode(runtime.write("windows.txt", "one\ntwo\n"))

    assert payload["ok"] is True
    assert target.read_bytes() == b"one\r\ntwo\r\n"
    assert b"\r\r\n" not in target.read_bytes()


def test_write_preserves_existing_utf16le_encoding(tmp_path):
    target = tmp_path / "utf16.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-16")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    read_payload = decode(runtime.read_file("utf16.txt"))
    payload = decode(runtime.write("utf16.txt", "one\ntwo\n"))

    assert read_payload["metadata"]["encoding"] == "utf16le"
    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf16le"
    assert target.read_bytes().startswith(b"\xff\xfe")
    assert target.read_text(encoding="utf-16") == "one\ntwo\n"


def test_write_preserves_existing_utf8_sig_encoding(tmp_path):
    target = tmp_path / "utf8_sig.py"
    target.write_bytes("城市=北京\n".encode("utf-8-sig"))
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    decode(runtime.read_file("utf8_sig.py"))
    payload = decode(runtime.write("utf8_sig.py", "城市=上海\n"))

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf8-sig"
    assert target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert target.read_bytes().decode("utf-8-sig") == "城市=上海\n"


def test_write_file_preserves_existing_windows_encodings(tmp_path):
    utf16 = tmp_path / "utf16.txt"
    utf16.write_text("alpha\nbeta\n", encoding="utf-16")
    utf8_sig = tmp_path / "utf8_sig.py"
    utf8_sig.write_bytes("城市=北京\n".encode("utf-8-sig"))
    gb18030 = tmp_path / "gb18030.txt"
    gb18030.write_bytes("城市=北京\n".encode("gb18030"))
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    utf16_read = decode(runtime.read_file("utf16.txt"))
    utf16_payload = decode(
        runtime.write_file(
            "utf16.txt",
            "one\ntwo\n",
            overwrite=True,
            snapshot_id=utf16_read["metadata"]["snapshot_id"],
        )
    )
    utf8_sig_read = decode(runtime.read_file("utf8_sig.py"))
    utf8_sig_payload = decode(
        runtime.write_file(
            "utf8_sig.py",
            "城市=上海\n",
            overwrite=True,
            expected_hash=utf8_sig_read["metadata"]["content_hash"],
        )
    )
    gb18030_read = decode(runtime.read_file("gb18030.txt"))
    gb18030_payload = decode(
        runtime.write_file(
            "gb18030.txt",
            "城市=上海\n",
            overwrite=True,
            snapshot_id=gb18030_read["metadata"]["snapshot_id"],
        )
    )

    assert utf16_payload["ok"] is True
    assert utf16_payload["metadata"]["encoding"] == "utf16le"
    assert utf16.read_bytes().startswith(b"\xff\xfe")
    assert utf16.read_text(encoding="utf-16") == "one\ntwo\n"
    assert utf8_sig_payload["ok"] is True
    assert utf8_sig_payload["metadata"]["encoding"] == "utf8-sig"
    assert utf8_sig.read_bytes().startswith(b"\xef\xbb\xbf")
    assert utf8_sig.read_bytes().decode("utf-8-sig") == "城市=上海\n"
    assert gb18030_payload["ok"] is True
    assert gb18030_payload["metadata"]["encoding"] == "gb18030"
    assert gb18030.read_bytes().decode("gb18030") == "城市=上海\n"


def test_read_decodes_gbk_compatible_text(tmp_path):
    target = tmp_path / "gbk.txt"
    target.write_bytes("城市=北京\n".encode("gb18030"))
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("gbk.txt"))

    assert payload["ok"] is True
    assert "1: 城市=北京" in payload["output"]
    assert payload["metadata"]["encoding"] == "gb18030"


def test_read_keeps_valid_utf8_classified_as_utf8(tmp_path):
    target = tmp_path / "utf8.txt"
    target.write_text("城市=北京\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read_file("utf8.txt"))

    assert payload["ok"] is True
    assert "1: 城市=北京" in payload["output"]
    assert payload["metadata"]["encoding"] == "utf8"


def test_windows_new_non_ascii_text_file_stays_plain_utf8(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    payload = decode(runtime.write_file("notes.py", "# 中文注释\nprint('ok')\n"))
    target = tmp_path / "notes.py"

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf8"
    assert not target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert target.read_bytes().decode("utf-8") == "# 中文注释\nprint('ok')\n"


def test_windows_new_non_ascii_python_file_is_utf8_parser_safe(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    payload = decode(runtime.write_file("script.py", "# 中文注释\nprint('ok')\n"))
    target = tmp_path / "script.py"
    source = target.read_text(encoding="utf-8")

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf8"
    assert not source.startswith("\ufeff")
    ast.parse(source)


def test_windows_new_ascii_text_file_stays_plain_utf8(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    payload = decode(runtime.write_file("notes.py", "# comment\nprint('ok')\n"))
    target = tmp_path / "notes.py"

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf8"
    assert not target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert target.read_bytes() == b"# comment\nprint('ok')\n"


def test_posix_new_non_ascii_text_file_stays_plain_utf8(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="darwin")

    payload = decode(runtime.write_file("notes.py", "# 中文注释\nprint('ok')\n"))
    target = tmp_path / "notes.py"

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf8"
    assert not target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert target.read_bytes().decode("utf-8") == "# 中文注释\nprint('ok')\n"


def test_write_repairs_json_object_content_for_json_files(tmp_path):
    target = tmp_path / "package.json"
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.write("package.json", {"name": "demo", "private": True}))

    assert payload["ok"] is True
    assert payload["metadata"]["input_repaired"] is True
    assert payload["metadata"]["repair_kind"] == "json-stringify-content"
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "name": "demo",
        "private": True,
    }
    assert target.read_text(encoding="utf-8").startswith('{\n  "name": "demo"')


def test_write_rejects_non_string_content_for_non_json_files(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.write("notes.txt", {"text": "demo"}))

    assert payload["ok"] is False
    assert payload["error"] == "content must be a string."


def test_write_file_after_out_of_band_delete_preserves_stale_protection(tmp_path):
    target = tmp_path / "notes.py"
    target.write_text("print('old')\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    decode(runtime.read_file("notes.py"))
    target.unlink()
    payload = decode(runtime.write_file("notes.py", "print('new')\n"))

    assert payload["ok"] is False
    assert payload["error"] == "File changed since it was read: it no longer exists."
    assert payload["metadata"]["recovery_kind"] == "stale_deleted_file"
    assert (
        "do not recreate Unicode files through shell here-strings"
        in payload["metadata"]["recovery"]
    )


def test_edit_preserves_existing_crlf_line_endings(tmp_path):
    target = tmp_path / "windows.txt"
    target.write_text("alpha\r\nbeta\r\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("windows.txt"))
    payload = decode(runtime.edit("windows.txt", "beta", "gamma"))

    assert payload["ok"] is True
    assert payload["metadata"]["line_endings"] == "CRLF"
    assert target.read_bytes() == b"alpha\r\ngamma\r\n"


def test_edit_matches_crlf_file_with_lf_old_string(tmp_path):
    target = tmp_path / "unicode_demo.py"
    target.write_bytes(
        "def demo():\r\n    title = '中文和Unicode字符演示程序'\r\n    return title\r\n".encode(
            "utf-8"
        )
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("unicode_demo.py"))
    payload = decode(
        runtime.edit_text(
            "unicode_demo.py",
            "def demo():\n    title = '中文和Unicode字符演示程序'",
            "def demo():\n    title = 'Unicode Character Demo Program'",
        )
    )

    assert payload["ok"] is True
    assert payload["metadata"]["matched_via"] == "line_endings"
    assert payload["metadata"]["line_endings"] == "CRLF"
    assert target.read_bytes() == (
        b"def demo():\r\n    title = 'Unicode Character Demo Program'\r\n    return title\r\n"
    )


def test_edit_preserves_existing_utf16le_encoding(tmp_path):
    target = tmp_path / "utf16.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-16")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("utf16.txt"))
    payload = decode(runtime.edit("utf16.txt", "beta", "gamma"))

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf16le"
    assert target.read_bytes().startswith(b"\xff\xfe")
    assert target.read_text(encoding="utf-16") == "alpha\ngamma\n"


def test_edit_preserves_existing_gbk_compatible_encoding(tmp_path):
    target = tmp_path / "gbk.txt"
    target.write_bytes("城市=北京\n".encode("gb18030"))
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("gbk.txt"))
    payload = decode(runtime.edit_text("gbk.txt", "北京", "上海"))

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "gb18030"
    assert target.read_bytes().decode("gb18030") == "城市=上海\n"


def test_edit_matches_gbk_compatible_crlf_file_with_lf_old_string(tmp_path):
    target = tmp_path / "gbk_crlf.txt"
    target.write_bytes("标题=中文\r\n城市=北京\r\n".encode("gb18030"))
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("gbk_crlf.txt"))
    payload = decode(
        runtime.edit_text(
            "gbk_crlf.txt",
            "标题=中文\n城市=北京",
            "Title=Chinese\nCity=Beijing",
        )
    )

    assert payload["ok"] is True
    assert payload["metadata"]["matched_via"] == "line_endings"
    assert payload["metadata"]["encoding"] == "gb18030"
    assert payload["metadata"]["line_endings"] == "CRLF"
    assert target.read_bytes().decode("gb18030") == "Title=Chinese\r\nCity=Beijing\r\n"


def test_apply_patch_preserves_existing_encoding_and_crlf_line_endings(tmp_path):
    target = tmp_path / "gb18030_crlf.txt"
    target.write_bytes("标题=中文\r\n城市=北京\r\n".encode("gb18030"))
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    payload = decode(
        runtime.apply_patch(
            [
                {
                    "type": "replace_block",
                    "file_path": "gb18030_crlf.txt",
                    "old_text": "城市=北京\n",
                    "new_text": "城市=上海\n",
                    "expected_occurrences": 1,
                }
            ]
        )
    )

    assert payload["ok"] is True
    assert target.read_bytes().decode("gb18030") == "标题=中文\r\n城市=上海\r\n"
    assert not target.read_bytes().startswith(b"\xef\xbb\xbf")


def test_edit_matches_crlf_file_with_lf_old_string_in_snippet_scope(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_bytes(b"alpha\r\ntarget = 1\r\nomega\r\nbeta\r\ntarget = 1\r\ndone\r\n")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    read_payload = decode(runtime.read_file("sample.txt", start_line=4, limit=2))
    snippet_id = read_payload["metadata"]["snippet"]["id"]
    payload = decode(
        runtime.edit_text(
            None,
            "beta\ntarget = 1",
            "beta\ntarget = 2",
            snippet_id=snippet_id,
        )
    )

    assert payload["ok"] is True
    assert payload["metadata"]["matched_via"] == "line_endings"
    assert payload["metadata"]["read_scope_type"] == "snippet"
    assert target.read_bytes() == b"alpha\r\ntarget = 1\r\nomega\r\nbeta\r\ntarget = 2\r\ndone\r\n"


def test_edit_line_ending_tolerant_absent_text_still_reports_closest_match(tmp_path):
    target = tmp_path / "near.txt"
    target.write_bytes(b"alpha\r\nbeta = 1\r\ngamma\r\n")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read_file("near.txt"))
    payload = decode(runtime.edit_text("near.txt", "bet = 1\nextra", "beta = 2\nextra"))

    assert payload["ok"] is False
    assert payload["error"] == "old_string not found in file."
    assert "closest_match" in payload["metadata"]
    assert payload["metadata"]["closest_match"]["strategy"] == "fuzzy_window"


def test_shell_runs_in_session_cwd_and_tracks_simple_cd(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    subdir = tmp_path / "sub"
    subdir.mkdir()
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.shell("cd sub"))

    assert payload["ok"] is True
    assert runtime.cwd == subdir


def test_shell_tool_returns_shell_result_name(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.shell("printf ok"))

    assert payload["ok"] is True
    assert payload["name"] == "shell"
    assert payload["output"] == "ok"


def test_shell_tracks_cwd_after_compound_cd_command(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    subdir = tmp_path / "sub"
    subdir.mkdir()
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.shell("cd sub && pwd"))

    assert payload["ok"] is True
    assert payload["metadata"]["cwd"] == str(subdir)
    assert payload["output"].strip() == str(subdir)
    assert runtime.cwd == subdir


def test_shell_tracks_cwd_even_when_command_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    subdir = tmp_path / "sub"
    subdir.mkdir()
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.shell("cd sub && false"))

    assert payload["ok"] is False
    assert payload["metadata"]["exitCode"] == 1
    assert payload["metadata"]["cwd"] == str(subdir)
    assert runtime.cwd == subdir


def test_shell_uses_shell_compatibility_wrapper(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.shell("printf hidden >nul"))

    assert payload["ok"] is True
    assert payload["output"] == ""
    assert payload["metadata"]["shellPath"]
    assert payload["metadata"]["shellKind"]
    assert payload["metadata"]["commandDialect"]
    assert payload["metadata"]["pathStyle"]
    assert payload["metadata"]["osFamily"]
    assert not (tmp_path / "nul").exists()


def test_build_shell_command_uses_powershell_wrapper_for_powershell():
    invocation = _build_shell_command(
        "Set-Location child",
        "__MARK__",
        shell_path=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        env={"PSModulePath": r"C:\Users\foo\Documents\PowerShell\Modules"},
        platform_name="win32",
        os_name="nt",
    )

    script = invocation.args[-1]
    assert invocation.runtime_environment.shell_kind == "powershell"
    assert invocation.runtime_environment.command_dialect == "powershell"
    assert invocation.runtime_environment.path_style == "windows"
    assert invocation.args[:4] == ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command"]
    assert "Get-Location" in script
    assert "$global:LASTEXITCODE" in script
    assert "$OutputEncoding = [System.Text.UTF8Encoding]::new($false)" in script
    assert "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)" in script
    assert "__MARK__CWD=$__deepy_cwd" in script
    assert "/c/" not in script
    assert invocation.env is not None
    assert invocation.env["PYTHONUTF8"] == "1"
    assert invocation.env["PYTHONIOENCODING"] == "utf-8"


def test_build_shell_command_preserves_explicit_python_encoding_env_for_windows():
    invocation = _build_shell_command(
        "python script.py",
        "__MARK__",
        shell_path=r"C:\Program Files\PowerShell\7\pwsh.exe",
        env={
            "PSModulePath": r"C:\Users\foo\Documents\PowerShell\Modules",
            "PYTHONUTF8": "0",
            "PYTHONIOENCODING": "gbk",
        },
        platform_name="win32",
        os_name="nt",
    )

    assert invocation.env is not None
    assert invocation.env["PYTHONUTF8"] == "0"
    assert invocation.env["PYTHONIOENCODING"] == "gbk"


def test_build_shell_command_does_not_apply_windows_encoding_setup_to_posix():
    invocation = _build_shell_command(
        "printf ok",
        "__MARK__",
        shell_path="/bin/bash",
        env={},
        platform_name="linux",
        os_name="posix",
    )

    script = invocation.args[-1]
    assert invocation.runtime_environment.command_dialect == "posix"
    assert "OutputEncoding" not in script
    assert invocation.env == {}
    assert "PYTHONUTF8" not in invocation.env
    assert "PYTHONIOENCODING" not in invocation.env


def test_build_shell_command_supports_cmd_detection():
    invocation = _build_shell_command(
        "cd child",
        "__MARK__",
        shell_path=r"C:\Windows\System32\cmd.exe",
        env={},
        platform_name="win32",
        os_name="nt",
    )

    assert invocation.runtime_environment.shell_kind == "cmd"
    assert invocation.runtime_environment.command_dialect == "cmd"
    assert invocation.runtime_environment.path_style == "windows"
    assert invocation.args[:3] == ["/d", "/s", "/c"]
    assert "__MARK__CWD=%CD%" in invocation.args[-1]


def test_extract_shell_sentinel_parses_cwd_and_exit_code(tmp_path):
    marker = "__MARK__"
    stdout = f"visible\n\n{marker}CWD={tmp_path}\n{marker}EXIT=7\n"

    visible, cwd, exit_code = _extract_bash_sentinel(stdout, marker)

    assert visible == "visible\n"
    assert cwd == tmp_path.resolve()
    assert exit_code == 7


def test_shell_decodes_utf16le_output_before_extracting_sentinel(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.shell(write_encoded_stdout_command("WSL 状态: 正常\n", "utf-16le")))

    assert payload["ok"] is True
    assert payload["output"] == "WSL 状态: 正常\n"
    assert payload["metadata"]["cwd"] == str(tmp_path)
    assert payload["metadata"]["exitCode"] == 0
    assert payload["metadata"]["stdoutEncoding"] == "utf-16le"


def test_shell_decodes_gbk_compatible_output(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.shell(write_encoded_stdout_command("状态: 正常\n", "gb18030")))

    assert payload["ok"] is True
    assert payload["output"] == "状态: 正常\n"
    assert payload["metadata"]["stdoutEncoding"] == "gb18030"


def test_shell_keeps_utf8_output_decoding(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.shell(write_encoded_stdout_command("状态: 正常\n", "utf-8")))

    assert payload["ok"] is True
    assert payload["output"] == "状态: 正常\n"
    assert payload["metadata"]["stdoutEncoding"] == "utf-8"


def test_shell_truncates_large_output(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.shell(repeat_x_command(31_000)))

    assert payload["ok"] is True
    assert len(payload["output"]) > MAX_BASH_OUTPUT_CHARS
    assert len(payload["output"]) < 31_000
    assert payload["output"].endswith("... [truncated 1000 chars]")
    assert payload["metadata"]["outputTruncated"] is True


def test_shell_caps_captured_output_before_formatting(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    monkeypatch.setattr("deepy.tools.builtin.MAX_BASH_CAPTURE_CHARS", 10)
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.shell(repeat_x_command(25)))

    assert payload["ok"] is True
    assert payload["output"] == "x" * 10
    assert payload["metadata"]["captureTruncated"] is True
    assert payload["metadata"]["outputTruncated"] is False


def test_shell_timeout_tracks_and_clears_process(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.shell("sleep 1", timeout_ms=20))

    assert payload["ok"] is False
    assert "timed out" in payload["error"]
    assert payload["metadata"]["interrupted"] is True
    assert payload["metadata"]["processId"]
    assert runtime.running_processes == {}


def test_shell_interrupt_terminates_running_process(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), should_interrupt=lambda: True)

    started = time.monotonic()
    payload = decode(runtime.shell("sleep 5", timeout_ms=10_000))
    elapsed = time.monotonic() - started

    assert payload["ok"] is False
    assert payload["error"] == "Command interrupted by user."
    assert payload["metadata"]["interrupted"] is True
    assert runtime.running_processes == {}
    assert elapsed < 1


def test_shell_background_launch_returns_task_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.shell(
            f"{shlex.quote(sys.executable)} -c \"import time; print('ready', flush=True); time.sleep(.2)\"",
            run_in_background=True,
        )
    )

    assert payload["ok"] is True
    assert payload["name"] == "shell"
    assert payload["metadata"]["kind"] == "background_task_launch"
    assert payload["metadata"]["runInBackground"] is True
    assert payload["metadata"]["taskId"].startswith("bg-")
    assert "Started background task" in payload["output"]
    output = decode(runtime.task_output(payload["metadata"]["taskId"], block=True, timeout=1))
    assert output["ok"] is True
    assert "ready" in output["output"]


def test_task_list_output_and_stop_background_task(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    launched = decode(
        runtime.shell(
            f"{shlex.quote(sys.executable)} -c \"import time; print('tick', flush=True); time.sleep(5)\"",
            run_in_background=True,
        )
    )
    task_id = launched["metadata"]["taskId"]

    tasks = decode(runtime.task_list(active_only=True))
    assert tasks["ok"] is True
    assert tasks["metadata"]["kind"] == "background_task_list"
    assert tasks["metadata"]["tasks"][0]["id"] == task_id
    assert tasks["metadata"]["tasks"][0]["status"] == "running"

    output = decode(runtime.task_output(task_id))
    assert output["ok"] is True
    assert output["metadata"]["kind"] == "background_task_output"
    assert output["metadata"]["taskId"] == task_id

    stopped = decode(runtime.task_stop(task_id))
    assert stopped["ok"] is True
    assert stopped["metadata"]["kind"] == "background_task_stop"
    runtime.background_tasks.stop_all(force_after_grace=True)


def test_task_output_block_waits_for_output_not_completion(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    launched = decode(
        runtime.shell(
            f"{shlex.quote(sys.executable)} -c \"import time; print('started', flush=True); time.sleep(5)\"",
            run_in_background=True,
        )
    )
    task_id = launched["metadata"]["taskId"]
    started = time.monotonic()

    output = decode(runtime.task_output(task_id, block=True, timeout=5))
    elapsed = time.monotonic() - started
    runtime.background_tasks.stop_all(force_after_grace=True)

    assert output["ok"] is True
    assert "started" in output["output"]
    assert output["metadata"]["task"]["status"] == "running"
    assert elapsed < 1


def test_task_output_and_stop_report_unknown_task_id(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    output = decode(runtime.task_output("bg-missing"))
    stopped = decode(runtime.task_stop("bg-missing"))

    assert output["ok"] is False
    assert output["metadata"]["error_code"] == "background_task_not_found"
    assert stopped["ok"] is False
    assert stopped["metadata"]["error_code"] == "background_task_not_found"


def test_shell_background_launch_limit_and_failure_are_structured(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    def reject_start(**_kwargs):
        raise BackgroundTaskLimitError("Background task limit reached (1 running).")

    monkeypatch.setattr(runtime.background_tasks, "start", reject_start)
    limited = decode(runtime.shell("sleep 5", run_in_background=True))

    assert limited["ok"] is False
    assert limited["metadata"]["error_code"] == "background_task_limit"

    def fail_start(**_kwargs):
        raise OSError("launch failed")

    monkeypatch.setattr(runtime.background_tasks, "start", fail_start)
    failed = decode(runtime.shell("sleep 5", run_in_background=True))

    assert failed["ok"] is False
    assert failed["metadata"]["error_code"] == "background_task_launch_failed"


def test_shell_function_tool_accepts_background_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/sh")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    shell_tool = next(tool for tool in build_function_tools(runtime) if tool.name == "shell")

    payload = decode(
        asyncio.run(
            shell_tool.on_invoke_tool(
                None,
                json.dumps({"command": "sleep .2", "run_in_background": True}),
            )
        )
    )

    assert payload["ok"] is True
    assert payload["metadata"]["kind"] == "background_task_launch"
    runtime.background_tasks.stop_all(force_after_grace=True)


def test_ask_user_question_sets_wait_flag(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(
        runtime.ask_user_question(
            [
                {
                    "question": "continue?",
                    "options": [
                        {"label": "Yes", "description": "Proceed."},
                        {"label": "No"},
                    ],
                }
            ]
        )
    )

    assert payload["ok"] is True
    assert payload["name"] == "AskUserQuestion"
    assert payload["awaitUserResponse"] is True
    assert payload["metadata"] == {
        "kind": "ask_user_question",
        "questions": [
            {
                "question": "continue?",
                "options": [
                    {"label": "Yes", "description": "Proceed."},
                    {"label": "No"},
                ],
            }
        ],
    }
    assert "Waiting for user input." in payload["output"]


def test_ask_user_question_rejects_invalid_questions(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.ask_user_question([]))

    assert payload["ok"] is False
    assert payload["error"] == '"questions" must be a non-empty array.'


def test_load_skill_returns_skill_body_and_root(tmp_path):
    skill_dir = tmp_path / ".agents" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\nUse demo.",
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.load_skill("demo"))

    assert payload["ok"] is True
    assert "Use demo." in payload["output"]
    assert payload["metadata"]["root"] == str(skill_dir)


def test_search_literal_content_default(tmp_path):
    tmp_path.joinpath("src").mkdir()
    tmp_path.joinpath("src", "app.py").write_text(
        "class ToolRuntime:\n    pass\n",
        encoding="utf-8",
    )
    tmp_path.joinpath("README.md").write_text("No match here\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.search("ToolRuntime", path=".", glob="src/*.py"))

    assert payload["ok"] is True
    assert payload["name"] == "Search"
    assert payload["output"] == "src/app.py:1:class ToolRuntime:"
    assert payload["metadata"]["engine"] == "python"
    assert payload["metadata"]["mode"] == "literal"
    assert payload["metadata"]["outputMode"] == "content"
    assert payload["metadata"]["matchedFileCount"] == 1
    assert payload["metadata"]["totalMatches"] == 1
    assert payload["metadata"]["truncated"] is False


def test_search_literal_mode_does_not_treat_query_as_regex(tmp_path):
    tmp_path.joinpath("data.txt").write_text(
        "abcXdef\nabc.def\n",
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.search("abc.def"))

    assert payload["ok"] is True
    assert payload["output"] == "data.txt:2:abc.def"
    assert payload["metadata"]["totalMatches"] == 1


def test_search_regex_mode_and_invalid_regex(tmp_path):
    tmp_path.joinpath("data.txt").write_text("alpha1\nalpha2\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    regex_payload = decode(runtime.search(r"alpha\d", mode="regex"))
    invalid_payload = decode(runtime.search("[", mode="regex"))

    assert regex_payload["ok"] is True
    assert "data.txt:1:alpha1" in regex_payload["output"]
    assert "data.txt:2:alpha2" in regex_payload["output"]
    assert regex_payload["metadata"]["totalMatches"] == 2
    assert invalid_payload["ok"] is False
    assert invalid_payload["metadata"]["error_code"] == "invalid_regex"
    assert "Invalid regex pattern" in invalid_payload["error"]


def test_search_regex_timeout_returns_structured_error(tmp_path, monkeypatch):
    tmp_path.joinpath("data.txt").write_text("needle\n", encoding="utf-8")

    def timeout_count_in_line(_self, _line):
        return 0, True

    monkeypatch.setattr(search_module._Matcher, "count_in_line", timeout_count_in_line)
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.search("needle", mode="regex"))

    assert payload["ok"] is False
    assert payload["metadata"]["timedOut"] is True
    assert payload["metadata"]["error_code"] == "regex_timeout"


def test_search_output_modes_and_pagination(tmp_path):
    tmp_path.joinpath("a.txt").write_text("needle\n", encoding="utf-8")
    tmp_path.joinpath("b.txt").write_text("needle\nneedle\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    files_page = decode(runtime.search("needle", output_mode="files", limit=1))
    counts = decode(runtime.search("needle", output_mode="count"))

    assert files_page["ok"] is True
    assert files_page["output"].startswith("a.txt")
    assert files_page["metadata"]["resultCount"] == 1
    assert files_page["metadata"]["totalResults"] == 2
    assert files_page["metadata"]["nextOffset"] == 1
    assert files_page["metadata"]["truncated"] is True
    assert counts["ok"] is True
    assert counts["output"].splitlines() == ["a.txt:1", "b.txt:2"]


def test_search_respects_gitignore_and_include_ignored(tmp_path):
    tmp_path.joinpath(".gitignore").write_text("ignored/\n", encoding="utf-8")
    tmp_path.joinpath("src").mkdir()
    tmp_path.joinpath("ignored").mkdir()
    tmp_path.joinpath("src", "hit.txt").write_text("needle\n", encoding="utf-8")
    tmp_path.joinpath("ignored", "hit.txt").write_text("needle\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    default_payload = decode(runtime.search("needle", output_mode="files"))
    included_payload = decode(runtime.search("needle", output_mode="files", include_ignored=True))

    assert default_payload["ok"] is True
    assert default_payload["output"].splitlines() == ["src/hit.txt"]
    assert included_payload["ok"] is True
    assert included_payload["output"].splitlines() == ["ignored/hit.txt", "src/hit.txt"]


def test_search_skips_binary_oversized_sensitive_and_unsupported_files(tmp_path):
    tmp_path.joinpath("visible.txt").write_text("needle\n", encoding="utf-8")
    tmp_path.joinpath(".env").write_text("needle=secret\n", encoding="utf-8")
    tmp_path.joinpath("binary.bin").write_bytes(b"needle\x00hidden")
    tmp_path.joinpath("notebook.ipynb").write_text("needle\n", encoding="utf-8")
    tmp_path.joinpath("large.txt").write_bytes(b"needle" + b"x" * search_module.MAX_SEARCH_FILE_BYTES)
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.search("needle", output_mode="files"))
    skipped = {item["path"]: item["reason"] for item in payload["metadata"]["skipped"]}

    assert payload["ok"] is True
    assert payload["output"] == "visible.txt"
    assert skipped[".env"] == "sensitive"
    assert skipped["binary.bin"] == "binary"
    assert skipped["large.txt"] == "too_large"
    assert skipped["notebook.ipynb"] == "unsupported"
    assert payload["metadata"]["sensitiveFiltered"] == 1


def test_search_decodes_windows_text_encodings_and_crlf(tmp_path):
    tmp_path.joinpath("utf16.txt").write_text("needle\r\nnext\r\n", encoding="utf-16")
    tmp_path.joinpath("utf8sig.txt").write_text("needle\n", encoding="utf-8-sig")
    tmp_path.joinpath("gb18030.txt").write_bytes("中文 needle\n".encode("gb18030"))
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    payload = decode(runtime.search("needle", output_mode="content"))

    assert payload["ok"] is True
    assert "utf16.txt:1:needle" in payload["output"]
    assert "utf8sig.txt:1:needle" in payload["output"]
    assert "gb18030.txt:1:中文 needle" in payload["output"]
    assert payload["metadata"]["totalMatches"] == 3


def test_search_rejects_paths_outside_project(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("needle\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.search("needle", path=str(outside)))

    assert payload["ok"] is False
    assert payload["metadata"]["error_code"] == "path_policy"
    assert payload["metadata"]["policyDecision"] == "deny"


def test_function_tools_have_stable_names_and_descriptions(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    tools = build_function_tools(runtime)

    assert [tool.name for tool in tools] == [
        "shell",
        "task_list",
        "task_output",
        "task_stop",
        "AskUserQuestion",
        "Search",
        "read_file",
        "edit_text",
        "write_file",
        "apply_patch",
        "WebSearch",
        "WebFetch",
        "load_skill",
        "todo_write",
    ]
    assert all(tool.description for tool in tools)
    shell_tool = tools[0]
    assert shell_tool.name == "shell"
    assert "current runtime shell" in shell_tool.description
    assert "command dialect" in shell_tool.description
    assert "run_in_background" in shell_tool.description
    assert "persistent bash session" not in shell_tool.description
    task_list_tool = tools[1]
    assert task_list_tool.name == "task_list"
    assert "background shell tasks" in task_list_tool.description
    task_output_tool = tools[2]
    assert task_output_tool.name == "task_output"
    assert "captured output" in task_output_tool.description
    task_stop_tool = tools[3]
    assert task_stop_tool.name == "task_stop"
    assert "termination" in task_stop_tool.description
    ask_tool = tools[4]
    assert ask_tool.name == "AskUserQuestion"
    assert "偏好" in ask_tool.description
    assert "for Chinese requests, ask in Chinese" in ask_tool.description
    assert "low-impact details" in ask_tool.description
    search_tool = tools[5]
    assert search_tool.name == "Search"
    assert "without shell grep or rg" in search_tool.description
    assert "Defaults to literal content search" in search_tool.description
    read_tool = tools[6]
    assert read_tool.name == "read_file"
    assert "managed text snapshots" in read_tool.description
    edit_tool = tools[7]
    assert edit_tool.name == "edit_text"
    assert "Preferred tool for small single-file exact/string edits" in edit_tool.description
    write_tool = tools[8]
    assert write_tool.name == "write_file"
    assert "snapshot_id, snapshot_token, or expected_hash" in write_tool.description
    patch_tool = tools[9]
    assert patch_tool.name == "apply_patch"
    assert "multiple edits in one file" in patch_tool.description
    assert "operations array" in patch_tool.description
    skill_tool = tools[-2]
    assert skill_tool.name == "load_skill"
    todo_tool = tools[-1]
    assert todo_tool.name == "todo_write"
    assert "complex multi-step work" in todo_tool.description
    assert "available Agent Skill" in skill_tool.description


def test_function_tool_schemas_match_shell_tool(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    tools = {tool.name: tool for tool in build_function_tools(runtime)}

    assert tools["shell"].params_json_schema["required"] == ["command"]
    assert list(tools["shell"].params_json_schema["properties"]) == [
        "command",
        "description",
        "run_in_background",
    ]
    assert tools["task_list"].params_json_schema["required"] == []
    assert list(tools["task_list"].params_json_schema["properties"]) == ["active_only", "limit"]
    assert tools["task_output"].params_json_schema["required"] == ["task_id"]
    assert list(tools["task_output"].params_json_schema["properties"]) == [
        "task_id",
        "block",
        "timeout",
    ]
    assert tools["task_stop"].params_json_schema["required"] == ["task_id"]
    assert list(tools["task_stop"].params_json_schema["properties"]) == ["task_id"]
    assert tools["AskUserQuestion"].params_json_schema["required"] == ["questions"]
    assert list(tools["AskUserQuestion"].params_json_schema["properties"]) == ["questions"]
    assert tools["Search"].params_json_schema["required"] == [
        "query",
        "path",
        "glob",
        "mode",
        "output_mode",
        "case_sensitive",
        "context",
        "limit",
        "offset",
        "include_ignored",
    ]
    assert list(tools["Search"].params_json_schema["properties"]) == [
        "query",
        "path",
        "glob",
        "mode",
        "output_mode",
        "case_sensitive",
        "context",
        "limit",
        "offset",
        "include_ignored",
    ]
    assert tools["read_file"].params_json_schema["required"] == [
        "file_path",
        "offset",
        "limit",
        "pages",
    ]
    assert tools["edit_text"].params_json_schema["required"] == [
        "file_path",
        "snippet_id",
        "old_string",
        "new_string",
        "replace_all",
        "expected_occurrences",
    ]
    assert tools["write_file"].params_json_schema["required"] == [
        "file_path",
        "content",
        "overwrite",
        "snapshot_id",
        "snapshot_token",
        "expected_hash",
    ]
    assert tools["apply_patch"].params_json_schema["required"] == ["operations"]
    operation_schema = tools["apply_patch"].params_json_schema["properties"]["operations"]["items"]
    assert "patch" not in tools["apply_patch"].params_json_schema["properties"]
    assert operation_schema["required"] == [
        "type",
        "file_path",
        "destination_path",
        "content",
        "old_text",
        "new_text",
        "anchor",
        "expected_occurrences",
        "replace_all",
        "overwrite",
        "snapshot_id",
        "snapshot_token",
        "expected_hash",
    ]
    assert tools["WebSearch"].params_json_schema["required"] == ["query"]
    assert list(tools["WebSearch"].params_json_schema["properties"]) == ["query"]
    assert tools["WebFetch"].params_json_schema["required"] == ["url"]
    assert list(tools["WebFetch"].params_json_schema["properties"]) == ["url"]


def test_mimo_compatible_schema_removes_nullable_required_fields_recursively():
    schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "offset": {"type": ["number", "null"]},
            "nested": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "expected": {"type": ["integer", "null"]},
                },
                "required": ["name", "expected"],
                "additionalProperties": False,
            },
        },
        "required": ["file_path", "offset", "nested"],
        "additionalProperties": False,
    }

    compatible = make_mimo_compatible_tool_schema(schema)

    assert schema["required"] == ["file_path", "offset", "nested"]
    assert compatible["required"] == ["file_path", "nested"]
    assert compatible["properties"]["offset"]["type"] == "number"
    nested = compatible["properties"]["nested"]
    assert nested["required"] == ["name"]
    assert nested["properties"]["expected"]["type"] == "integer"
    assert nested["additionalProperties"] is False


def test_mimo_compatible_function_tools_keep_optional_nullable_defaults(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    tools = {
        tool.name: tool for tool in build_function_tools(runtime, mimo_schema_compatibility=True)
    }

    read_schema = tools["read_file"].params_json_schema
    assert read_schema["required"] == ["file_path"]
    assert read_schema["properties"]["offset"]["type"] == "number"

    payload = decode(
        asyncio.run(
            tools["read_file"].on_invoke_tool(
                None,
                '{"file_path":"a.txt"}',
            )
        )
    )

    assert payload["ok"] is True
    assert "1: one" in payload["output"]
    assert "2: two" in payload["output"]


def test_web_search_tool_description_mentions_mcp_fallback_when_preferred(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    tools = {
        tool.name: tool
        for tool in build_function_tools(
            runtime,
            preferred_mcp_web_search_tools=["mcp_tavily__tavily_search"],
        )
    }

    assert "Built-in fallback web search" in tools["WebSearch"].description
    assert "mcp_tavily__tavily_search" in tools["WebSearch"].description
    assert "Prefer those MCP tools first" in tools["WebSearch"].description


def test_web_fetch_requires_complete_http_url(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    missing_scheme = decode(runtime.web_fetch("www.example.com/page"))
    unsupported_scheme = decode(runtime.web_fetch("ftp://example.com/page"))

    assert missing_scheme["ok"] is False
    assert "complete http or https URL" in missing_scheme["error"]
    assert unsupported_scheme["ok"] is False
    assert "complete http or https URL" in unsupported_scheme["error"]


def test_web_fetch_extracts_readable_html_page(tmp_path, monkeypatch):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    requested: list[object] = []

    class FakeResponse:
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def geturl(self):
            return "https://example.com/final"

        def read(self, size=-1):
            assert size > 0
            return (
                b"<html><head><title>Demo Title</title>"
                b"<script>ignored()</script></head>"
                b"<body><h1>Heading</h1><p>First paragraph.</p>"
                b"<a href='/next'>Link text</a></body></html>"
            )

    def fake_urlopen(request, timeout):
        requested.append(request)
        assert timeout == 30
        assert request.get_method() == "GET"
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = decode(runtime.web_fetch("https://example.com/page"))

    assert payload["ok"] is True
    assert requested[0].full_url == "https://example.com/page"
    assert "URL: https://example.com/page" in payload["output"]
    assert "Final URL: https://example.com/final" in payload["output"]
    assert "Title: Demo Title" in payload["output"]
    assert "Heading" in payload["output"]
    assert "First paragraph." in payload["output"]
    assert "Link text" in payload["output"]
    assert "ignored()" not in payload["output"]
    assert payload["metadata"]["url"] == "https://example.com/page"
    assert payload["metadata"]["finalUrl"] == "https://example.com/final"
    assert payload["metadata"]["contentType"] == "text/html; charset=utf-8"
    assert payload["metadata"]["bodyTruncated"] is False


def test_web_fetch_uses_meta_description_when_body_text_is_empty(tmp_path, monkeypatch):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    class FakeResponse:
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def geturl(self):
            return "https://leetcode.cn/problems/two-sum/description/"

        def read(self, size=-1):
            assert size > 0
            return (
                b"<html><head><title>1. Two Sum</title>"
                b"<meta name='description' content='Given an integer array nums and a target, "
                b"return indices of the two numbers such that they add up to target.'>"
                b"</head><body><div id='__next'></div><script>ignored()</script></body></html>"
            )

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse())

    payload = decode(runtime.web_fetch("https://leetcode.cn/problems/two-sum/description/"))

    assert payload["ok"] is True
    assert "Title: 1. Two Sum" in payload["output"]
    assert "Given an integer array nums and a target" in payload["output"]
    assert "return indices of the two numbers" in payload["output"]
    assert "[No readable text extracted.]" not in payload["output"]
    assert "ignored()" not in payload["output"]


def test_web_fetch_uses_social_description_metadata_fallbacks(tmp_path, monkeypatch):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    class FakeResponse:
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def geturl(self):
            return "https://example.com/app"

        def read(self, size=-1):
            return (
                b"<html><head><title>App Page</title>"
                b"<meta name='twitter:description' content='Twitter description text.'>"
                b"<meta property='og:description' content='OpenGraph description text.'>"
                b"</head><body><div id='root'></div></body></html>"
            )

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse())

    payload = decode(runtime.web_fetch("https://example.com/app"))

    assert payload["ok"] is True
    assert "OpenGraph description text." in payload["output"]
    assert "Twitter description text." not in payload["output"]


def test_web_fetch_decodes_gzip_response(tmp_path, monkeypatch):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    requested: list[object] = []

    class FakeResponse:
        headers = {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Encoding": "gzip",
        }

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def geturl(self):
            return "https://example.com/compressed"

        def read(self, size=-1):
            return gzip.compress(
                b"<html><head><title>Compressed</title></head>"
                b"<body><p>Compressed readable content.</p></body></html>"
            )

    def fake_urlopen(request, timeout):
        requested.append(request)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = decode(runtime.web_fetch("https://example.com/compressed"))

    assert payload["ok"] is True
    assert requested[0].get_header("Accept-encoding") == "gzip, deflate"
    assert "Compressed readable content." in payload["output"]
    assert payload["metadata"]["byteCount"] > 0


def test_web_fetch_prefers_body_text_over_meta_description(tmp_path, monkeypatch):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    class FakeResponse:
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def geturl(self):
            return "https://example.com/article"

        def read(self, size=-1):
            return (
                b"<html><head><title>Article</title>"
                b"<meta name='description' content='SEO summary should not replace body.'>"
                b"</head><body><article><p>This is the article body text that should win.</p>"
                b"</article></body></html>"
            )

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse())

    payload = decode(runtime.web_fetch("https://example.com/article"))

    assert payload["ok"] is True
    assert "This is the article body text that should win." in payload["output"]
    assert "SEO summary should not replace body." not in payload["output"]


def test_web_fetch_unsupported_content_encoding_returns_structured_error(tmp_path, monkeypatch):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    class FakeResponse:
        headers = {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Encoding": "br",
        }

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def geturl(self):
            return "https://example.com/brotli"

        def read(self, size=-1):
            return b"not decoded here"

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse())

    payload = decode(runtime.web_fetch("https://example.com/brotli"))

    assert payload["ok"] is False
    assert "Unsupported content encoding: br" in payload["error"]
    assert payload["metadata"]["url"] == "https://example.com/brotli"


def test_web_fetch_returns_plain_text_response(tmp_path, monkeypatch):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    class FakeResponse:
        headers = {"Content-Type": "text/plain; charset=utf-8"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def geturl(self):
            return "https://example.com/robots.txt"

        def read(self, size=-1):
            return b"User-agent: *\nDisallow: /private\n"

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse())

    payload = decode(runtime.web_fetch("https://example.com/robots.txt"))

    assert payload["ok"] is True
    assert "User-agent: *" in payload["output"]
    assert "Disallow: /private" in payload["output"]
    assert payload["metadata"]["charset"] == "utf-8"


def test_web_search_uses_configured_searxng_url_first(tmp_path, monkeypatch):
    settings = Settings(
        model=ModelConfig(
            api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"
        ),
        tools=ToolsConfig(
            web_search=WebSearchToolConfig(
                searxng_url="https://search.example",
            )
        ),
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=settings)
    requested_urls: list[str] = []
    chat_prompts: list[str] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "results": [
                        {
                            "title": "DeepSeek Docs",
                            "url": "https://api-docs.deepseek.com",
                            "content": "DeepSeek API documentation.",
                        }
                    ]
                }
            ).encode()

    def fake_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        assert timeout == 30
        assert request.get_method() == "GET"
        assert request.full_url == "https://search.example/search?q=deep+seek&format=json"
        assert request.get_header("Accept-language") == "zh-CN,zh;q=0.9,en;q=0.8"
        assert request.get_header("Accept-encoding") == "gzip, deflate"
        assert request.get_header("Sec-fetch-site") == "none"
        return FakeResponse()

    def fake_chat(settings, prompt):
        chat_prompts.append(prompt)
        return '{"dominant_language":"en","reason":"English docs are richer."}'

    monkeypatch.setattr("deepy.tools.builtin._web_search_chat", fake_chat)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = decode(runtime.web_search("deep seek"))

    assert payload["ok"] is True
    assert "DeepSeek Docs" in payload["output"]
    assert requested_urls == ["https://search.example/search?q=deep+seek&format=json"]
    assert payload["metadata"]["dominantLanguage"] == "en"
    assert payload["metadata"]["languageReason"] == "English docs are richer."
    assert payload["metadata"]["backend"] == "searxng_json"
    assert len(chat_prompts) == 1


def test_web_search_falls_back_to_duckduckgo_when_searxng_fails(tmp_path, monkeypatch):
    settings = Settings(
        model=ModelConfig(
            api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"
        ),
        tools=ToolsConfig(web_search=WebSearchToolConfig(searxng_url="https://search.example")),
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=settings)
    requested_urls: list[str] = []

    class FakeDuckDuckGoResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return (
                b'<html><body><a class="result__a" href="https://example.com">'
                b"Example Result</a></body></html>"
            )

    def fake_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        if request.full_url.startswith("https://search.example/search?"):
            raise OSError("searxng offline")
        assert request.full_url.startswith("https://html.duckduckgo.com/html/?")
        return FakeDuckDuckGoResponse()

    monkeypatch.setattr(
        "deepy.tools.builtin._web_search_chat",
        lambda settings, prompt: (
            '{"dominant_language":"en","reason":"English results are richer."}'
        ),
    )
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = decode(runtime.web_search("deep seek"))

    assert payload["ok"] is True
    assert "Example Result" in payload["output"]
    assert payload["metadata"]["backend"] == "duckduckgo_html"
    assert [attempt["provider"] for attempt in payload["metadata"]["providerAttempts"]] == [
        "searxng_json",
        "duckduckgo_html",
    ]
    assert payload["metadata"]["providerAttempts"][0]["ok"] is False
    assert payload["metadata"]["providerAttempts"][1]["ok"] is True
    assert requested_urls[0] == "https://search.example/search?q=deep+seek&format=json"
    assert requested_urls[1].startswith("https://html.duckduckgo.com/html/?")


def test_web_search_reports_chinese_dominant_language(tmp_path, monkeypatch):
    settings = Settings(
        model=ModelConfig(
            api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"
        ),
        tools=ToolsConfig(web_search=WebSearchToolConfig(searxng_url="https://search.example")),
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=settings)
    requested_urls: list[str] = []
    chat_prompts: list[str] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "results": [
                        {
                            "title": "DeepSeek models",
                            "url": "https://api-docs.deepseek.com/news",
                            "content": "Latest DeepSeek model information.",
                        }
                    ]
                }
            ).encode()

    def fake_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        assert request.get_method() == "GET"
        assert request.full_url == (
            "https://search.example/search?q=latest+DeepSeek+model&format=json"
        )
        return FakeResponse()

    def fake_chat(settings, prompt):
        chat_prompts.append(prompt)
        if "Return strict JSON" in prompt:
            return '{"dominant_language":"en","reason":"English results are better."}'
        return "latest DeepSeek model"

    monkeypatch.setattr("deepy.tools.builtin._web_search_chat", fake_chat)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = decode(runtime.web_search("DeepSeek 最新模型"))

    assert payload["ok"] is True
    assert payload["metadata"]["dominantLanguage"] == "en"
    assert payload["metadata"]["translated"] is True
    assert payload["metadata"]["resolvedQuery"] == "latest DeepSeek model"
    assert requested_urls == ["https://search.example/search?q=latest+DeepSeek+model&format=json"]
    assert len(chat_prompts) == 2


def test_web_search_uses_default_searxng_backend(tmp_path, monkeypatch):
    settings = Settings(
        model=ModelConfig(
            api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"
        ),
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=settings)
    requested: list[object] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "results": [
                        {
                            "title": "Node.js Releases",
                            "url": "https://nodejs.org/en/about/previous-releases",
                            "content": "Previous and current Node.js releases.",
                        }
                    ]
                }
            ).encode()

    def fake_urlopen(request, timeout):
        requested.append(request)
        assert timeout == 30
        assert request.get_method() == "GET"
        return FakeResponse()

    monkeypatch.setattr(
        "deepy.tools.builtin._web_search_chat",
        lambda settings, prompt: (
            '{"dominant_language":"en","reason":"English results are richer."}'
        ),
    )
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = decode(runtime.web_search("latest node release"))

    assert payload["ok"] is True
    assert "Node.js Releases" in payload["output"]
    assert "https://nodejs.org/en/about/previous-releases" in payload["output"]
    assert "Previous and current Node.js releases." in payload["output"]
    assert requested[0].full_url.startswith(DEFAULT_WEB_SEARCH_SEARXNG_URL + "search?")
    assert "q=latest+node+release" in requested[0].full_url
    assert requested[0].get_header("Accept-language") == "zh-CN,zh;q=0.9,en;q=0.8"
    assert requested[0].get_header("Accept-encoding") == "gzip, deflate"
    assert payload["metadata"]["backend"] == "searxng_json"
    assert payload["metadata"]["providerAttempts"] == [{"provider": "searxng_json", "ok": True}]


def test_web_search_builtin_backend_works_without_llm_config(tmp_path, monkeypatch):
    runtime = ToolRuntime(
        cwd=tmp_path,
        settings=Settings(),
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"results":[{"title":"Example Result","url":"https://example.com"}]}'

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse())

    payload = decode(runtime.web_search("latest node release"))

    assert payload["ok"] is True
    assert "Example Result" in payload["output"]
    assert payload["metadata"]["backend"] == "searxng_json"
    assert "valid LLM configuration" in payload["metadata"]["queryPreparationWarning"]


def test_web_search_falls_back_to_duckduckgo_when_searxng_returns_empty(tmp_path, monkeypatch):
    settings = Settings(
        model=ModelConfig(
            api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"
        ),
        tools=ToolsConfig(web_search=WebSearchToolConfig(searxng_url="https://search.example")),
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=settings)
    requested_urls: list[str] = []

    class FakeResponse:
        def __init__(self, body: bytes):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self.body

    def fake_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        if request.full_url.startswith("https://search.example/search?"):
            return FakeResponse(b'{"results":[]}')
        assert request.full_url.startswith("https://html.duckduckgo.com/html/?")
        return FakeResponse(
            b'<html><body><a class="result__a" '
            b'href="/l/?uddg=https%3A%2F%2Fnodejs.org%2Fen%2Fabout%2Fprevious-releases">'
            b"Node.js Releases</a>"
            b'<div class="result__snippet">Previous and current Node.js releases.</div>'
            b"</body></html>"
        )

    monkeypatch.setattr(
        "deepy.tools.builtin._web_search_chat",
        lambda settings, prompt: (
            '{"dominant_language":"en","reason":"English results are richer."}'
        ),
    )
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = decode(runtime.web_search("latest node release"))

    assert payload["ok"] is True
    assert "Node.js Releases" in payload["output"]
    assert payload["metadata"]["backend"] == "duckduckgo_html"
    assert payload["metadata"]["provider"] == "duckduckgo_html"
    assert payload["metadata"]["providerAttempts"][0]["provider"] == "searxng_json"
    assert payload["metadata"]["providerAttempts"][0]["ok"] is False
    assert payload["metadata"]["providerAttempts"][1] == {
        "provider": "duckduckgo_html",
        "ok": True,
    }
    assert requested_urls[0] == "https://search.example/search?q=latest+node+release&format=json"
    assert requested_urls[1].startswith("https://html.duckduckgo.com/html/?")


def test_web_search_reports_all_provider_failures_with_masked_metadata(tmp_path, monkeypatch):
    settings = Settings(
        model=ModelConfig(
            api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"
        ),
        tools=ToolsConfig(
            web_search=WebSearchToolConfig(
                searxng_url="https://search.example/?token=secret-token-value"
            )
        ),
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=settings)

    def fake_urlopen(request, timeout):
        raise OSError("offline")

    monkeypatch.setattr(
        "deepy.tools.builtin._web_search_chat",
        lambda settings, prompt: (
            '{"dominant_language":"en","reason":"English results are richer."}'
        ),
    )
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = decode(runtime.web_search("latest node release"))

    assert payload["ok"] is False
    assert "duckduckgo_html" in payload["error"]
    assert "searxng_json" in payload["error"]
    attempts = payload["metadata"]["providerAttempts"]
    assert [attempt["provider"] for attempt in attempts] == ["searxng_json", "duckduckgo_html"]
    assert all(attempt["ok"] is False for attempt in attempts)
    assert "secret-token-value" not in json.dumps(payload)
    assert "secr...alue" in attempts[0]["searchUrl"]


def test_web_search_limits_calls_per_turn(tmp_path, monkeypatch):
    runtime = ToolRuntime(
        cwd=tmp_path,
        settings=Settings(
            model=ModelConfig(
                api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"
            )
        ),
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"results":[{"title":"Example","url":"https://example.com"}]}'

    monkeypatch.setattr(
        "deepy.tools.builtin._web_search_chat",
        lambda settings, prompt: (
            '{"dominant_language":"en","reason":"English results are richer."}'
        ),
    )
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse())

    for index in range(MAX_WEB_SEARCH_CALLS_PER_TURN):
        payload = decode(runtime.web_search(f"query {index}"))
        assert payload["ok"] is True

    payload = decode(runtime.web_search("one too many"))

    assert payload["ok"] is False
    assert "call limit reached" in payload["error"]
    assert payload["metadata"]["callLimit"] == MAX_WEB_SEARCH_CALLS_PER_TURN
