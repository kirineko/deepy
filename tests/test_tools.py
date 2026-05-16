from __future__ import annotations

import ast
import gzip
import json
import os
import shlex
import sys

from deepy.config import Settings
from deepy.config.settings import (
    DEFAULT_WEB_SEARCH_SEARXNG_URL,
    ModelConfig,
    ToolsConfig,
    WebSearchToolConfig,
)
from deepy.tools import ToolResult, ToolRuntime
from deepy.tools.agents import build_function_tools
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


def test_edit_uses_loose_escape_match_when_quotes_are_overescaped(tmp_path):
    target = tmp_path / "quotes.py"
    target.write_text('print("hello")\n', encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read("quotes.py"))
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

    decode(runtime.read("query.py"))
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

    decode(runtime.read("near.txt"))
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


def test_modify_creates_new_files_and_edits_existing_files(tmp_path):
    target = tmp_path / "existing.txt"
    target.write_text("old\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    created = decode(runtime.modify("new.txt", content="hello\n"))
    assert created["ok"] is True
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "hello\n"

    denied = decode(runtime.modify("existing.txt", content="changed\n"))
    assert denied["ok"] is False
    assert "old_string/new_string" in denied["error"]

    decode(runtime.read("existing.txt"))
    edited = decode(runtime.modify("existing.txt", old="old", new="new"))

    assert edited["ok"] is True
    assert target.read_text(encoding="utf-8") == "new\n"


def test_write_preserves_existing_crlf_line_endings(tmp_path):
    target = tmp_path / "windows.txt"
    target.write_text("alpha\r\nbeta\r\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read("windows.txt"))
    payload = decode(runtime.write("windows.txt", "one\ntwo\n"))

    assert payload["ok"] is True
    assert payload["metadata"]["line_endings"] == "CRLF"
    assert target.read_bytes() == b"one\r\ntwo\r\n"


def test_write_does_not_double_translate_existing_crlf_bytes(tmp_path):
    target = tmp_path / "windows.txt"
    target.write_bytes(b"alpha\r\nbeta\r\n")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    decode(runtime.read("windows.txt"))
    payload = decode(runtime.write("windows.txt", "one\ntwo\n"))

    assert payload["ok"] is True
    assert target.read_bytes() == b"one\r\ntwo\r\n"
    assert b"\r\r\n" not in target.read_bytes()


def test_write_preserves_existing_utf16le_encoding(tmp_path):
    target = tmp_path / "utf16.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-16")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    read_payload = decode(runtime.read("utf16.txt"))
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

    decode(runtime.read("utf8_sig.py"))
    payload = decode(runtime.write("utf8_sig.py", "城市=上海\n"))

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf8-sig"
    assert target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert target.read_bytes().decode("utf-8-sig") == "城市=上海\n"


def test_read_decodes_gbk_compatible_text(tmp_path):
    target = tmp_path / "gbk.txt"
    target.write_bytes("城市=北京\n".encode("gb18030"))
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read("gbk.txt"))

    assert payload["ok"] is True
    assert "1: 城市=北京" in payload["output"]
    assert payload["metadata"]["encoding"] == "gb18030"


