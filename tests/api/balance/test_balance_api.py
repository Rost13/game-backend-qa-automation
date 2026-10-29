from __future__ import annotations

from uuid import UUID

import allure
import pytest

from qa_automation.clients.balance import BalanceClient
from qa_automation.clients.base import (
    assert_response_status,
    validate_error_response,
    validate_response_model,
    validate_success_data,
)
from qa_automation.config import Settings
from qa_automation.models.balance import (
    BalanceResponse,
    BalanceServiceError,
    HistoryResponse,
    PublishedBalanceResponse,
    ReferralInvitedResponse,
    ReferralStatusResponse,
    ReplenishResponse,
)

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Balance")]


@allure.title("Balance requires authentication")
@pytest.mark.smoke
def test_balance_requires_authentication(balance_user_client: BalanceClient) -> None:
    response = balance_user_client.get_balance(authenticated=False)

    assert_response_status(response, 401)
    assert validate_error_response(response).error_description == "missing or invalid access token"


@allure.title("Unauthorized Balance response follows the published OpenAPI schema")
@pytest.mark.contract
def test_balance_unauthorized_error_matches_openapi_contract(
    balance_user_client: BalanceClient,
) -> None:
    response = balance_user_client.get_balance(authenticated=False)

    assert_response_status(response, 401)
    validate_response_model(response, BalanceServiceError)


@allure.title("User can get the current balance")
@pytest.mark.smoke
def test_user_can_get_current_balance(balance_user_client: BalanceClient) -> None:
    response = balance_user_client.get_balance()

    assert_response_status(response, 200)
    balance = validate_success_data(response, BalanceResponse)
    assert any(
        value is not None for value in (balance.soft, balance.xp, balance.hard, balance.keys)
    ), "at least one balance currency must be returned"


@allure.title("Current balance follows the published OpenAPI success schema")
@pytest.mark.contract
def test_current_balance_matches_openapi_contract(balance_user_client: BalanceClient) -> None:
    response = balance_user_client.get_balance()

    assert_response_status(response, 200)
    validate_response_model(response, PublishedBalanceResponse)


@allure.title("User can request a page of balance history")
@pytest.mark.smoke
def test_user_can_get_balance_history(balance_user_client: BalanceClient) -> None:
    response = balance_user_client.get_history(limit=5, offset=0)

    assert_response_status(response, 200)
    history = validate_success_data(response, HistoryResponse)
    assert history.meta.limit == 5
    assert history.meta.offset == 0
    assert len(history.items) <= 5


@pytest.mark.parametrize(
    ("currency", "transaction_type", "expected_message"),
    [
        ("invalid", None, "invalid currency type"),
        (None, "invalid", "invalid type (incoming/outcoming)"),
    ],
    ids=["invalid-currency", "invalid-transaction-type"],
)
@allure.title("Balance history rejects unsupported filters")
@pytest.mark.regression
def test_balance_history_rejects_invalid_filter(
    balance_user_client: BalanceClient,
    currency: str | None,
    transaction_type: str | None,
    expected_message: str,
) -> None:
    response = balance_user_client.get_history(
        currency=currency,
        transaction_type=transaction_type,
    )

    assert_response_status(response, 400)
    assert validate_error_response(response).error_description == expected_message


@allure.title("Ordinary user cannot read another user's balance")
@pytest.mark.smoke
def test_regular_user_cannot_get_balance_by_uuid(
    balance_user_client: BalanceClient,
    balance_test_user_uuid: UUID,
) -> None:
    response = balance_user_client.get_balance_by_uuid(balance_test_user_uuid)

    assert_response_status(response, 403)
    assert validate_error_response(response).error_description == "insufficient permissions"


@allure.title("Admin can read the test user's balance")
@pytest.mark.smoke
def test_admin_can_get_test_user_balance(
    balance_admin_client: BalanceClient,
    balance_test_user_uuid: UUID,
) -> None:
    response = balance_admin_client.get_balance_by_uuid(balance_test_user_uuid)

    assert_response_status(response, 200)
    validate_success_data(response, BalanceResponse)


@allure.title("Admin balance lookup rejects a malformed UUID")
@pytest.mark.regression
def test_admin_balance_lookup_rejects_malformed_uuid(
    balance_admin_client: BalanceClient,
) -> None:
    response = balance_admin_client.get_balance_by_uuid("not-a-uuid")

    assert_response_status(response, 400)
    assert validate_error_response(response).error_description == "invalid account uuid"


