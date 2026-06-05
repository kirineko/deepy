from __future__ import annotations

from pathlib import Path


from ..mutation_policy import (
    _mutation_error_metadata,
    _mutation_policy_decision,
    _policy_error_result,
    _resolve_mutation_target,
    _unsupported_text_mutation_reason,
)
from ..payload_parsing import _parse_v3_update_edits
from ..result import ToolResult
from ..shell_command import _normalize_line_endings
from ..text_io import (
    _atomic_write_text_with_encoding,
    _coerce_write_content,
    _default_new_text_encoding,
    _new_file_line_endings,
    _patch_changed_path_summary,
    _read_text_metadata,
    _stale_write_recovery_metadata,
    _unified_diff,
)
from ..tool_dataclasses import MutationErrorCode, PlannedUpdateFile, UpdateEdit
from .mutation_preflight import MutationPreflightMixin


class MutationApplyMixin(MutationPreflightMixin):
    def _write_result(
        self,
        path: str,
        content: object,
        *,
        overwrite: bool = True,
        name: str = "Write",
    ) -> str:
        target, error, metadata = _resolve_mutation_target(self.cwd, path)
        if error is not None or target is None:
            return ToolResult.error_result(name, error or "Invalid file path.", metadata=metadata).to_json()
        if target.exists():
            if not overwrite:
                return ToolResult.error_result(
                    name,
                    "File already exists; explicit overwrite intent is required.",
                    metadata=_mutation_error_metadata(MutationErrorCode.INVALID_ARGUMENTS, path=target),
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
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_result = _atomic_write_text_with_encoding(
            target,
            normalized_content,
            encoding,
            platform_name=self.platform_name,
        )
        snapshot = self.file_state.mark_written(
            target,
            encoding=encoding,
            line_endings=line_endings,
        )
        diff = _unified_diff(old_content, normalized_content, path=str(target))
        return ToolResult.ok_result(
            name,
            f"Wrote {target}",
            metadata={
                "path": str(target),
                "encoding": encoding,
                "line_endings": line_endings,
                "changedFiles": [str(target)],
                "policyDecision": policy.decision,
                **policy.result_metadata(),
                **atomic_result.metadata(),
                **repair_metadata,
                "diff": diff,
                "diff_preview": diff,
                "trackedForWrite": snapshot is not None,
            },
        ).to_json()
    def write_v3(self, path: str, content: object, *, overwrite: bool = False) -> str:
        target, _, _ = _resolve_mutation_target(self.cwd, path)
        if target is not None and target.exists() and not overwrite:
            return ToolResult.error_result(
                "Write",
                "Existing file replacement requires overwrite=true.",
                metadata=_mutation_error_metadata(
                    MutationErrorCode.INVALID_ARGUMENTS,
                    path=target,
                    recovery="Pass overwrite=true only when replacing the whole existing file.",
                ),
            ).to_json()
        return self._write_result(path, content, overwrite=overwrite, name="Write")
    def update(self, request: object) -> str:
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
                },
            ).to_json()

        committed: list[dict[str, object]] = []
        changed_files: list[str] = []
        diffs: list[str] = []
        attempted: list[tuple[Path, str, str]] = []
        try:
            for plan in planned:
                attempted.append((plan.target, plan.old_content, plan.encoding))
                atomic_result = _atomic_write_text_with_encoding(
                    plan.target,
                    plan.new_content,
                    plan.encoding,
                    platform_name=self.platform_name,
                )
                self.file_state.mark_written(
                    plan.target,
                    encoding=plan.encoding,
                    line_endings=plan.line_endings,
                )
                changed_files.append(str(plan.target))
                diff = _unified_diff(plan.old_content, plan.new_content, path=str(plan.target))
                diffs.append(diff)
                committed.append(
                    {
                        "path": str(plan.target),
                        "editIndices": list(plan.edit_indices),
                        "actualOccurrences": plan.occurrences,
                        "skippedEditIndices": [
                            skipped.get("index") for skipped in plan.skipped_edits
                        ],
                        "encoding": plan.encoding,
                        "line_endings": plan.line_endings,
                        **atomic_result.metadata(),
                    }
                )
        except OSError as exc:
            rollback_failures: list[str] = []
            for target, old_content, encoding in reversed(attempted):
                try:
                    _atomic_write_text_with_encoding(
                        target,
                        old_content,
                        encoding,
                        platform_name=self.platform_name,
                    )
                    self.file_state.mark_written(target, encoding=encoding)
                except OSError as rollback_exc:
                    rollback_failures.append(f"{target}: {rollback_exc}")
            return ToolResult.error_result(
                "Update",
                f"Update commit failed after partial changes: {exc}",
                metadata=_mutation_error_metadata(
                    MutationErrorCode.PARTIAL_COMMIT,
                    committedOperations=committed,
                    failedError=str(exc),
                    rollbackFailures=rollback_failures,
                    rolledBack=not rollback_failures,
                ),
            ).to_json()

        diff_items = [item for item in diffs if item]
        unique_changed_files = list(dict.fromkeys(changed_files))
        return ToolResult.ok_result(
            "Update",
            f"Updated {len(unique_changed_files)} file(s) with {len(edits)} edit(s).",
            metadata={
                "path": _patch_changed_path_summary(unique_changed_files),
                "changedFiles": unique_changed_files,
                "editCount": len(edits),
                "appliedEditCount": sum(len(plan.edit_indices) for plan in planned),
                "skippedEditCount": len(skipped_edits),
                "skippedEdits": skipped_edits,
                "changedFileCount": len(unique_changed_files),
                "operations": committed,
                "policyDecision": "allow",
                "diff": "\n".join(diff_items),
                "diff_preview": "\n".join(diff_items),
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
