from __future__ import annotations

from deepy.config.settings import ModelConfig, Settings
from deepy.session_cost import (
    balance_snapshot_to_dict,
    compute_session_cost_amounts,
    format_session_cost,
    should_track_session_cost,
    supports_session_cost,
    start_session_cost,
    complete_session_cost,
)
from deepy.status import BalanceInfo, BalanceStatus


def _snapshot(total: str, *, currency: str = "CNY") -> dict[str, object]:
    return {
        "capturedAt": 1,
        "isAvailable": True,
        "balanceInfos": [
            {
                "currency": currency,
                "totalBalance": total,
                "grantedBalance": "0.00",
                "toppedUpBalance": total,
            }
        ],
    }


def test_should_track_session_cost_requires_official_deepseek_key():
    assert not should_track_session_cost(Settings())
    assert not should_track_session_cost(
        Settings(model=ModelConfig(api_key="sk-test", base_url="https://example.com"))
    )
    assert not should_track_session_cost(
        Settings(
            model=ModelConfig(
                provider="openrouter",
                api_key="sk-test",
                base_url="https://api.deepseek.com",
            )
        )
    )
    assert should_track_session_cost(Settings(model=ModelConfig(api_key="sk-test")))


def test_supports_session_cost_is_deepseek_provider_only():
    assert supports_session_cost(Settings())
    assert not supports_session_cost(
        Settings(
            model=ModelConfig(
                provider="openrouter",
                name="xiaomi/mimo-v2.5-pro",
                base_url="https://openrouter.ai/api/v1",
            )
        )
    )


def test_balance_snapshot_to_dict_reuses_balance_parser_shape():
    snapshot = balance_snapshot_to_dict(
        BalanceStatus(
            is_available=True,
            balance_infos=(
                BalanceInfo(
                    currency="CNY",
                    total_balance="110.00",
                    granted_balance="10.00",
                    topped_up_balance="100.00",
                ),
            ),
        ),
        captured_at_ms=123,
    )

    assert snapshot["capturedAt"] == 123
    assert snapshot["balanceInfos"] == [
        {
            "currency": "CNY",
            "totalBalance": "110.00",
            "grantedBalance": "10.00",
            "toppedUpBalance": "100.00",
        }
    ]


def test_compute_session_cost_amounts_reports_positive_spend():
    amounts, reason = compute_session_cost_amounts(_snapshot("100.00"), _snapshot("99.75"))

    assert reason is None
    assert amounts == [
        {
            "currency": "CNY",
            "startTotal": "100.00",
            "endTotal": "99.75",
            "spent": "0.25",
        }
    ]


def test_compute_session_cost_amounts_handles_unreliable_deltas():
    assert compute_session_cost_amounts(_snapshot("100.00"), _snapshot("100.00")) == (
        [],
        "no measurable spend",
    )
    assert compute_session_cost_amounts(_snapshot("100.00"), _snapshot("101.00")) == (
        [],
        "no measurable spend",
    )
    assert compute_session_cost_amounts(
        _snapshot("100.00"), _snapshot("99.00", currency="USD")
    ) == (
        [],
        "currency mismatch",
    )
    assert compute_session_cost_amounts(_snapshot("bad"), _snapshot("99.00")) == (
        [],
        "invalid balance amount",
    )
    assert compute_session_cost_amounts(
        {"capturedAt": 1, "unavailableReason": "network error"},
        _snapshot("99.00"),
    ) == ([], "start network error")


def test_format_session_cost_displays_spend_or_unavailable_reason():
    cost = complete_session_cost(start_session_cost(_snapshot("10.00")), _snapshot("9.50"))

    assert format_session_cost(cost) == "CNY 0.5 (DeepSeek balance delta)"

    unavailable = complete_session_cost(
        start_session_cost(_snapshot("10.00")),
        {"capturedAt": 2, "unavailableReason": "timeout"},
    )

    assert format_session_cost(unavailable) == "unavailable (end timeout)"
