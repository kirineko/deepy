from __future__ import annotations

import pytest

from deepy.config import Settings
from deepy.tools import ToolRuntime


@pytest.fixture
def make_runtime(tmp_path):
    def _make(**kwargs):
        settings = kwargs.pop("settings", None) or Settings()
        return ToolRuntime(cwd=tmp_path, settings=settings, **kwargs)

    return _make
