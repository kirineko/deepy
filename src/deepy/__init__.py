from __future__ import annotations

__version__ = "0.1.5"


def main() -> None:
    from .cli import main as cli_main

    cli_main()