@allure.title("User can get referral status")
@pytest.mark.smoke
def test_user_can_get_referral_status(balance_user_client: BalanceClient) -> None:
    response = balance_user_client.get_referral_status()

    assert_response_status(response, 200)
    status = validate_success_data(response, ReferralStatusResponse)
    assert status.qualified_count >= 0


@allure.title("User can get a page of invited referrals")
@pytest.mark.regression
def test_user_can_get_invited_referrals(balance_user_client: BalanceClient) -> None:
    response = balance_user_client.get_invited_referrals(limit=1, offset=0)

    assert_response_status(response, 200)
    invited = validate_success_data(response, ReferralInvitedResponse)
    assert len(invited.items) <= 1
    assert invited.total >= len(invited.items)


@allure.title("Invited referrals reject a negative limit")
@pytest.mark.regression
def test_invited_referrals_reject_negative_limit(balance_user_client: BalanceClient) -> None:
    response = balance_user_client.get_invited_referrals(limit=-1, offset=0)

    assert_response_status(response, 400)
    assert validate_error_response(response).error_description == "invalid limit"


@allure.title("Admin can read referral data for the test user")
@pytest.mark.regression
def test_admin_can_get_test_user_referral_data(
    balance_admin_client: BalanceClient,
    balance_test_user_uuid: UUID,
) -> None:
    status_response = balance_admin_client.get_referral_status_by_uuid(balance_test_user_uuid)
    invited_response = balance_admin_client.get_invited_referrals_by_uuid(
        balance_test_user_uuid, limit=1, offset=0
    )

    assert_response_status(status_response, 200)
    validate_success_data(status_response, ReferralStatusResponse)
    assert_response_status(invited_response, 200)
    validate_success_data(invited_response, ReferralInvitedResponse)


@allure.title("Ordinary user cannot replenish a balance")
@pytest.mark.regression
def test_regular_user_cannot_replenish_balance(
    balance_user_client: BalanceClient,
    destructive_rbac_target_uuid: UUID,
) -> None:
    response = balance_user_client.replenish({"uuid": str(destructive_rbac_target_uuid), "soft": 1})

    assert_response_status(response, 403)
    assert validate_error_response(response).error_description == "insufficient permissions"


@allure.title("Admin replenish rejects an empty payload without changing balance")
@pytest.mark.regression
def test_admin_replenish_rejects_empty_payload(balance_admin_client: BalanceClient) -> None:
    response = balance_admin_client.replenish({})

    assert_response_status(response, 400)
    assert validate_error_response(response).error_description == "uid is required"


@allure.title("Admin replenishment increases the test user's soft balance exactly once")
@pytest.mark.regression
@pytest.mark.serial
def test_admin_can_replenish_test_user_soft_balance(
    balance_admin_client: BalanceClient,
    balance_test_user_uuid: UUID,
    balance_mutation_settings: Settings,
) -> None:
    amount = balance_mutation_settings.balance_replenish_amount
    before_response = balance_admin_client.get_balance_by_uuid(balance_test_user_uuid)
    assert_response_status(before_response, 200)
    before = validate_success_data(before_response, BalanceResponse)

    replenish_response = balance_admin_client.replenish(
        {"uuid": str(balance_test_user_uuid), "soft": amount}
    )

    assert_response_status(replenish_response, 200)
    result = validate_success_data(replenish_response, ReplenishResponse)
    assert result.message == "balance replenished successfully"

    after_response = balance_admin_client.get_balance_by_uuid(balance_test_user_uuid)
    assert_response_status(after_response, 200)
    after = validate_success_data(after_response, BalanceResponse)
    assert (after.soft or 0) == (before.soft or 0) + amount


@allure.title("Ordinary user cannot run referral backfill")
@pytest.mark.regression
def test_regular_user_cannot_backfill_referrals(
    balance_user_client: BalanceClient,
    destructive_rbac_target_uuid: UUID,
) -> None:
    response = balance_user_client.backfill_referrals(
        {"referrer_uuids": [str(destructive_rbac_target_uuid)], "batch_size": 1}
    )

    assert_response_status(response, 403)
    assert validate_error_response(response).error_description == "insufficient permissions"


@allure.title("Admin referral backfill rejects an empty payload without changing data")
@pytest.mark.regression
def test_admin_backfill_rejects_empty_payload(balance_admin_client: BalanceClient) -> None:
    response = balance_admin_client.backfill_referrals({})

    assert_response_status(response, 400)
    assert validate_error_response(response).error_description == "referrer_uuids is required"
