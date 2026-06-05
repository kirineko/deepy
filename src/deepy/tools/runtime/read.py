from __future__ import annotations

import concurrent.futures
from typing import cast

from deepy.utils import json as json_utils

from ..constants import DEFAULT_LINE_LIMIT, MAX_LINE_LENGTH
from ..media import _build_image_follow_up_message, _image_mime_type, _read_pdf
from ..mutation_policy import (
    _mutation_error_metadata,
    _resolve_read_target,
    _snippet_metadata,
)
from ..tool_dataclasses import MutationErrorCode
from ..payload_parsing import _format_notebook, _parse_v3_read_targets
from ..result import ToolResult
from ..shell_command import (
    _format_directory_entries,
    _truncate_line,
)
from ..text_io import _read_text_metadata
from .state import ToolRuntimeState


class ReadToolsMixin(ToolRuntimeState):
    def _read_file_result(
        self,
        path: str,
        start_line: int = 1,
        limit: int | None = None,
        pages: str | None = None,
        *,
        name: str = "Read",
    ) -> str:
        target, error = _resolve_read_target(self.cwd, path)
        if error is not None:
            return ToolResult.error_result(name, error).to_json()
        if target is None or not target.exists():
            return ToolResult.error_result(name, f"File does not exist: {path}").to_json()
        if target.is_dir():
            entries, visible_count, ignored_count = _format_directory_entries(target, self.cwd)
            return ToolResult.ok_result(
                name,
                entries,
                metadata={
                    "path": str(target),
                    "kind": "directory",
                    "entryCount": len(list(target.iterdir())),
                    "visibleEntryCount": visible_count,
                    "ignoredEntryCount": ignored_count,
                },
            ).to_json()

        if target.suffix.lower() == ".ipynb":
            output, error = _format_notebook(target)
            if error is not None:
                return ToolResult.error_result(
                    name, error, metadata={"path": str(target)}
                ).to_json()
            return ToolResult.ok_result(
                name,
                output,
                metadata={
                    "path": str(target),
                    "kind": "notebook",
                    "trackedForWrite": False,
                },
            ).to_json()

        if target.suffix.lower() == ".pdf":
            return _read_pdf(target, pages, name=name)

        mime = _image_mime_type(target.suffix.lower())
        if mime is not None:
            data = target.read_bytes()
            return ToolResult(
                ok=True,
                name=name,
                output="File loaded.",
                metadata={"path": str(target), "mime": mime, "bytes": len(data)},
                followUpMessages=[_build_image_follow_up_message(target, mime, data)],
            ).to_json()

        text_metadata = _read_text_metadata(target)
        text = text_metadata.content
        lines = text.splitlines()
        start = max(len(lines) + start_line, 0) if start_line < 0 else max(start_line, 1) - 1
        effective_limit = limit if limit and limit > 0 else DEFAULT_LINE_LIMIT
        selected = lines[start : start + effective_limit]
        formatted_lines = [_truncate_line(line) for line in selected]
        truncated = start + len(selected) < len(lines) or any(
            len(line) > MAX_LINE_LENGTH for line in selected
        )
        full_file_read = start == 0 and not truncated
        numbered = "\n".join(
            f"{idx + start + 1}: {line}" for idx, line in enumerate(formatted_lines)
        )
        if full_file_read:
            self.file_state.mark_read(
                target,
                encoding=text_metadata.encoding,
                line_endings=text_metadata.line_endings,
            )
        snippet_metadata = None
        if not full_file_read and selected:
            snippet = self.file_state.create_snippet(
                target,
                start_line=start + 1,
                end_line=start + len(selected),
                text="\n".join(selected),
            )
            self.file_state.mark_read(
                target,
                full=False,
                encoding=text_metadata.encoding,
                line_endings=text_metadata.line_endings,
            )
            snippet_metadata = _snippet_metadata(snippet)
        metadata: dict[str, object] = {
            "path": str(target),
            "kind": "file",
            "startLine": start + 1,
            "lineCount": len(selected),
            "lineLimit": effective_limit,
            "totalLines": len(lines),
            "truncated": truncated,
            "trackedForWrite": full_file_read,
            "encoding": text_metadata.encoding,
            "line_endings": text_metadata.line_endings,
        }
        if snippet_metadata is not None:
            metadata["snippet"] = snippet_metadata
        return ToolResult.ok_result(
            name,
            numbered,
            metadata=metadata,
        ).to_json()
    def read(self, request: object) -> str:
        targets, error = _parse_v3_read_targets(request)
        if error is not None:
            return ToolResult.error_result(
                "Read",
                error,
                metadata=_mutation_error_metadata(
                    MutationErrorCode.INVALID_ARGUMENTS,
                    recovery="Pass {'path': 'file'} or {'files': [{'path': 'file'}]}.",
                ),
            ).to_json()
        if len(targets) == 1:
            target = targets[0]
            path = cast(str, target["path"])
            start_line = cast(int, target["start_line"])
            limit = cast(int | None, target["limit"])
            pages = cast(str | None, target["pages"])
            return self._read_file_result(
                path,
                start_line=start_line,
                limit=limit,
                pages=pages,
                name="Read",
            )

        results: list[dict[str, object]] = []
        max_workers = min(8, max(1, len(targets)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_by_index: dict[concurrent.futures.Future[str], int] = {}
            for index, target in enumerate(targets):
                future = executor.submit(
                    self._read_file_result,
                    cast(str, target["path"]),
                    start_line=cast(int, target["start_line"]),
                    limit=cast(int | None, target["limit"]),
                    pages=cast(str | None, target["pages"]),
                    name="Read",
                )
                future_by_index[future] = index
            for future in concurrent.futures.as_completed(future_by_index):
                index = future_by_index[future]
                target = targets[index]
                try:
                    payload = json_utils.loads(future.result())
                except Exception as exc:
                    payload = {
                        "ok": False,
                        "name": "Read",
                        "output": "",
                        "error": f"Read target failed: {exc}",
                        "metadata": {"path": target["path"]},
                    }
                if not isinstance(payload, dict):
                    payload = {
                        "ok": False,
                        "name": "Read",
                        "output": "",
                        "error": "Read target returned an invalid result.",
                        "metadata": {"path": target["path"]},
                    }
                metadata = payload.get("metadata")
                metadata_dict = metadata if isinstance(metadata, dict) else {}
                results.append(
                    {
                        "index": index,
                        "path": str(metadata_dict.get("path") or target["path"]),
                        "ok": bool(payload.get("ok")),
                        "output": str(payload.get("output") or ""),
                        "error": payload.get("error"),
                        "metadata": metadata_dict,
                    }
                )
        results.sort(key=lambda item: int(item["index"]))
        success_count = sum(1 for item in results if item["ok"] is True)
        lines: list[str] = []
        for item in results:
            status = "ok" if item["ok"] is True else "failed"
            lines.append(f"## {item['path']} [{status}]")
            if item["ok"] is True:
                output = str(item.get("output") or "")
                lines.append(output if output else "[No content]")
            else:
                lines.append(str(item.get("error") or "Read failed."))
            lines.append("")
        return ToolResult.ok_result(
            "Read",
            "\n".join(lines).rstrip(),
            metadata={
                "kind": "batch",
                "targetCount": len(results),
                "successCount": success_count,
                "failureCount": len(results) - success_count,
                "targets": results,
                "paths": [str(item["path"]) for item in results],
            },
        ).to_json()
