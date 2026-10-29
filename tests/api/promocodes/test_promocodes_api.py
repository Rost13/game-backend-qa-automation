from __future__ import annotations

import allure
import pytest
from fixtures.promocodes import PromoFactory

from qa_automation.clients.base import (
    assert_response_status,
    validate_error_response,
    validate_response_model,
    validate_success_data,
)
from qa_automation.clients.promocodes import PromocodesClient
from qa_automation.db.promocodes import PromocodesDatabase, PromoRecord
from qa_automation.models.promocodes import (
    ApplyPromoResponse,
    ListPromosResponse,
    Promo,
    ServiceError,
    SetActivePromoResponse,
    UpsertPromoResponse,
)

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Promocodes")]


@allure.title("Promocodes list requires authentication")
@pytest.mark.smoke
def test_promocodes_list_requires_authentication(
    promocodes_user_client: PromocodesClient,
) -> None:
    response = promocodes_user_client.list_promos(offset=0, limit=1, authenticated=False)

    assert_response_status(response, 401)
    error = validate_error_response(response)
    assert error.error_description == "missing or invalid access token"


@allure.title("Unauthorized error follows the published OpenAPI ServiceError schema")
@pytest.mark.contract
def test_unauthorized_error_matches_openapi_contract(
    promocodes_user_client: PromocodesClient,
) -> None:
    response = promocodes_user_client.list_promos(offset=0, limit=1, authenticated=False)

    assert_response_status(response, 401)
    validate_response_model(response, ServiceError)


@allure.title("An ordinary user cannot access the admin Promocodes list")
@pytest.mark.smoke
def test_regular_user_cannot_list_admin_promocodes(
    promocodes_user_client: PromocodesClient,
) -> None:
    response = promocodes_user_client.list_promos(offset=0, limit=1)

    assert_response_status(response, 403)
    error = validate_error_response(response)
    assert error.error_description == "insufficient permissions"


@allure.title("Promocodes list returns the requested page")
@pytest.mark.smoke
def test_promocodes_list_returns_requested_page(
    promocodes_admin_client: PromocodesClient,
) -> None:
    response = promocodes_admin_client.list_promos(offset=0, limit=5)

    assert_response_status(response, 200)
    page = validate_success_data(response, ListPromosResponse)
    assert page.offset == 0
    assert page.limit == 5
    assert page.total >= len(page.items)
    assert len(page.items) <= 5
    assert all(item.code for item in page.items)


@allure.title("Promocodes list follows the published OpenAPI success schema")
@pytest.mark.contract
def test_promocodes_list_matches_openapi_contract(
    promocodes_admin_client: PromocodesClient,
) -> None:
    response = promocodes_admin_client.list_promos(offset=0, limit=1)

    assert_response_status(response, 200)
    validate_response_model(response, ListPromosResponse)


@allure.title("Promocodes list rejects a negative offset")
@pytest.mark.regression
def test_promocodes_list_rejects_negative_offset(
    promocodes_admin_client: PromocodesClient,
) -> None:
    response = promocodes_admin_client.list_promos(offset=-1, limit=10)

    assert_response_status(response, 400)
    assert validate_error_response(response).error_description


@allure.title("Admin can create an active campaign and retrieve it from the list")
@pytest.mark.regression
@pytest.mark.serial
def test_admin_can_create_active_campaign(
    promo_factory: PromoFactory,
    promocodes_admin_client: PromocodesClient,
    promo_database: PromocodesDatabase | None,
) -> None:
    created, payload = promo_factory.create_active_campaign()

    assert_response_status(created, 200)
    result = validate_success_data(created, UpsertPromoResponse)
    assert result.code == payload["code"]
    assert result.created is True

    listed = _find_promo(promocodes_admin_client, str(result.promo_uuid))
    assert listed is not None, f"created promo {result.promo_uuid} was not returned by list"
    assert listed.code == payload["code"]
    assert listed.is_active is True
    assert listed.reward_currency == "SFT"
    assert listed.reward_amount == payload["reward_amount"]

    if promo_database is not None:
        _assert_initial_database_state(promo_database, str(result.promo_uuid), payload)


@allure.title("Upsert updates an existing campaign without creating a duplicate")
@pytest.mark.regression
@pytest.mark.serial
def test_upsert_updates_existing_campaign(
    promo_factory: PromoFactory,
    promocodes_admin_client: PromocodesClient,
    promo_database: PromocodesDatabase | None,
) -> None:
    created, payload = promo_factory.create_active_campaign()
    assert_response_status(created, 200)
    original = validate_success_data(created, UpsertPromoResponse)

    original_reward_amount = payload["reward_amount"]
    assert isinstance(original_reward_amount, int)
    updated_payload = {**payload, "reward_amount": original_reward_amount + 1}
    updated = promocodes_admin_client.upsert(updated_payload)

    assert_response_status(updated, 200)
    result = validate_success_data(updated, UpsertPromoResponse)
    assert result.promo_uuid == original.promo_uuid
    assert result.code == original.code
    assert result.created is False

    if promo_database is not None:
        record = _require_promo(promo_database, str(result.promo_uuid))
        assert record.reward_amount == updated_payload["reward_amount"]
        assert record.claims_used == 0


