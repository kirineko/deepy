"""Persisted provider profiles and ephemeral credential resolution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .providers import DEFAULT_PROVIDER, PROVIDERS, provider_info_for

KEY_ENVIRONMENTS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "mimo": "MIMO_API_KEY",
    "kimi": "KIMI_API_KEY",
    "cli_proxy": "CLI_PROXY_API_KEY",
}


def resolve_profile_key(
    provider: str, profile: Mapping[str, Any], env: Mapping[str, str]
) -> str | None:
    reference = profile.get("api_key_env") or KEY_ENVIRONMENTS[provider]
    value = env.get(str(reference), "").strip()
    if not value and provider == "kimi" and reference == "KIMI_API_KEY":
        value = env.get("MOONSHOT_API_KEY", "").strip()
    saved = profile.get("api_key")
    return value or (saved.strip() if isinstance(saved, str) else None) or None


def parse_profiles(raw: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], str]:
    if "model" in raw or raw.get("config_version", 2) != 2:
        raise ValueError(
            "This configuration needs provider profiles (config_version = 2). "
            "Keep a copy of the old file, then run `deepy config setup` to reconfigure."
        )
    active = raw.get("active_provider", DEFAULT_PROVIDER)
    if not isinstance(active, str):
        raise ValueError("active_provider must be a provider ID.")
    provider_info_for(active)
    profiles = raw.get("providers", {})
    if not isinstance(profiles, Mapping):
        raise ValueError("providers must contain provider profile tables.")
    result: dict[str, dict[str, Any]] = {}
    for name, profile in profiles.items():
        if name not in PROVIDERS or not isinstance(profile, Mapping):
            raise ValueError(f"Unsupported provider profile: {name}.")
        result[name] = dict(profile)
    return result, active
