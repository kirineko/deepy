from __future__ import annotations

import urllib.error

from deepy.config.settings import ModelConfig, Settings
from deepy.status import (
    BalanceStatus,
    build_status_report,
    fetch_deepseek_balance,
    format_balance_status,
    format_compact_status_report,
    format_status_report,
    parse_balance_payload,
    status_report_to_dict,
)


def test_status_report_includes_counts_and_context(tmp_path):
    skill_dir = tmp_path / ".agents" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo\n---\n",
        encoding="utf-8",
    )
    settings = Settings(model=ModelConfig(api_key="sk-test"))

    report = build_status_report(tmp_path, settings)
    rendered = format_status_report(report)

    assert report.skill_count >= 3
    assert "API key: configured" in rendered
    assert "Provider: deepseek" in rendered
    assert "Thinking: max" in rendered
    assert "Reserved context: 50000 tokens" in rendered
    assert "Input suggestions: enabled" in rendered
    assert f"Project: {tmp_path}" in rendered
    assert "Git dirty:" in rendered


def test_status_report_to_dict_is_json_ready(tmp_path):
    report = build_status_report(tmp_path, Settings())

    payload = status_report_to_dict(report)

    assert payload["project_root"] == str(tmp_path)
    assert payload["provider"] == "deepseek"
    assert payload["model"] == "deepseek-v4-pro"
    assert payload["reasoning_mode"] == "max"
    assert payload["reserved_context_tokens"] == 50000
    assert payload["input_suggestions_enabled"] is True


def test_status_report_includes_usage_context_and_balance(tmp_path):
    from deepy.sessions import DeepyJsonlSession

    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
    session.record_usage({"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120})

    report = build_status_report(
        tmp_path,
        Settings(model=ModelConfig(api_key="sk-test")),
        current_session_id="s1",
        balance=BalanceStatus(is_available=True),
    )
    rendered = format_compact_status_report(report)

    assert report.active_session_usage is not None
    assert report.project_usage is not None
    assert report.latest_context_window_tokens == 120
    assert "Deepy Status" in rendered
    assert "balance" in rendered
    assert "available" in rendered
    assert "session usage" in rendered
    assert "project usage" in rendered


def test_parse_balance_payload_accepts_cny_and_usd():
    balance = parse_balance_payload(
        {
            "is_available": True,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "110.00",
                    "granted_balance": "10.00",
                    "topped_up_balance": "100.00",
                },
                {
                    "currency": "USD",
                    "total_balance": "2.50",
                    "granted_balance": "0.50",
                    "topped_up_balance": "2.00",
                },
            ],
        }
    )

    assert balance.known
    assert balance.is_available is True
    assert [info.currency for info in balance.balance_infos] == ["CNY", "USD"]
    assert "CNY 110.00" in format_balance_status(balance)
    assert "USD 2.50" in format_balance_status(balance)


def test_parse_balance_payload_rejects_bad_shape():
    balance = parse_balance_payload({"is_available": True, "balance_infos": [{}]})

    assert balance.unavailable_reason == "invalid response"


def test_fetch_deepseek_balance_uses_official_host_and_masks_key():
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return (
                b'{"is_available":true,"balance_infos":[{"currency":"CNY",'
                b'"total_balance":"1.00","granted_balance":"0.00",'
                b'"topped_up_balance":"1.00"}]}'
            )

    def fake_urlopen(request, *, timeout):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return FakeResponse()

    balance = fetch_deepseek_balance(
        Settings(model=ModelConfig(api_key="sk-secret")),
        urlopen=fake_urlopen,
        timeout=1.5,
    )

    assert balance.known
    assert captured == {
        "url": "https://api.deepseek.com/user/balance",
        "auth": "Bearer sk-secret",
        "timeout": 1.5,
    }
    assert "sk-secret" not in format_balance_status(balance)


def test_fetch_deepseek_balance_unavailable_paths():
    assert fetch_deepseek_balance(Settings()).unavailable_reason == "api key missing"
    assert (
        fetch_deepseek_balance(
            Settings(model=ModelConfig(api_key="sk-test", base_url="https://example.com"))
        ).unavailable_reason
        == "unsupported api host"
    )

    def http_error(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://api.deepseek.com/user/balance",
            401,
            "Unauthorized",
            {},
            None,
        )

    assert (
        fetch_deepseek_balance(
            Settings(model=ModelConfig(api_key="sk-test")),
            urlopen=http_error,
        ).unavailable_reason
        == "http 401"
    )

    def invalid_response(*args, **kwargs):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self):
                return b"not-json"

        return FakeResponse()

    assert (
        fetch_deepseek_balance(
            Settings(model=ModelConfig(api_key="sk-test")),
            urlopen=invalid_response,
        ).unavailable_reason
        == "invalid response"
    )
