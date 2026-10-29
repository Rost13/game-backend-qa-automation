from __future__ import annotations

from decimal import Decimal
from threading import Event
from time import monotonic
from typing import Literal
from uuid import UUID

import allure
import pytest
from fixtures.promocodes import PromoFactory

from qa_automation.clients.balance import BalanceClient
from qa_automation.clients.base import assert_response_status, validate_success_data
from qa_automation.clients.promocodes import PromocodesClient
from qa_automation.config import Settings
from qa_automation.models.balance import PXG_MINOR_UNITS, BalanceResponse
from qa_automation.models.promocodes import ApplyPromoResponse, UpsertPromoResponse
from qa_automation.test_data.promocodes import PromoRewardCurrency

BalanceField = Literal["soft", "hard"]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.serial,
    allure.feature("Promocodes to Balance rewards"),
]


@allure.title("SFT promocode increases the test account's soft balance")
@pytest.mark.regression
def test_sft_promocode_increases_user_soft_balance(
    promo_factory: PromoFactory,
    promocodes_admin_client: PromocodesClient,
    balance_admin_client: BalanceClient,
    balance_admin_uuid: UUID,
    balance_live_settings: Settings,
) -> None:
    reward_amount = promo_factory.settings.promocodes_reward_amount

    before, after = _apply_promo_and_wait_for_balance(
        reward_currency="SFT",
        balance_field="soft",
        expected_delta=reward_amount,
        promo_factory=promo_factory,
        promocodes_client=promocodes_admin_client,
        balance_client=balance_admin_client,
        account_uuid=balance_admin_uuid,
        timeout_seconds=balance_live_settings.balance_event_timeout.total_seconds(),
    )

    assert (after.soft or 0) - (before.soft or 0) == reward_amount


@allure.title("PXG promocode increases raw and displayed PXG balance")
@pytest.mark.regression
def test_pxg_promocode_increases_user_pxg_balance(
    promo_factory: PromoFactory,
    promocodes_admin_client: PromocodesClient,
    balance_admin_client: BalanceClient,
    balance_admin_uuid: UUID,
    balance_live_settings: Settings,
) -> None:
    reward_amount = promo_factory.settings.promocodes_reward_amount

    before, after = _apply_promo_and_wait_for_balance(
        reward_currency="PXG",
        balance_field="hard",
        expected_delta=reward_amount * PXG_MINOR_UNITS,
        promo_factory=promo_factory,
        promocodes_client=promocodes_admin_client,
        balance_client=balance_admin_client,
        account_uuid=balance_admin_uuid,
        timeout_seconds=balance_live_settings.balance_event_timeout.total_seconds(),
    )

    assert (after.hard or 0) - (before.hard or 0) == reward_amount * PXG_MINOR_UNITS
    before_display = before.hard_display or Decimal(0)
    after_display = after.hard_display or Decimal(0)
    assert after_display - before_display == Decimal(reward_amount)


def _apply_promo_and_wait_for_balance(
    *,
    reward_currency: PromoRewardCurrency,
    balance_field: BalanceField,
    expected_delta: int,
    promo_factory: PromoFactory,
    promocodes_client: PromocodesClient,
    balance_client: BalanceClient,
    account_uuid: UUID,
    timeout_seconds: float,
) -> tuple[BalanceResponse, BalanceResponse]:
    before = _get_balance(balance_client, account_uuid)
    before_value = _currency_value(before, balance_field)
    created_response, payload = promo_factory.create_active_campaign(
        reward_currency=reward_currency
    )
    assert_response_status(created_response, 200)
    created = validate_success_data(created_response, UpsertPromoResponse)
    assert created.created is True
    assert payload["reward_currency"] == reward_currency

    applied_response = promocodes_client.apply(str(payload["code"]))

    assert_response_status(applied_response, 200)
    applied = validate_success_data(applied_response, ApplyPromoResponse)
    assert applied.promo_uuid == created.promo_uuid
    assert applied.reward_currency == reward_currency
    assert applied.reward_amount == promo_factory.settings.promocodes_reward_amount

    after = _wait_for_balance_value(
        balance_client=balance_client,
        account_uuid=account_uuid,
        balance_field=balance_field,
        expected_value=before_value + expected_delta,
        timeout_seconds=timeout_seconds,
    )
    return before, after


def _wait_for_balance_value(
    *,
    balance_client: BalanceClient,
    account_uuid: UUID,
    balance_field: BalanceField,
    expected_value: int,
    timeout_seconds: float,
) -> BalanceResponse:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    last_value: int | None = None

    while True:
        balance = _get_balance(balance_client, account_uuid)
        last_value = _currency_value(balance, balance_field)
        if last_value == expected_value:
            return balance
        if last_value > expected_value:
            pytest.fail(
                f"TEST_DATA_DEFECT: {balance_field} balance changed beyond the expected "
                f"promo delta; expected {expected_value}, got {last_value}",
                pytrace=False,
            )

        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: {balance_field} promo reward was not credited within "
                f"{timeout_seconds:g}s; expected {expected_value}, last value {last_value}",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.25, remaining))


def _get_balance(balance_client: BalanceClient, account_uuid: UUID) -> BalanceResponse:
    response = balance_client.get_balance_by_uuid(account_uuid)
    assert_response_status(response, 200)
    return validate_success_data(response, BalanceResponse)


def _currency_value(balance: BalanceResponse, balance_field: BalanceField) -> int:
    if balance_field == "soft":
        return balance.soft or 0
    return balance.hard or 0
