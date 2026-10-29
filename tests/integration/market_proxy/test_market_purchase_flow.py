from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

import allure
import httpx
import pytest

from qa_automation.clients.balance import BalanceClient
from qa_automation.clients.base import (
    assert_response_status,
    attach_response_diagnostics,
    sanitize_diagnostic_text,
    validate_error_response,
    validate_success_data,
)
from qa_automation.clients.market_proxy import MarketProxyClient
from qa_automation.config import Settings
from qa_automation.models.balance import PXG_MINOR_UNITS, BalanceResponse, ReplenishResponse
from qa_automation.models.market_proxy import CatalogItem, CatalogResponse, PurchaseResponse
from qa_automation.oracles import market_purchase_debit_minor_units

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.regression,
    pytest.mark.serial,
    allure.feature("Market Proxy purchase flow"),
]

_TERMINAL_PURCHASE_STATUSES = {"cancelled", "completed", "delivery_failed", "refunded"}


@allure.title("Available product can be purchased exactly once with an idempotency key")
def test_user_can_purchase_available_product_idempotently(
    market_proxy_user_client: MarketProxyClient,
    market_proxy_purchase_settings: Settings,
    balance_admin_client: BalanceClient,
    balance_test_user_uuid: UUID,
    balance_mutation_settings: Settings,
) -> None:
    catalog_response = market_proxy_user_client.get_catalog()
    assert_response_status(catalog_response, 200)
    catalog = validate_success_data(catalog_response, CatalogResponse)
    product = _cheapest_available_product(catalog)
    catalog_price_minor = _pxg_minor_units(product.pxg_amount)

    _ensure_hard_balance(
        balance_client=balance_admin_client,
        account_uuid=balance_test_user_uuid,
        required_minor_units=catalog_price_minor,
        settings=balance_mutation_settings,
    )
    purchase_start_balance = _get_hard_balance(
        balance_admin_client,
        balance_test_user_uuid,
    )
    idempotency_key = f"qa-market-purchase-{uuid4()}"

    purchase_response = market_proxy_user_client.create_purchase(
        product.product_id,
        idempotency_key=idempotency_key,
    )

    if purchase_response.status_code == 400:
        error = validate_error_response(purchase_response)
        refreshed_response = market_proxy_user_client.get_catalog()
        assert_response_status(refreshed_response, 200)
        refreshed = validate_success_data(refreshed_response, CatalogResponse)
        still_available = any(
            item.product_id == product.product_id and item.available for item in refreshed.items
        )
        classification = "PRODUCT_DEFECT" if still_available else "TEST_DATA_DEFECT"
        pytest.fail(
            f"{classification}: advertised available product was rejected: "
            f"{sanitize_diagnostic_text(error.error_description)}",
            pytrace=False,
        )
    _assert_status_in(purchase_response, {200, 202})
    purchase = validate_success_data(purchase_response, PurchaseResponse)
    assert purchase.purchase_id is not None
    assert purchase.product_id == product.product_id
    UUID(purchase.purchase_id)
    if purchase.def_uuid is not None:
        UUID(purchase.def_uuid)

    replay_response = market_proxy_user_client.create_purchase(
        product.product_id,
        idempotency_key=idempotency_key,
    )
    _assert_status_in(replay_response, {200, 202})
    replay = validate_success_data(replay_response, PurchaseResponse)
    assert replay.purchase_id == purchase.purchase_id

    completed = _wait_for_terminal_purchase(
        client=market_proxy_user_client,
        purchase_id=purchase.purchase_id,
        timeout_seconds=market_proxy_purchase_settings.market_proxy_purchase_timeout.total_seconds(),
    )
    if completed.status != "completed":
        pytest.fail(
            f"PRODUCT_DEFECT: purchase ended in {completed.status!r}; "
            f"reason={sanitize_diagnostic_text(completed.failure_reason or '')!r}, "
            f"error={sanitize_diagnostic_text(completed.last_error or '')!r}",
            pytrace=False,
        )
    if completed.market_status != "completed":
        pytest.fail(
            "PRODUCT_DEFECT: completed purchase has non-completed market status", pytrace=False
        )
    if completed.pxg_amount is None:
        pytest.fail("PRODUCT_DEFECT: completed purchase does not report PXG amount", pytrace=False)
    debit_minor_units = market_purchase_debit_minor_units(
        product.pxg_amount,
        completed.pxg_amount,
        PXG_MINOR_UNITS,
    )
    assert debit_minor_units <= purchase_start_balance

    final_balance = _wait_for_hard_balance(
        balance_client=balance_admin_client,
        account_uuid=balance_test_user_uuid,
        expected_minor_units=purchase_start_balance - debit_minor_units,
        timeout_seconds=market_proxy_purchase_settings.market_proxy_purchase_timeout.total_seconds(),
    )
    assert purchase_start_balance - final_balance == debit_minor_units


