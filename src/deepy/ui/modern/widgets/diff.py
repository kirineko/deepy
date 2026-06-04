"""Unified-diff transcript block for the Modern UI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Label, Static

from deepy.ui.modern.render.diff import TuiDiffView, render_unified_diff_rich, render_unified_diff_text
from deepy.ui.modern.render.transcript import transcript_display


class DiffBlock(Vertical, can_focus=True):
    BINDINGS = [
        Binding("n", "next_hunk", "Next hunk", show=False),
        Binding("p", "previous_hunk", "Previous hunk", show=False),
        Binding("f", "toggle_hunk_fold", "Fold hunk", show=False),
    ]

    def __init__(self, diff: TuiDiffView, *, theme: str = "dark", width: int | None = None) -> None:
        self.display_model = transcript_display("diff")
        super().__init__(classes="transcript-block diff-block")
        self.diff = diff
        self.body = render_unified_diff_text(diff)
        self.renderable = render_unified_diff_rich(diff, theme=theme, width=width)
        self.current_hunk = 0
        self.folded = False

    def compose(self) -> ComposeResult:
        title = Label(self.display_model.label, classes="block-title")
        title.display = False
        yield title
        yield Static(self.renderable, classes="block-body")

    def action_next_hunk(self) -> None:
        if not self.diff.hunks:
            return
        self.current_hunk = min(len(self.diff.hunks) - 1, self.current_hunk + 1)
        self._update_hunk_status()

    def action_previous_hunk(self) -> None:
        if not self.diff.hunks:
            return
        self.current_hunk = max(0, self.current_hunk - 1)
        self._update_hunk_status()

    def action_toggle_hunk_fold(self) -> None:
        self.folded = not self.folded
        body = self.query_one(".block-body", Static)
        if self.folded:
            body.update(f"{self.diff.path or 'file'} (+{self.diff.added} -{self.diff.removed})\n... hunk folded ...")
        else:
            body.update(self.renderable)
        self._update_hunk_status()

    def _update_hunk_status(self) -> None:
        title = "Diff"
        if self.diff.hunks:
            title = f"Diff hunk {self.current_hunk + 1}/{len(self.diff.hunks)}"
            if self.folded:
                title += " folded"
        self.query_one(".block-title", Label).update(title)
