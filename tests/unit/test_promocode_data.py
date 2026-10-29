from __future__ import annotations

import pytest

from qa_automation.test_data.promocodes import campaign_payload, unique_promo_code


def test_unique_promo_code_is_twelve_safe_characters() -> None:
    code = unique_promo_code("AT")

    assert len(code) == 12
    assert code.startswith("AT")
    assert code.isascii()
    assert code.isalnum()
    assert code == code.upper()


def test_unique_promo_code_rejects_unsafe_prefix() -> None:
    with pytest.raises(ValueError, match="ASCII"):
        unique_promo_code("BAD-")


def test_campaign_payload_has_an_active_time_window() -> None:
    payload = campaign_payload(prefix="AT", reward_amount=1, max_claims=5)

    assert payload["type"] == "CAMPAIGN"
    assert payload["is_active"] is True
    assert payload["reward_currency"] == "SFT"
    start_at_ms = payload["start_at_ms"]
    expire_at_ms = payload["expire_at_ms"]
    assert isinstance(start_at_ms, int)
    assert isinstance(expire_at_ms, int)
    assert start_at_ms < expire_at_ms


def test_campaign_payload_accepts_pxg_reward_currency() -> None:
    payload = campaign_payload(
        prefix="AT",
        reward_amount=1,
        max_claims=5,
        reward_currency="PXG",
    )

    assert payload["reward_currency"] == "PXG"
