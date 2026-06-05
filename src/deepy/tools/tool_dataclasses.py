from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .shell_utils import RuntimeEnvironment


class MutationErrorCode:
    PATH_POLICY = "path_policy"
    SYMLINK_POLICY = "symlink_policy"
    SENSITIVE_POLICY = "sensitive_policy"
    APPROVAL_REQUIRED = "approval_required"
    GUARDRAIL_BLOCK = "guardrail_block"
    UNSUPPORTED_TARGET = "unsupported_target"
    STALE_SNAPSHOT = "stale_snapshot"
    MATCH_NOT_FOUND = "match_not_found"
    AMBIGUOUS_MATCH = "ambiguous_match"
    EXPECTED_COUNT_MISMATCH = "expected_count_mismatch"
    NO_OP = "no_op"
    PATCH_PARSE = "patch_parse_error"
    PATCH_APPLY = "patch_apply_error"
    ATOMIC_WRITE = "atomic_write_error"
    BACKUP = "backup_error"
    PARTIAL_COMMIT = "partial_commit"
    INVALID_ARGUMENTS = "invalid_arguments"


@dataclass(frozen=True)
class MutationPolicyDecision:
    decision: str = "allow"
    reason: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def result_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {"policyDecision": self.decision}
        if self.reason:
            metadata["policyReason"] = self.reason
        metadata.update(self.metadata)
        return metadata


@dataclass(frozen=True)
class AtomicWriteResult:
    fallback_used: bool = False
    retries: int = 0

    def metadata(self) -> dict[str, object]:
        return {
            "atomicWrite": True,
            "atomicFallbackUsed": self.fallback_used,
            "atomicRenameRetries": self.retries,
        }


@dataclass(frozen=True)
class MatchOccurrence:
    start_offset: int
    end_offset: int
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ClosestMatch:
    text: str
    start_line: int
    end_line: int
    score: float
    strategy: str


@dataclass(frozen=True)
class TextFileMetadata:
    content: str
    encoding: str
    line_endings: str


@dataclass(frozen=True)
class UpdateEdit:
    index: int
    path: str
    old: str
    new: str
    replace_all: bool
    expected_occurrences: int | None


@dataclass(frozen=True)
class PlannedUpdateFile:
    target: Path
    old_content: str
    new_content: str
    encoding: str
    line_endings: str
    policy: MutationPolicyDecision
    edit_indices: tuple[int, ...]
    occurrences: int
    skipped_edits: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class WebSearchPreparation:
    original_query: str
    resolved_query: str
    dominant_language: str
    language_reason: str
    translated: bool = False

    def metadata(self) -> dict[str, object]:
        return {
            "query": self.resolved_query,
            "originalQuery": self.original_query,
            "resolvedQuery": self.resolved_query,
            "translated": self.translated,
            "dominantLanguage": self.dominant_language,
            "languageReason": self.language_reason,
        }


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True)
class WebSearchProviderFailure:
    provider: str
    error: str
    search_url: str | None = None

    def metadata(self) -> dict[str, str]:
        from .web.search_parse import _mask_url_secrets

        payload = {"provider": self.provider, "error": self.error}
        if self.search_url:
            payload["searchUrl"] = _mask_url_secrets(self.search_url)
        return payload


@dataclass(frozen=True)
class WebSearchProviderResult:
    provider: str
    search_url: str
    results: list[WebSearchResult]


@dataclass(frozen=True)
class ShellInvocation:
    shell_path: str
    args: list[str]
    runtime_environment: RuntimeEnvironment
    env: dict[str, str] | None = None


@dataclass(frozen=True)
class PageRange:
    start: int
    end: int

    @property
    def count(self) -> int:
        return self.end - self.start + 1

    def label(self) -> str:
        return f"{self.start}-{self.end}"
