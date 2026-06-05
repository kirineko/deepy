from __future__ import annotations

from pathlib import Path
from typing import cast

from deepy.utils import json as json_utils

from ..mutation_policy import (
    _mutation_error_metadata,
    _mutation_policy_decision,
    _policy_error_result,
    _resolve_mutation_target,
    _unsupported_text_mutation_reason,
    _update_noop_metadata,
)
from ..payload_parsing import _parse_v3_update_edits
from ..result import ToolResult
from ..shell_command import _normalize_line_endings
from ..text_io import (
    _coerce_write_content,
    _default_new_text_encoding,
    _new_file_line_endings,
    _patch_changed_path_summary,
    _read_text_metadata,
    _stale_write_recovery_metadata,
    _unified_diff,
)
from ..text_match import _build_closest_match_metadata, _find_closest_match
from ..tool_dataclasses import MutationErrorCode, PlannedUpdateFile, UpdateEdit
from .state import ToolRuntimeState


class MutationPreflightMixin(ToolRuntimeState):
    def preflight_file_mutation(self, tool_name: str, arguments: str) -> dict[str, object]:
        try:
            parsed = json_utils.loads(arguments)
        except json_utils.JSONDecodeError:
            return cast(
                dict[str, object],
                json_utils.loads(
                    ToolResult.error_result(
                        tool_name or "tool",
                        "Preflight requires valid JSON arguments.",
                        metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS),
                    ).to_json()
                ),
            )
        if not isinstance(parsed, dict):
            return cast(
                dict[str, object],
                json_utils.loads(
                    ToolResult.error_result(
                        tool_name or "tool",
                        "Preflight requires object arguments.",
                        metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS),
                    ).to_json()
                ),
            )
        if tool_name == "Write":
            result = self.preflight_write(
                str(parsed.get("path") or ""),
                parsed.get("content"),
                overwrite=bool(parsed.get("overwrite")),
                name="Write",
            )
        elif tool_name == "Update":
            result = self.preflight_update(parsed)
        else:
            result = ToolResult.error_result(
                tool_name or "tool",
                "Preflight is only supported for Write and Update.",
                metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS),
            ).to_json()
        return cast(dict[str, object], json_utils.loads(result))
    def preflight_write(
        self,
        path: str,
        content: object,
        *,
        overwrite: bool = False,
        name: str = "Write",
    ) -> str:
        target, error, metadata = _resolve_mutation_target(self.cwd, path)
        if error is not None or target is None:
            return ToolResult.error_result(name, error or "Invalid file path.", metadata=metadata).to_json()
        if target.exists() and not overwrite:
            return ToolResult.error_result(
                name,
                "Existing file replacement requires overwrite=true.",
                metadata=_mutation_error_metadata(
                    MutationErrorCode.INVALID_ARGUMENTS,
                    path=target,
                    recovery="Pass overwrite=true only when replacing the whole existing file.",
                ),
            ).to_json()
        policy = _mutation_policy_decision(self.cwd, target)
        policy_error = _policy_error_result(name, policy)
        if policy_error is not None:
            return policy_error
        unsupported_reason = _unsupported_text_mutation_reason(target)
        if unsupported_reason is not None:
            return ToolResult.error_result(
                name,
                unsupported_reason,
                metadata=_mutation_error_metadata(MutationErrorCode.UNSUPPORTED_TARGET, path=target),
            ).to_json()
        snapshot_status = self.file_state.snapshot_status(target)
        if target.exists() and snapshot_status in {"missing", "partial"}:
            text_metadata = _read_text_metadata(target)
            self.file_state.mark_read(
                target,
                encoding=text_metadata.encoding,
                line_endings=text_metadata.line_endings,
            )
        ok, error = self.file_state.check_writable(target, require_read=True)
        if not ok:
            metadata = _stale_write_recovery_metadata(target, error)
            return ToolResult.error_result(
                name,
                error or "File is not writable.",
                metadata={
                    **_mutation_error_metadata(
                        MutationErrorCode.STALE_SNAPSHOT,
                        path=target,
                        recovery="Re-read the file before retrying.",
                    ),
                    **metadata,
                },
            ).to_json()
        text_content, repair_metadata, content_error = _coerce_write_content(target, content)
        if content_error is not None:
            return ToolResult.error_result(
                name,
                content_error,
                metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS, path=target),
            ).to_json()
        existing_metadata = _read_text_metadata(target) if target.exists() else None
        old_content = existing_metadata.content if existing_metadata is not None else ""
        encoding = (
            existing_metadata.encoding
            if existing_metadata is not None
            else _default_new_text_encoding()
        )
        line_endings = (
            existing_metadata.line_endings
            if existing_metadata is not None
            else _new_file_line_endings(target, text_content)
        )
        normalized_content = _normalize_line_endings(text_content, line_endings)
        if old_content == normalized_content and target.exists():
            return ToolResult.error_result(
                name,
                "Mutation would not change file content.",
                metadata=_mutation_error_metadata(MutationErrorCode.NO_OP, path=target),
            ).to_json()
        diff = _unified_diff(old_content, normalized_content, path=str(target))
        return ToolResult.ok_result(
            name,
            f"Proposed write to {target}",
            metadata={
                "path": str(target),
                "encoding": encoding,
                "line_endings": line_endings,
                "changedFiles": [str(target)],
                "policyDecision": policy.decision,
                **policy.result_metadata(),
                **repair_metadata,
                "diff": diff,
                "diff_preview": diff,
                "preflight": True,
            },
        ).to_json()
    def preflight_update(self, request: object) -> str:
        edits, error, metadata = _parse_v3_update_edits(request)
        if error is not None:
            return ToolResult.error_result(
                "Update",
                error,
                metadata={
                    **_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS),
                    **metadata,
                },
            ).to_json()
        if not edits:
            return ToolResult.error_result(
                "Update",
                "Update requires at least one edit.",
                metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS),
            ).to_json()

        by_path: dict[Path, list[UpdateEdit]] = {}
        failures: list[dict[str, object]] = []
        skipped_edits: list[dict[str, object]] = []
        for edit in edits:
            target, resolve_error, resolve_metadata = _resolve_mutation_target(self.cwd, edit.path)
            if resolve_error is not None or target is None:
                failures.append(
                    {
                        "index": edit.index,
                        "path": edit.path,
                        "error": resolve_error or "Invalid file path.",
                        **resolve_metadata,
                    }
                )
                continue
            by_path.setdefault(target, []).append(edit)

        planned: list[PlannedUpdateFile] = []
        for target, file_edits in by_path.items():
            plan, plan_failures, plan_skipped = self._plan_update_file(target, file_edits)
            failures.extend(plan_failures)
            skipped_edits.extend(plan_skipped)
            if plan is not None:
                planned.append(plan)

        if failures:
            return ToolResult.error_result(
                "Update",
                "Update preflight failed; no file changes were committed.",
                metadata=_mutation_error_metadata(
                    MutationErrorCode.PATCH_APPLY,
                    failures=failures,
                    preflightFailed=True,
                    preflight=True,
                    editCount=len(edits),
                    fileCount=len(by_path),
                    skippedEdits=skipped_edits,
                    skippedEditCount=len(skipped_edits),
                ),
            ).to_json()

        if not planned:
            return ToolResult.ok_result(
                "Update",
                f"Update no-op; skipped {len(skipped_edits)} edit(s).",
                metadata={
                    "path": "",
                    "changedFiles": [],
                    "editCount": len(edits),
                    "appliedEditCount": 0,
                    "skippedEditCount": len(skipped_edits),
                    "skippedEdits": skipped_edits,
                    "changedFileCount": 0,
                    "operations": [],
                    "policyDecision": "allow",
                    "diff": "",
                    "diff_preview": "",
                    "noOp": True,
                    "preflight": True,
                },
            ).to_json()

        changed_files: list[str] = []
        diffs: list[str] = []
        operations: list[dict[str, object]] = []
        for plan in planned:
            changed_files.append(str(plan.target))
            diffs.append(_unified_diff(plan.old_content, plan.new_content, path=str(plan.target)))
            operations.append(
                {
                    "path": str(plan.target),
                    "editIndices": list(plan.edit_indices),
                    "actualOccurrences": plan.occurrences,
                    "skippedEditIndices": [skipped.get("index") for skipped in plan.skipped_edits],
                    "encoding": plan.encoding,
                    "line_endings": plan.line_endings,
                }
            )

        diff_items = [item for item in diffs if item]
        unique_changed_files = list(dict.fromkeys(changed_files))
        return ToolResult.ok_result(
            "Update",
            f"Proposed update to {len(unique_changed_files)} file(s) with {len(edits)} edit(s).",
            metadata={
                "path": _patch_changed_path_summary(unique_changed_files),
                "changedFiles": unique_changed_files,
                "editCount": len(edits),
                "appliedEditCount": sum(len(plan.edit_indices) for plan in planned),
                "skippedEditCount": len(skipped_edits),
                "skippedEdits": skipped_edits,
                "changedFileCount": len(unique_changed_files),
                "operations": operations,
                "policyDecision": "allow",
                "diff": "\n".join(diff_items),
                "diff_preview": "\n".join(diff_items),
                "preflight": True,
                **(
                    {
                        "encoding": planned[0].encoding,
                        "line_endings": planned[0].line_endings,
                    }
                    if len(planned) == 1
                    else {}
                ),
            },
        ).to_json()
    def _plan_update_file(
        self,
        target: Path,
        edits: list[UpdateEdit],
    ) -> tuple[PlannedUpdateFile | None, list[dict[str, object]], list[dict[str, object]]]:
        failures: list[dict[str, object]] = []
        skipped_edits: list[dict[str, object]] = []
        if not target.exists():
            return None, [
                {
                    "index": edit.index,
                    "path": str(target),
                    "error": f"File does not exist: {target}",
                    **_mutation_error_metadata(MutationErrorCode.UNSUPPORTED_TARGET, path=target),
                }
                for edit in edits
            ], []
        policy = _mutation_policy_decision(self.cwd, target)
        policy_error = _policy_error_result("Update", policy)
        if policy_error is not None:
            parsed = json_utils.loads(policy_error)
            return None, [
                {
                    "index": edit.index,
                    "path": str(target),
                    "error": parsed.get("error") or "Mutation rejected by policy.",
                    **(parsed.get("metadata", {}) if isinstance(parsed.get("metadata"), dict) else {}),
                }
                for edit in edits
            ], []
        unsupported_reason = _unsupported_text_mutation_reason(target)
        if unsupported_reason is not None:
            return None, [
                {
                    "index": edit.index,
                    "path": str(target),
                    "error": unsupported_reason,
                    **_mutation_error_metadata(MutationErrorCode.UNSUPPORTED_TARGET, path=target),
                }
                for edit in edits
            ], []
        snapshot_status = self.file_state.snapshot_status(target)
        if snapshot_status in {"missing", "partial"}:
            text_metadata = _read_text_metadata(target)
            self.file_state.mark_read(
                target,
                encoding=text_metadata.encoding,
                line_endings=text_metadata.line_endings,
            )
        ok, stale_error = self.file_state.check_writable(target, require_read=True)
        if not ok:
            return None, [
                {
                    "index": edit.index,
                    "path": str(target),
                    "error": stale_error or "File is not writable.",
                    **_mutation_error_metadata(
                        MutationErrorCode.STALE_SNAPSHOT,
                        path=target,
                        recovery="Call Read for this path before retrying Update.",
                    ),
                }
                for edit in edits
            ], []
        metadata = _read_text_metadata(target)
        original = metadata.content
        staged = original
        total_occurrences = 0
        applied_indices: list[int] = []
        for edit in edits:
            normalized_old = _normalize_line_endings(edit.old, metadata.line_endings)
            normalized_new = _normalize_line_endings(edit.new, metadata.line_endings)
            if normalized_old == normalized_new:
                skipped_edits.append(_update_noop_metadata(edit, target))
                continue
            count = staged.count(normalized_old)
            if count == 0:
                closest = _find_closest_match(staged, normalized_old, (0, len(staged)))
                closest_metadata = (
                    {"closest_match": _build_closest_match_metadata(self.file_state, target, closest)}
                    if closest is not None
                    else {}
                )
                failures.append(
                    {
                        "index": edit.index,
                        "path": str(target),
                        "error": "old text not found in file.",
                        **_mutation_error_metadata(MutationErrorCode.MATCH_NOT_FOUND, path=target),
                        **closest_metadata,
                    }
                )
                continue
            if edit.expected_occurrences is not None and count != edit.expected_occurrences:
                failures.append(
                    {
                        "index": edit.index,
                        "path": str(target),
                        "error": "old text match count did not equal expected_occurrences.",
                        **_mutation_error_metadata(
                            MutationErrorCode.EXPECTED_COUNT_MISMATCH,
                            path=target,
                            expectedOccurrences=edit.expected_occurrences,
                            actualOccurrences=count,
                        ),
                    }
                )
                continue
            if count > 1 and not edit.replace_all:
                failures.append(
                    {
                        "index": edit.index,
                        "path": str(target),
                        "error": "old text is not unique; provide more context or set replace_all=true.",
                        **_mutation_error_metadata(
                            MutationErrorCode.AMBIGUOUS_MATCH,
                            path=target,
                            actualOccurrences=count,
                        ),
                    }
                )
                continue
            replacements = count if edit.replace_all else 1
            staged = staged.replace(normalized_old, normalized_new, replacements)
            total_occurrences += replacements
            applied_indices.append(edit.index)
        if failures:
            return None, failures, skipped_edits
        if staged == original:
            applied_noops = [
                _update_noop_metadata(edit, target)
                for edit in edits
                if edit.index in set(applied_indices)
            ]
            return None, [], [*skipped_edits, *applied_noops]
        plan = PlannedUpdateFile(
            target=target,
            old_content=original,
            new_content=staged,
            encoding=metadata.encoding,
            line_endings=metadata.line_endings,
            policy=policy,
            edit_indices=tuple(applied_indices),
            occurrences=total_occurrences,
            skipped_edits=tuple(skipped_edits),
        )
        return plan, [], skipped_edits