@allure.title("A deactivated campaign cannot be applied")
@pytest.mark.regression
@pytest.mark.serial
def test_deactivated_campaign_cannot_be_applied(
    promo_factory: PromoFactory,
    promocodes_admin_client: PromocodesClient,
    promo_database: PromocodesDatabase | None,
) -> None:
    created, payload = promo_factory.create_active_campaign()
    assert_response_status(created, 200)
    promo_uuid = str(validate_success_data(created, UpsertPromoResponse).promo_uuid)

    first = promocodes_admin_client.deactivate(promo_uuid)
    second = promocodes_admin_client.deactivate(promo_uuid)
    applied = promocodes_admin_client.apply(str(payload["code"]))

    assert_response_status(first, 200)
    first_result = validate_success_data(first, SetActivePromoResponse)
    assert str(first_result.promo_uuid) == promo_uuid
    assert first_result.is_active is False
    assert first_result.changed is True

    assert_response_status(second, 200)
    second_result = validate_success_data(second, SetActivePromoResponse)
    assert second_result.is_active is False
    assert second_result.changed is False
    assert_response_status(applied, 400)

    if promo_database is not None:
        assert _require_promo(promo_database, promo_uuid).is_active is False


@allure.title("A reactivated campaign can be applied only once by the same user")
@pytest.mark.regression
@pytest.mark.serial
def test_reactivated_campaign_can_be_applied_only_once(
    promo_factory: PromoFactory,
    promocodes_admin_client: PromocodesClient,
    promo_database: PromocodesDatabase | None,
) -> None:
    created, payload = promo_factory.create_active_campaign()
    assert_response_status(created, 200)
    promo_uuid = str(validate_success_data(created, UpsertPromoResponse).promo_uuid)

    assert_response_status(promocodes_admin_client.deactivate(promo_uuid), 200)
    activated = promocodes_admin_client.activate(promo_uuid)
    first_apply = promocodes_admin_client.apply(str(payload["code"]))
    duplicate_apply = promocodes_admin_client.apply(str(payload["code"]))

    assert_response_status(activated, 200)
    activation = validate_success_data(activated, SetActivePromoResponse)
    assert str(activation.promo_uuid) == promo_uuid
    assert activation.is_active is True
    assert activation.changed is True

    assert_response_status(first_apply, 200)
    applied = validate_success_data(first_apply, ApplyPromoResponse)
    assert str(applied.promo_uuid) == promo_uuid
    assert applied.code == payload["code"]
    assert applied.reward_currency == "SFT"
    assert applied.reward_amount == payload["reward_amount"]
    assert applied.referral_applied is False
    assert_response_status(duplicate_apply, 400)

    if promo_database is not None:
        record = _require_promo(promo_database, promo_uuid)
        assert record.claims_used == 1
        assert promo_database.application_count(promo_uuid) == 1


@allure.title("Upsert rejects a payload without required campaign fields")
@pytest.mark.regression
def test_upsert_rejects_missing_required_fields(
    promocodes_admin_client: PromocodesClient,
) -> None:
    response = promocodes_admin_client.upsert(
        {"code": "BAD", "type": "CAMPAIGN", "reward_amount": 1}
    )

    assert_response_status(response, 400)
    assert validate_error_response(response).error_description


@allure.title("Activate rejects a malformed promo UUID")
@pytest.mark.regression
def test_activate_rejects_malformed_uuid(
    promocodes_admin_client: PromocodesClient,
) -> None:
    response = promocodes_admin_client.activate("not-a-uuid")

    assert_response_status(response, 400)
    assert validate_error_response(response).error_description


@allure.title("An ordinary user receives bad request when promo code is empty")
@pytest.mark.smoke
def test_regular_user_cannot_apply_empty_promocode(
    promocodes_user_client: PromocodesClient,
) -> None:
    response = promocodes_user_client.apply("")

    assert_response_status(response, 400)
    error = validate_error_response(response)
    assert error.error_description == "code is required"


def _find_promo(promocodes_admin_client: PromocodesClient, promo_uuid: str) -> Promo | None:
    offset = 0
    limit = 100
    while True:
        response = promocodes_admin_client.list_promos(offset=offset, limit=limit)
        assert_response_status(response, 200)
        page = validate_success_data(response, ListPromosResponse)
        for promo in page.items:
            if str(promo.uuid) == promo_uuid:
                return promo
        offset += len(page.items)
        if not page.items or offset >= page.total:
            return None


def _assert_initial_database_state(
    database: PromocodesDatabase,
    promo_uuid: str,
    payload: dict[str, object],
) -> None:
    record = _require_promo(database, promo_uuid)
    assert record.code == payload["code"]
    assert record.is_active is True
    assert record.reward_currency == "SFT"
    assert record.reward_amount == payload["reward_amount"]
    assert record.max_claims == payload["max_claims"]
    assert record.claims_used == 0
    assert database.application_count(promo_uuid) == 0


def _require_promo(database: PromocodesDatabase, promo_uuid: str) -> PromoRecord:
    record = database.get_promo(promo_uuid)
    assert record is not None, f"promo {promo_uuid} must exist in PostgreSQL"
    return record
