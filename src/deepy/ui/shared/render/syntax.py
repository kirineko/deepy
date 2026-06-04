from __future__ import annotations

from pathlib import PurePosixPath

from rich.style import Style
from rich.syntax import Syntax


XML_LANGUAGE_ALIASES = {
    "xml",
    "svg",
    "xaml",
    "csproj",
    "vbproj",
    "fsproj",
    "props",
    "targets",
    "xsd",
    "xsl",
    "xslt",
}
XML_EXTENSIONS = {
    ".xml",
    ".svg",
    ".xaml",
    ".csproj",
    ".vbproj",
    ".fsproj",
    ".props",
    ".targets",
    ".xsd",
    ".xsl",
    ".xslt",
}
XML_CONFIG_FILES = {
    "app.config",
    "web.config",
    "packages.config",
}


def normalize_syntax_lexer(
    *,
    language: str | None = None,
    path: str | None = None,
    sample: str = "",
) -> str | None:
    language = _clean_language(language)
    if language in XML_LANGUAGE_ALIASES:
        return "xml"
    if path and _is_xml_path(path):
        return "xml"
    if language:
        return language
    if not path or not sample.strip():
        return None
    try:
        lexer = Syntax.guess_lexer(path, sample)
    except Exception:
        return None
    return lexer if lexer and lexer != "default" else None


def syntax_style_on_background(style: str | Style, base: Style) -> Style:
    syntax_style = Style.parse(style) if isinstance(style, str) else style
    return Style(
        color=syntax_style.color or base.color,
        bgcolor=base.bgcolor,
        bold=syntax_style.bold,
        italic=syntax_style.italic,
        underline=syntax_style.underline,
        dim=syntax_style.dim,
        strike=syntax_style.strike,
    )


def _clean_language(language: str | None) -> str:
    if not language:
        return ""
    return language.strip().lower()


def _is_xml_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    name = PurePosixPath(normalized).name.lower()
    if name in XML_CONFIG_FILES:
        return True
    return PurePosixPath(name).suffix.lower() in XML_EXTENSIONS
