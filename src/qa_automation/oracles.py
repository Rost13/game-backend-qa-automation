from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID


def market_purchase_debit_minor_units(
    catalog_price: Decimal,
    reported_price: Decimal,
    minor_units_per_unit: int,
) -> int:
    """Return the independently advertised debit after validating the purchase report."""

    assert reported_price == catalog_price, (
        "PRODUCT_DEFECT: completed purchase price differs from catalog price"
    )
    minor_units = catalog_price * minor_units_per_unit
    assert minor_units == minor_units.to_integral_value(), (
        "PRODUCT_DEFECT: catalog price has invalid minor-unit precision"
    )
    return int(minor_units)


def assert_only_expected_ids_added(
    before: set[UUID],
    after: set[UUID],
    expected: set[UUID],
) -> None:
    """Require an exact set of newly persisted Lottery opening IDs."""

    added = after - before
    unexpected = added - expected
    missing = expected - added
    assert not unexpected, (
        f"PRODUCT_DEFECT: Lottery persisted unexpected opening IDs (count={len(unexpected)})"
    )
    assert not missing, f"PRODUCT_DEFECT: Lottery is missing opening IDs (count={len(missing)})"


def reward_expiration_window(
    previous: datetime | None,
    observed_at: datetime,
    duration: timedelta,
    tolerance: timedelta,
) -> tuple[datetime, datetime]:
    """Return the valid delivery window for an entitlement extension."""

    if duration <= timedelta(0):
        raise ValueError("reward duration must be positive")
    if tolerance < timedelta(0):
        raise ValueError("reward tolerance must not be negative")
    lower_base = max(previous, observed_at) if previous is not None else observed_at
    upper_observation = observed_at + tolerance
    upper_base = max(previous, upper_observation) if previous is not None else upper_observation
    return lower_base + duration, upper_base + duration
