"""Result type for the Modern UI config-reset flow."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResetConfigResult:
    api_key: str
    provider: str
    model: str
    base_url: str
    thinking: str
    interface: str
    theme: str