def _cheapest_available_product(catalog: CatalogResponse) -> CatalogItem:
    available = [item for item in catalog.items if item.available and item.pxg_amount > 0]
    assert available, "TEST_DATA_DEFECT: Market catalog has no available PXG products"
    return min(available, key=lambda item: item.pxg_amount)


def _ensure_hard_balance(
    *,
    balance_client: BalanceClient,
    account_uuid: UUID,
    required_minor_units: int,
    settings: Settings,
) -> None:
    current = _get_hard_balance(balance_client, account_uuid)
    if current >= required_minor_units:
        return

    missing_minor_units = required_minor_units - current
    replenish_amount = int(
        (Decimal(missing_minor_units) / PXG_MINOR_UNITS).to_integral_value(rounding=ROUND_CEILING)
    )
    response = balance_client.replenish({"uuid": str(account_uuid), "hard": replenish_amount})
    assert_response_status(response, 200)
    validate_success_data(response, ReplenishResponse)
    _wait_for_hard_balance(
        balance_client=balance_client,
        account_uuid=account_uuid,
        expected_minor_units=current + replenish_amount * PXG_MINOR_UNITS,
        timeout_seconds=settings.balance_event_timeout.total_seconds(),
    )


def _wait_for_terminal_purchase(
    *,
    client: MarketProxyClient,
    purchase_id: str,
    timeout_seconds: float,
) -> PurchaseResponse:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    last_status: str | None = None

    while True:
        response = client.get_purchase(purchase_id)
        assert_response_status(response, 200)
        purchase = validate_success_data(response, PurchaseResponse)
        last_status = purchase.status
        if last_status in _TERMINAL_PURCHASE_STATUSES:
            return purchase

        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: purchase {purchase_id} did not reach a terminal state within "
                f"{timeout_seconds:g}s; last status {last_status!r}",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.5, remaining))


def _wait_for_hard_balance(
    *,
    balance_client: BalanceClient,
    account_uuid: UUID,
    expected_minor_units: int,
    timeout_seconds: float,
) -> int:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    last_value: int | None = None

    while True:
        last_value = _get_hard_balance(balance_client, account_uuid)
        if last_value == expected_minor_units:
            return last_value

        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: hard balance did not become {expected_minor_units} within "
                f"{timeout_seconds:g}s; last value {last_value}",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.25, remaining))


def _get_hard_balance(balance_client: BalanceClient, account_uuid: UUID) -> int:
    response = balance_client.get_balance_by_uuid(account_uuid)
    assert_response_status(response, 200)
    balance = validate_success_data(response, BalanceResponse)
    return balance.hard or 0


def _pxg_minor_units(pxg_amount: Decimal) -> int:
    minor_units = pxg_amount * PXG_MINOR_UNITS
    assert minor_units == minor_units.to_integral_value(), (
        f"PRODUCT_DEFECT: PXG amount {pxg_amount} has more than two decimal places"
    )
    return int(minor_units)


def _assert_status_in(response: httpx.Response, expected_statuses: set[int]) -> None:
    if response.status_code not in expected_statuses:
        attach_response_diagnostics(response)
    assert response.status_code in expected_statuses, (
        f"expected HTTP status in {sorted(expected_statuses)}, got {response.status_code}"
    )
