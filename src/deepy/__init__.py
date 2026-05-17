from __future__ import annotations

__version__ = "0.2.3"


def main() -> None:
    from .cli import main as cli_main

    cli_main()
