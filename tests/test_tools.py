from __future__ import annotations

import json
import os
from types import SimpleNamespace

from deepy.config import Settings
from deepy.config.settings import ToolsConfig, WebSearchToolConfig
from deepy.tools import ToolResult, ToolRuntime
from deepy.tools.agents import build_function_tools
from deepy.tools.builtin import DEFAULT_LINE_LIMIT, MAX_BASH_OUTPUT_CHARS, MAX_LINE_LENGTH


def decode(payload: str) -> dict:
    return json.loads(payload)


def test_tool_result_shape_is_stable():
    payload = decode(ToolResult.ok_result("read", "hello").to_json())

    assert payload == {
        "ok": True,
        "name": "read",
        "output": "hello",
        "error": None,
        "metadata": {},
        "awaitUserResponse": False,
    }


def test_read_marks_file_and_edit_requires_prior_read(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    denied = decode(runtime.edit("a.txt", "one", "ONE"))
    assert denied["ok"] is False
    assert "read before" in denied["error"]

    read_payload = decode(runtime.read("a.txt"))
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

    payload = decode(runtime.read("."))

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
    (tmp_path / ".gitignore").write_text("ignored.log\nignored_dir/\nspec/\nreference/\n", encoding="utf-8")
    (tmp_path / "ignored.log").write_text("secret", encoding="utf-8")
    (tmp_path / "ignored_dir").mkdir()
    (tmp_path / "visible.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "spec").mkdir()
    (tmp_path / "reference").mkdir()
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read("."))

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

    payload = decode(runtime.read("settings.py"))

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

    payload = decode(runtime.read("settings.py"))

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

    payload = decode(runtime.read("settings.py"))

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

    payload = decode(runtime.read("demo.ipynb"))

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

    payload = decode(runtime.read("broken.ipynb"))

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

    payload = decode(runtime.read("pixel.png"))

    assert payload["ok"] is True
    assert payload["output"] == "File loaded."
    assert payload["metadata"]["mime"] == "image/png"
    assert payload["metadata"]["bytes"] == image.stat().st_size
    assert len(payload["followUpMessages"]) == 1
    follow_up = payload["followUpMessages"][0]
    assert follow_up["role"] == "system"
    assert "pixel.png" in follow_up["content"]
    content_params = follow_up["contentParams"]
    assert content_params[0]["type"] == "image_url"
    assert content_params[0]["image_url"]["url"].startswith("data:image/png;base64,")


def _write_fake_pdf(path, page_count: int):
    pages = "\n".join(f"{idx} 0 obj << /Type /Page >> endobj" for idx in range(1, page_count + 1))
    path.write_bytes(f"%PDF-1.4\n{pages}\ntrailer << /Type /Pages >>\n%%EOF".encode("latin1"))


def test_read_pdf_returns_base64_with_metadata(tmp_path):
    pdf = tmp_path / "small.pdf"
    _write_fake_pdf(pdf, 2)
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read("small.pdf"))

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

    payload = decode(runtime.read("large.pdf"))

    assert payload["ok"] is False
    assert 'provide "pages" to read a range' in payload["error"]
    assert payload["metadata"]["pageCount"] == 11


def test_read_pdf_accepts_page_range_metadata(tmp_path):
    pdf = tmp_path / "large.pdf"
    _write_fake_pdf(pdf, 11)
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read("large.pdf", pages="2-3"))

    assert payload["ok"] is True
    assert payload["metadata"]["pageCount"] == 11
    assert payload["metadata"]["pages"] == "2-3"


def test_read_pdf_rejects_invalid_page_range(tmp_path):
    pdf = tmp_path / "small.pdf"
    _write_fake_pdf(pdf, 2)
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    too_many = decode(runtime.read("small.pdf", pages="1-21"))
    assert too_many["ok"] is False
    assert "exceeds 20 pages" in too_many["error"]

    out_of_bounds = decode(runtime.read("small.pdf", pages="3"))
    assert out_of_bounds["ok"] is False
    assert "exceeds total page count" in out_of_bounds["error"]


def test_read_limits_large_files_by_default(tmp_path):
    target = tmp_path / "large.txt"
    target.write_text(
        "".join(f"line {idx}\n" for idx in range(DEFAULT_LINE_LIMIT + 5)),
        encoding="utf-8",
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read("large.txt"))

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

    payload = decode(runtime.read("long.txt"))

    assert payload["ok"] is True
    assert "... [truncated]" in payload["output"]
    assert payload["metadata"]["truncated"] is True
    assert payload["metadata"]["trackedForWrite"] is False


def test_partial_read_does_not_unlock_existing_file_for_edit(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read("a.txt", start_line=2, limit=1))
    denied = decode(runtime.edit("a.txt", "two", "TWO"))

    assert payload["ok"] is True
    assert payload["metadata"]["trackedForWrite"] is False
    assert denied["ok"] is False
    assert "read before" in denied["error"]


def test_partial_read_returns_snippet_metadata(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read("a.txt", start_line=2, limit=1))

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

    read_payload = decode(runtime.read("sample.txt", start_line=4, limit=2))
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


