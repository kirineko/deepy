from __future__ import annotations

DEFAULT_LINE_LIMIT = 2_000
MAX_LINE_LENGTH = 2_000
MAX_BASH_OUTPUT_CHARS = 30_000
MAX_BASH_CAPTURE_CHARS = 10 * 1024 * 1024
MAX_WEB_FETCH_BYTES = 2 * 1024 * 1024
MAX_WEB_FETCH_OUTPUT_CHARS = 30_000
MIN_USEFUL_WEB_FETCH_BODY_CHARS = 40
DEFAULT_WEB_SEARCH_URL = "https://html.duckduckgo.com/html/"
DEFAULT_WEB_SEARCH_RESULTS = 8
MAX_WEB_SEARCH_CALLS_PER_TURN = 8
WEB_SEARCH_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
}
PDF_LARGE_PAGE_THRESHOLD = 10
PDF_MAX_PAGE_RANGE = 20
MAX_CANDIDATE_COUNT = 5
MIN_FUZZY_SCORE = 0.45
ATOMIC_RENAME_RETRIES = 5
ATOMIC_RENAME_BACKOFF_SECONDS = 0.02
IGNORED_DIRECTORY_ENTRIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "wheels",
}
UNSUPPORTED_TEXT_MUTATION_SUFFIXES = {
    ".7z",
    ".avif",
    ".db",
    ".gif",
    ".gz",
    ".ico",
    ".ipynb",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp4",
    ".pdf",
    ".png",
    ".sqlite",
    ".tar",
    ".webp",
    ".zip",
}
SENSITIVE_MUTATION_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".netrc",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}
