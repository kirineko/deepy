from __future__ import annotations

import ast
from pathlib import Path


def test_production_json_paths_go_through_json_utils():
    src_root = Path(__file__).resolve().parents[1] / "src" / "deepy"
    offenders: list[str] = []
    for path in src_root.rglob("*.py"):
        if path.relative_to(src_root).as_posix() == "utils/json.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _uses_stdlib_json_directly(tree):
            offenders.append(path.relative_to(src_root).as_posix())

    assert offenders == []


def test_token_estimation_uses_tiktoken_when_available():
    import deepy.llm.context as context

    encoding = context._token_encoding()
    if encoding is None:
        assert context.estimate_tokens_for_text("hello") == 2
    else:
        assert context.estimate_tokens_for_text("hello") == len(encoding.encode("hello"))


def _uses_stdlib_json_directly(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "json" for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom) and node.module == "json":
            return True
        if (
            isinstance(node, ast.Attribute)
            and node.attr in {"loads", "dumps"}
            and isinstance(node.value, ast.Name)
            and node.value.id == "json"
        ):
            return True
    return False