def test_edit_returns_candidate_snippets_when_old_text_is_not_unique(tmp_path):
    target = tmp_path / "duplicate.txt"
    target.write_text("city\ncity\nsalary\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read("duplicate.txt"))
    payload = decode(runtime.edit("duplicate.txt", "city", "location"))

    assert payload["ok"] is False
    assert payload["error"] == "old_string is not unique; use snippet_id, replace_all, or provide more context."
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

    decode(runtime.read("duplicate.txt"))
    duplicate = decode(runtime.edit("duplicate.txt", "city", "location"))
    snippet_id = duplicate["metadata"]["candidates"][1]["snippet_id"]
    edited = decode(runtime.edit("duplicate.txt", "city", "location", snippet_id=snippet_id))

    assert edited["ok"] is True
    assert edited["metadata"]["read_scope_type"] == "snippet"
    assert target.read_text(encoding="utf-8") == "city\nlocation\nsalary\n"


def test_edit_detects_mtime_change_after_read(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("one\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read("a.txt"))
    target.write_text("changed\n", encoding="utf-8")
    os.utime(target, ns=(target.stat().st_atime_ns, target.stat().st_mtime_ns + 1_000_000))

    payload = decode(runtime.edit("a.txt", "changed", "updated"))

    assert payload["ok"] is False
    assert "changed since it was read" in payload["error"]


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


def test_write_preserves_existing_crlf_line_endings(tmp_path):
    target = tmp_path / "windows.txt"
    target.write_text("alpha\r\nbeta\r\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read("windows.txt"))
    payload = decode(runtime.write("windows.txt", "one\ntwo\n"))

    assert payload["ok"] is True
    assert payload["metadata"]["line_endings"] == "CRLF"
    assert target.read_bytes() == b"one\r\ntwo\r\n"


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


def test_edit_preserves_existing_crlf_line_endings(tmp_path):
    target = tmp_path / "windows.txt"
    target.write_text("alpha\r\nbeta\r\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read("windows.txt"))
    payload = decode(runtime.edit("windows.txt", "beta", "gamma"))

    assert payload["ok"] is True
    assert payload["metadata"]["line_endings"] == "CRLF"
    assert target.read_bytes() == b"alpha\r\ngamma\r\n"


def test_bash_runs_in_session_cwd_and_tracks_simple_cd(tmp_path):
    subdir = tmp_path / "sub"
    subdir.mkdir()
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.bash("cd sub"))

    assert payload["ok"] is True
    assert runtime.cwd == subdir


def test_bash_tracks_cwd_after_compound_cd_command(tmp_path):
    subdir = tmp_path / "sub"
    subdir.mkdir()
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.bash("cd sub && pwd"))

    assert payload["ok"] is True
    assert payload["metadata"]["cwd"] == str(subdir)
    assert payload["output"].strip() == str(subdir)
    assert runtime.cwd == subdir


def test_bash_tracks_cwd_even_when_command_fails(tmp_path):
    subdir = tmp_path / "sub"
    subdir.mkdir()
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.bash("cd sub && false"))

    assert payload["ok"] is False
    assert payload["metadata"]["exitCode"] == 1
    assert payload["metadata"]["cwd"] == str(subdir)
    assert runtime.cwd == subdir


def test_bash_uses_shell_compatibility_wrapper(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.bash("printf hidden >nul"))

    assert payload["ok"] is True
    assert payload["output"] == ""
    assert payload["metadata"]["shellPath"]
    assert not (tmp_path / "nul").exists()


def test_bash_truncates_large_output(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.bash("printf 'x%.0s' {1..31000}"))

    assert payload["ok"] is True
    assert len(payload["output"]) > MAX_BASH_OUTPUT_CHARS
    assert len(payload["output"]) < 31_000
    assert payload["output"].endswith("... [truncated 1000 chars]")
    assert payload["metadata"]["outputTruncated"] is True


def test_bash_caps_captured_output_before_formatting(tmp_path, monkeypatch):
    monkeypatch.setattr("deepy.tools.builtin.MAX_BASH_CAPTURE_CHARS", 10)
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.bash("printf 'x%.0s' {1..25}"))

    assert payload["ok"] is True
    assert payload["output"] == "x" * 10
    assert payload["metadata"]["captureTruncated"] is True
    assert payload["metadata"]["outputTruncated"] is False


def test_bash_timeout_tracks_and_clears_process(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.bash("sleep 1", timeout_ms=20))

    assert payload["ok"] is False
    assert "timed out" in payload["error"]
    assert payload["metadata"]["interrupted"] is True
    assert payload["metadata"]["processId"]
    assert runtime.running_processes == {}


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


def test_function_tools_have_stable_names_and_descriptions(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    tools = build_function_tools(runtime)

    assert [tool.name for tool in tools] == [
        "bash",
        "read",
        "write",
        "edit",
        "AskUserQuestion",
        "WebSearch",
    ]
    assert all(tool.description for tool in tools)


def test_web_search_uses_configured_api_url(tmp_path, monkeypatch):
    settings = Settings(
        tools=ToolsConfig(web_search=WebSearchToolConfig(api_url="https://search.example/api"))
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=settings)
    requested: list[str] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"results"

    def fake_urlopen(url, timeout):
        requested.append(url)
        assert timeout == 30
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = decode(runtime.web_search("deep seek"))

    assert payload["ok"] is True
    assert payload["output"] == "results"
    assert requested == ["https://search.example/api?q=deep+seek"]


def test_web_search_prefers_configured_command_over_api_url(tmp_path, monkeypatch):
    settings = Settings(
        tools=ToolsConfig(
            web_search=WebSearchToolConfig(
                command="search-tool",
                api_url="https://search.example/api",
            )
        )
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=settings)
    commands: list[str] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        assert kwargs["cwd"] == tmp_path
        return SimpleNamespace(returncode=0, stdout="local results", stderr="")

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("api_url should not be used when command is configured")

    monkeypatch.setattr("deepy.tools.builtin.subprocess.run", fake_run)
    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)

    payload = decode(runtime.web_search("deep seek"))

    assert payload["ok"] is True
    assert payload["output"] == "local results"
    assert commands == ["search-tool 'deep seek'"]
