from __future__ import annotations

import urllib.parse
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from deepy.config import Settings


def should_track_session_cost(settings: Settings) -> bool:
    if not settings.model.api_key:
        return False
    parsed = urllib.parse.urlparse(settings.model.base_url)
    return parsed.scheme in {"http", "https"} and parsed.hostname == "api.deepseek.com"


def balance_snapshot_to_dict(balance: Any, *, captured_at_ms: int) -> dict[str, Any]:
    unavailable_reason = _string_or_none(_field(balance, "unavailable_reason"))
    if unavailable_reason:
        return {
            "capturedAt": captured_at_ms,
            "unavailableReason": unavailable_reason,
        }

    infos: list[dict[str, str]] = []
    for item in _field(balance, "balance_infos") or ():
        currency = _string_or_none(_field(item, "currency"))
        total = _string_or_none(_field(item, "total_balance"))
        granted = _string_or_none(_field(item, "granted_balance"))
        topped_up = _string_or_none(_field(item, "topped_up_balance"))
        if None in (currency, total, granted, topped_up):
            return {
                "capturedAt": captured_at_ms,
                "unavailableReason": "invalid balance snapshot",
            }
        infos.append(
            {
                "currency": currency or "",
                "totalBalance": total or "",
                "grantedBalance": granted or "",
                "toppedUpBalance": topped_up or "",
            }
        )
    is_available = _field(balance, "is_available")
    return {
        "capturedAt": captured_at_ms,
        "isAvailable": is_available if isinstance(is_available, bool) else None,
        "balanceInfos": infos,
    }


def start_session_cost(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    cost: dict[str, Any] = {
        "attempted": True,
        "start": dict(snapshot),
    }
    if reason := _snapshot_unavailable_reason(snapshot):
        cost["unavailableReason"] = f"start {reason}"
    return cost


def complete_session_cost(
    existing: Mapping[str, Any] | None,
    end_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    cost: dict[str, Any] = dict(existing or {})
    cost["attempted"] = True
    cost["end"] = dict(end_snapshot)
    start = cost.get("start")
    if not isinstance(start, Mapping):
        cost["amounts"] = []
        cost["unavailableReason"] = "start snapshot missing"
        return cost
    amounts, reason = compute_session_cost_amounts(start, end_snapshot)
    cost["amounts"] = amounts
    if reason:
        cost["unavailableReason"] = reason
    else:
        cost.pop("unavailableReason", None)
    return cost


def compute_session_cost_amounts(
    start_snapshot: Mapping[str, Any],
    end_snapshot: Mapping[str, Any],
) -> tuple[list[dict[str, str]], str | None]:
    if reason := _snapshot_unavailable_reason(start_snapshot):
        return [], f"start {reason}"
    if reason := _snapshot_unavailable_reason(end_snapshot):
        return [], f"end {reason}"

    start_infos = _snapshot_infos_by_currency(start_snapshot)
    end_infos = _snapshot_infos_by_currency(end_snapshot)
    if start_infos is None or end_infos is None:
        return [], "invalid balance snapshot"
    shared = [currency for currency in start_infos if currency in end_infos]
    if not shared:
        return [], "currency mismatch"

    amounts: list[dict[str, str]] = []
    for currency in shared:
        start_total_text = start_infos[currency]
        end_total_text = end_infos[currency]
        start_total = _decimal(start_total_text)
        end_total = _decimal(end_total_text)
        if start_total is None or end_total is None:
            return [], "invalid balance amount"
        spent = start_total - end_total
        if spent > 0:
            amounts.append(
                {
                    "currency": currency,
                    "startTotal": start_total_text,
                    "endTotal": end_total_text,
                    "spent": _format_decimal(spent),
                }
            )
    if not amounts:
        return [], "no measurable spend"
    return amounts, None


def format_session_cost(cost: Any) -> str | None:
    if not isinstance(cost, Mapping) or not cost.get("attempted"):
        return None
    amounts = cost.get("amounts")
    if isinstance(amounts, list) and amounts:
        parts: list[str] = []
        for item in amounts:
            if not isinstance(item, Mapping):
                continue
            currency = _string_or_none(item.get("currency"))
            spent = _string_or_none(item.get("spent"))
            if currency and spent:
                parts.append(f"{currency} {spent}")
        if parts:
            return f"{', '.join(parts)} (DeepSeek balance delta)"
    reason = _string_or_none(cost.get("unavailableReason")) or "unknown"
    return f"unavailable ({reason})"


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _snapshot_unavailable_reason(snapshot: Mapping[str, Any]) -> str | None:
    return _string_or_none(snapshot.get("unavailableReason"))


def _snapshot_infos_by_currency(snapshot: Mapping[str, Any]) -> dict[str, str] | None:
    raw_infos = snapshot.get("balanceInfos")
    if not isinstance(raw_infos, list):
        return None
    infos: dict[str, str] = {}
    for item in raw_infos:
        if not isinstance(item, Mapping):
            return None
        currency = _string_or_none(item.get("currency"))
        total = _string_or_none(item.get("totalBalance"))
        if not currency or total is None:
            return None
        infos[currency] = total
    return infos


def _decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." not in text:
        return text
    return text.rstrip("0").rstrip(".") or "0"