def test_read_keeps_valid_utf8_classified_as_utf8(tmp_path):
    target = tmp_path / "utf8.txt"
    target.write_text("城市=北京\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    payload = decode(runtime.read("utf8.txt"))

    assert payload["ok"] is True
    assert "1: 城市=北京" in payload["output"]
    assert payload["metadata"]["encoding"] == "utf8"


def test_windows_new_non_ascii_text_file_stays_plain_utf8(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    payload = decode(runtime.modify("notes.py", content="# 中文注释\nprint('ok')\n"))
    target = tmp_path / "notes.py"

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf8"
    assert not target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert target.read_bytes().decode("utf-8") == "# 中文注释\nprint('ok')\n"


def test_windows_new_non_ascii_python_file_is_utf8_parser_safe(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    payload = decode(runtime.modify("script.py", content="# 中文注释\nprint('ok')\n"))
    target = tmp_path / "script.py"
    source = target.read_text(encoding="utf-8")

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf8"
    assert not source.startswith("\ufeff")
    ast.parse(source)


def test_windows_new_ascii_text_file_stays_plain_utf8(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    payload = decode(runtime.modify("notes.py", content="# comment\nprint('ok')\n"))
    target = tmp_path / "notes.py"

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf8"
    assert not target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert target.read_bytes() == b"# comment\nprint('ok')\n"


def test_posix_new_non_ascii_text_file_stays_plain_utf8(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="darwin")

    payload = decode(runtime.modify("notes.py", content="# 中文注释\nprint('ok')\n"))
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


def test_modify_content_after_out_of_band_delete_preserves_stale_protection(tmp_path):
    target = tmp_path / "notes.py"
    target.write_text("print('old')\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings(), platform_name="win32")

    decode(runtime.read("notes.py"))
    target.unlink()
    payload = decode(runtime.modify("notes.py", content="print('new')\n"))

    assert payload["ok"] is False
    assert payload["error"] == "File changed since it was read: it no longer exists."
    assert payload["metadata"]["recovery_kind"] == "stale_deleted_file"
    assert "do not recreate Unicode files through shell here-strings" in payload["metadata"]["recovery"]


def test_edit_preserves_existing_crlf_line_endings(tmp_path):
    target = tmp_path / "windows.txt"
    target.write_text("alpha\r\nbeta\r\n", encoding="utf-8")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read("windows.txt"))
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

    decode(runtime.read("unicode_demo.py"))
    payload = decode(
        runtime.modify(
            "unicode_demo.py",
            old="def demo():\n    title = '中文和Unicode字符演示程序'",
            new="def demo():\n    title = 'Unicode Character Demo Program'",
        )
    )

    assert payload["ok"] is True
    assert payload["metadata"]["matched_via"] == "line_endings"
    assert payload["metadata"]["line_endings"] == "CRLF"
    assert target.read_bytes() == (
        b"def demo():\r\n"
        b"    title = 'Unicode Character Demo Program'\r\n"
        b"    return title\r\n"
    )


def test_edit_preserves_existing_utf16le_encoding(tmp_path):
    target = tmp_path / "utf16.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-16")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read("utf16.txt"))
    payload = decode(runtime.edit("utf16.txt", "beta", "gamma"))

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "utf16le"
    assert target.read_bytes().startswith(b"\xff\xfe")
    assert target.read_text(encoding="utf-16") == "alpha\ngamma\n"


def test_edit_preserves_existing_gbk_compatible_encoding(tmp_path):
    target = tmp_path / "gbk.txt"
    target.write_bytes("城市=北京\n".encode("gb18030"))
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read("gbk.txt"))
    payload = decode(runtime.modify("gbk.txt", old="北京", new="上海"))

    assert payload["ok"] is True
    assert payload["metadata"]["encoding"] == "gb18030"
    assert target.read_bytes().decode("gb18030") == "城市=上海\n"


def test_edit_matches_gbk_compatible_crlf_file_with_lf_old_string(tmp_path):
    target = tmp_path / "gbk_crlf.txt"
    target.write_bytes("标题=中文\r\n城市=北京\r\n".encode("gb18030"))
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    decode(runtime.read("gbk_crlf.txt"))
    payload = decode(
        runtime.modify(
            "gbk_crlf.txt",
            old="标题=中文\n城市=北京",
            new="Title=Chinese\nCity=Beijing",
        )
    )

    assert payload["ok"] is True
    assert payload["metadata"]["matched_via"] == "line_endings"
    assert payload["metadata"]["encoding"] == "gb18030"
    assert payload["metadata"]["line_endings"] == "CRLF"
    assert target.read_bytes().decode("gb18030") == "Title=Chinese\r\nCity=Beijing\r\n"


def test_edit_matches_crlf_file_with_lf_old_string_in_snippet_scope(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_bytes(b"alpha\r\ntarget = 1\r\nomega\r\nbeta\r\ntarget = 1\r\ndone\r\n")
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    read_payload = decode(runtime.read("sample.txt", start_line=4, limit=2))
    snippet_id = read_payload["metadata"]["snippet"]["id"]
    payload = decode(
        runtime.modify(
            None,
            old="beta\ntarget = 1",
            new="beta\ntarget = 2",
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

    decode(runtime.read("near.txt"))
    payload = decode(runtime.modify("near.txt", old="bet = 1\nextra", new="beta = 2\nextra"))

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


def test_function_tools_have_stable_names_and_descriptions(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    tools = build_function_tools(runtime)

    assert [tool.name for tool in tools] == [
        "shell",
        "AskUserQuestion",
        "read",
        "modify",
        "WebSearch",
        "WebFetch",
        "load_skill",
    ]
    assert all(tool.description for tool in tools)
    shell_tool = tools[0]
    assert shell_tool.name == "shell"
    assert "current runtime shell" in shell_tool.description
    assert "command dialect" in shell_tool.description
    assert "persistent bash session" not in shell_tool.description
    ask_tool = tools[1]
    assert ask_tool.name == "AskUserQuestion"
    assert "偏好" in ask_tool.description
    assert "for Chinese requests, ask in Chinese" in ask_tool.description
    assert "low-impact details" in ask_tool.description
    skill_tool = tools[-1]
    assert skill_tool.name == "load_skill"
    assert "available Agent Skill" in skill_tool.description


def test_function_tool_schemas_match_shell_tool(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    tools = {tool.name: tool for tool in build_function_tools(runtime)}

    assert tools["shell"].params_json_schema["required"] == ["command"]
    assert list(tools["shell"].params_json_schema["properties"]) == ["command", "description"]
    assert tools["AskUserQuestion"].params_json_schema["required"] == ["questions"]
    assert list(tools["AskUserQuestion"].params_json_schema["properties"]) == ["questions"]
    assert tools["read"].params_json_schema["required"] == ["file_path"]
    assert list(tools["read"].params_json_schema["properties"]) == [
        "file_path",
        "offset",
        "limit",
        "pages",
    ]
    assert tools["modify"].params_json_schema["required"] == []
    assert "old_string/new_string" in tools["modify"].description
    assert list(tools["modify"].params_json_schema["properties"]) == [
        "file_path",
        "snippet_id",
        "content",
        "old_string",
        "new_string",
        "replace_all",
        "expected_occurrences",
    ]
    assert tools["WebSearch"].params_json_schema["required"] == ["query"]
    assert list(tools["WebSearch"].params_json_schema["properties"]) == ["query"]
    assert tools["WebFetch"].params_json_schema["required"] == ["url"]
    assert list(tools["WebFetch"].params_json_schema["properties"]) == ["url"]


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
        model=ModelConfig(api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"),
        tools=ToolsConfig(
            web_search=WebSearchToolConfig(
                searxng_url="https://search.example",
            )
        )
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
        model=ModelConfig(api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"),
        tools=ToolsConfig(
            web_search=WebSearchToolConfig(searxng_url="https://search.example")
        )
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
        model=ModelConfig(api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"),
        tools=ToolsConfig(
            web_search=WebSearchToolConfig(searxng_url="https://search.example")
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
    assert requested_urls == [
        "https://search.example/search?q=latest+DeepSeek+model&format=json"
    ]
    assert len(chat_prompts) == 2


def test_web_search_uses_default_searxng_backend(tmp_path, monkeypatch):
    settings = Settings(
        model=ModelConfig(api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"),
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
    assert payload["metadata"]["providerAttempts"] == [
        {"provider": "searxng_json", "ok": True}
    ]


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
        model=ModelConfig(api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"),
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
        model=ModelConfig(api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat"),
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
            model=ModelConfig(api_key="sk-test", base_url="https://api.deepseek.com", name="deepseek-chat")
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
