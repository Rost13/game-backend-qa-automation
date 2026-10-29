from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from qa_automation.oracles import (
    assert_only_expected_ids_added,
    market_purchase_debit_minor_units,
    reward_expiration_window,
)


def test_market_purchase_debit_uses_matching_catalog_price() -> None:
    assert market_purchase_debit_minor_units(Decimal("10.25"), Decimal("10.25"), 100) == 1025


def test_market_purchase_debit_rejects_reported_price_different_from_catalog() -> None:
    with pytest.raises(AssertionError, match="catalog price"):
        market_purchase_debit_minor_units(Decimal("10.00"), Decimal("20.00"), 100)


def test_market_purchase_debit_rejects_subminor_catalog_precision() -> None:
    with pytest.raises(AssertionError, match="precision"):
        market_purchase_debit_minor_units(Decimal("10.005"), Decimal("10.005"), 100)


def test_opening_delta_accepts_exact_expected_ids() -> None:
    existing = UUID("550e8400-e29b-41d4-a716-446655440000")
    opened = UUID("6e590c2f-2237-488f-b0b3-22cf08f00000")

    assert_only_expected_ids_added({existing}, {existing, opened}, {opened})


def test_opening_delta_rejects_unexpected_or_missing_ids() -> None:
    existing = UUID("550e8400-e29b-41d4-a716-446655440000")
    expected = UUID("6e590c2f-2237-488f-b0b3-22cf08f00000")
    unexpected = UUID("723ac438-ae1f-4ed5-86ad-d285ce3d0000")

    with pytest.raises(AssertionError, match="unexpected opening IDs"):
        assert_only_expected_ids_added(
            {existing},
            {existing, expected, unexpected},
            {expected},
        )
    with pytest.raises(AssertionError, match="missing opening IDs"):
        assert_only_expected_ids_added({existing}, {existing}, {expected})


def test_expired_reward_expiration_uses_observation_time_with_tolerance() -> None:
    observed_at = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
    duration = timedelta(days=1)
    tolerance = timedelta(seconds=2)

    lower, upper = reward_expiration_window(
        observed_at - timedelta(hours=1),
        observed_at,
        duration,
        tolerance,
    )

    assert lower == datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
    assert upper == datetime(2026, 10, 30, 12, 0, 2, tzinfo=UTC)


def test_active_reward_expiration_extends_existing_expiration_exactly() -> None:
    observed_at = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
    previous = observed_at + timedelta(hours=1)
    duration = timedelta(days=1)

    lower, upper = reward_expiration_window(
        previous,
        observed_at,
        duration,
        timedelta(seconds=2),
    )

    expected = datetime(2026, 10, 30, 13, 0, tzinfo=UTC)
    assert (lower, upper) == (expected, expected)


def test_reward_expiration_boundary_allows_entitlement_to_expire_during_request() -> None:
    observed_at = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
    previous = observed_at + timedelta(seconds=1)
    duration = timedelta(hours=1)

    lower, upper = reward_expiration_window(
        previous,
        observed_at,
        duration,
        timedelta(seconds=2),
    )

    assert lower == datetime(2026, 10, 29, 13, 0, 1, tzinfo=UTC)
    assert upper == datetime(2026, 10, 29, 13, 0, 2, tzinfo=UTC)
