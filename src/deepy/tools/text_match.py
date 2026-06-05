from __future__ import annotations

import re
from pathlib import Path

from .constants import MIN_FUZZY_SCORE
from .file_state import FileState
from .tool_dataclasses import ClosestMatch, MatchOccurrence

def _find_occurrences(text: str, needle: str, scope: tuple[int, int]) -> list[MatchOccurrence]:
    matches: list[MatchOccurrence] = []
    scoped_text = text[scope[0] : scope[1]]
    search_index = 0
    while True:
        found = scoped_text.find(needle, search_index)
        if found == -1:
            return matches
        start_offset = scope[0] + found
        end_offset = start_offset + len(needle)
        matches.append(
            MatchOccurrence(
                start_offset=start_offset,
                end_offset=end_offset,
                start_line=_offset_to_line(text, start_offset),
                end_line=_offset_to_line(text, max(start_offset, end_offset - 1)),
            )
        )
        search_index = found + len(needle)


def _offset_to_line(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, min(offset, len(text))) + 1


def _build_candidate_preview(text: str, start_line: int, end_line: int) -> str:
    lines = text.splitlines()
    selected = lines[start_line - 1 : end_line]
    return "\n".join(
        f"{str(start_line + index).rjust(6)}\t{line}" for index, line in enumerate(selected)
    )


def _build_closest_match_metadata(
    file_state: FileState,
    path: Path,
    closest_match: ClosestMatch,
) -> dict[str, object]:
    preview = _build_candidate_preview(text=closest_match.text, start_line=1, end_line=10)
    if preview:
        preview = _renumber_preview(preview, closest_match.start_line)
    snippet = file_state.create_snippet(
        path,
        start_line=closest_match.start_line,
        end_line=closest_match.end_line,
        text=preview,
    )
    return {
        "snippet_id": snippet.id,
        "start_line": closest_match.start_line,
        "end_line": closest_match.end_line,
        "similarity": round(closest_match.score, 3),
        "strategy": closest_match.strategy,
        "preview": preview,
    }


def _renumber_preview(preview: str, start_line: int) -> str:
    lines = [line.split("\t", 1)[1] if "\t" in line else line for line in preview.splitlines()]
    return "\n".join(
        f"{str(start_line + index).rjust(6)}\t{line}" for index, line in enumerate(lines)
    )


def _find_loose_escape_occurrences(
    text: str,
    needle: str,
    scope: tuple[int, int],
) -> list[tuple[MatchOccurrence, float, str]]:
    pattern = _build_loose_escape_pattern(needle)
    if pattern is None:
        return []
    scoped_text = text[scope[0] : scope[1]]
    normalized_needle = _normalize_loose_text(needle)
    matches = []
    for regex_match in pattern.finditer(scoped_text):
        start_offset = scope[0] + regex_match.start()
        end_offset = scope[0] + regex_match.end()
        matched_text = regex_match.group(0)
        matches.append(
            (
                MatchOccurrence(
                    start_offset=start_offset,
                    end_offset=end_offset,
                    start_line=_offset_to_line(text, start_offset),
                    end_line=_offset_to_line(text, max(start_offset, end_offset - 1)),
                ),
                _similarity_score(normalized_needle, _normalize_loose_text(matched_text)),
                matched_text,
            )
        )
    return matches


def _build_loose_escape_pattern(source: str) -> re.Pattern[str] | None:
    if not source:
        return None
    pattern = []
    index = 0
    while index < len(source):
        if source[index] == "\\":
            slash_end = index
            while slash_end < len(source) and source[slash_end] == "\\":
                slash_end += 1
            if slash_end < len(source) and source[slash_end] in "\"'`\\":
                pattern.append(r"\\*")
                pattern.append(re.escape(source[slash_end]))
                index = slash_end + 1
                continue
            pattern.append(re.escape(source[index:slash_end]))
            index = slash_end
            continue
        pattern.append(re.escape(source[index]))
        index += 1
    return re.compile("".join(pattern))


def _find_closest_match(
    text: str,
    needle: str,
    scope: tuple[int, int],
) -> ClosestMatch | None:
    loose_matches = _find_loose_escape_occurrences(text, needle, scope)
    best_loose: ClosestMatch | None = None
    for occurrence, score, matched_text in loose_matches:
        candidate = ClosestMatch(
            text=matched_text,
            start_line=occurrence.start_line,
            end_line=occurrence.end_line,
            score=score,
            strategy="loose_escape",
        )
        if best_loose is None or candidate.score > best_loose.score:
            best_loose = candidate
    if best_loose is not None:
        return best_loose

    normalized_target = _normalize_loose_text(needle)
    target_line_count = max(1, len(needle.splitlines()) or 1)
    window_sizes = sorted({max(1, target_line_count - 1), target_line_count, target_line_count + 1})
    start_line = _offset_to_line(text, scope[0])
    end_line = _offset_to_line(text, max(scope[0], scope[1] - 1))
    best_match: ClosestMatch | None = None
    for line in range(start_line, end_line + 1):
        for window_size in window_sizes:
            candidate_end = line + window_size - 1
            if candidate_end > end_line:
                continue
            candidate_text = _slice_lines(text, line, candidate_end)
            score = _similarity_score(normalized_target, _normalize_loose_text(candidate_text))
            if score < MIN_FUZZY_SCORE:
                continue
            candidate = ClosestMatch(
                text=candidate_text,
                start_line=line,
                end_line=candidate_end,
                score=score,
                strategy="fuzzy_window",
            )
            if best_match is None or candidate.score > best_match.score:
                best_match = candidate
    return best_match


def _slice_lines(text: str, start_line: int, end_line: int) -> str:
    lines = text.splitlines(keepends=True)
    return "".join(lines[start_line - 1 : end_line])


def _normalize_loose_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\\+(?=[\"'`\\])", "", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()


def _similarity_score(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    left_bigrams = _to_bigrams(left)
    right_bigrams = _to_bigrams(right)
    if not left_bigrams or not right_bigrams:
        return 1.0 if left == right else 0.0
    right_counts: dict[str, int] = {}
    for bigram in right_bigrams:
        right_counts[bigram] = right_counts.get(bigram, 0) + 1
    overlap = 0
    for bigram in left_bigrams:
        count = right_counts.get(bigram, 0)
        if count > 0:
            overlap += 1
            right_counts[bigram] = count - 1
    return (2 * overlap) / (len(left_bigrams) + len(right_bigrams))


def _to_bigrams(value: str) -> list[str]:
    if len(value) < 2:
        return [value]
    return [value[index : index + 2] for index in range(len(value) - 1)]
