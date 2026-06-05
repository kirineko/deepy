from __future__ import annotations

import pytest

from deepy.config import Settings
from deepy.ui.modern.app import DeepyTuiApp

from tui_harness import _idle_run_once


@pytest.fixture
def make_tui_app(tmp_path):
    def _make(run_once=_idle_run_once, settings=None, **kwargs):
        return DeepyTuiApp(
            settings=settings or Settings(),
            project_root=tmp_path,
            run_once=run_once,
            **kwargs,
        )

    return _make
