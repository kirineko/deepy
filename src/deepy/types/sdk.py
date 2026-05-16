from __future__ import annotations

from collections.abc import Callable

from agents.items import TResponseInputItem


SessionInputCallback = Callable[
    [list[TResponseInputItem], list[TResponseInputItem]],
    list[TResponseInputItem],
]

