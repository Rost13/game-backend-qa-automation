from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import allure
import pytest

from qa_automation.clients.base import (
    assert_response_status,
    validate_error_response,
    validate_success_data,
)
from qa_automation.clients.boosters import BoostersClient
from qa_automation.models.boosters import BoosterStates

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Boosters")]


@allure.title("Boosters requires authentication")
@pytest.mark.smoke
def test_boosters_requires_authentication(boosters_user_client: BoostersClient) -> None:
    response = boosters_user_client.get_active(authenticated=False)

    assert_response_status(response, 401)
    validate_error_response(response)


@allure.title("User receives valid unique active boosters")
@pytest.mark.smoke
@pytest.mark.contract
def test_user_receives_valid_active_boosters(boosters_user_client: BoostersClient) -> None:
    response = boosters_user_client.get_active()

    assert_response_status(response, 200)
    states = validate_success_data(response, BoosterStates).root
    types = [state.type for state in states]
    assert len(types) == len(set(types)), "active booster types must be unique"
    now = datetime.now(UTC)
    for state in states:
        assert state.type.strip()
        assert state.source.strip()
        assert state.updated_at < state.expires_at
        assert state.expires_at > now, "inactive booster returned by the active endpoint"


@allure.title("Boosters rejects invalid at_ms: {at_ms}")
@pytest.mark.regression
@pytest.mark.parametrize("at_ms", [0, -1, "not-a-number"])
def test_boosters_rejects_invalid_timestamp(
    boosters_user_client: BoostersClient, at_ms: object
) -> None:
    response = boosters_user_client.get_active(at_ms=at_ms)

    assert_response_status(response, 400)
    error = validate_error_response(response)
    assert error.error_description == "invalid at_ms"


@allure.title("Ordinary user cannot inspect another user's boosters")
@pytest.mark.regression
def test_boosters_admin_route_rejects_ordinary_user(
    boosters_user_client: BoostersClient, api_test_user_uuid: UUID
) -> None:
    response = boosters_user_client.get_active_by_uuid(api_test_user_uuid)

    assert_response_status(response, 403)
    validate_error_response(response)


@allure.title("Admin booster view matches the user's view at the same timestamp")
@pytest.mark.regression
def test_boosters_admin_view_matches_user_view(
    boosters_user_client: BoostersClient,
    boosters_admin_client: BoostersClient,
    api_test_user_uuid: UUID,
) -> None:
    at_ms = int(datetime.now(UTC).timestamp() * 1000)
    user_response = boosters_user_client.get_active(at_ms=at_ms)
    admin_response = boosters_admin_client.get_active_by_uuid(api_test_user_uuid, at_ms=at_ms)

    assert_response_status(user_response, 200)
    assert_response_status(admin_response, 200)
    user_states = validate_success_data(user_response, BoosterStates)
    admin_states = validate_success_data(admin_response, BoosterStates)
    assert admin_states == user_states


@allure.title("Published Swagger admin booster path is callable")
@pytest.mark.contract
def test_documented_boosters_admin_path_is_callable(
    boosters_admin_client: BoostersClient, api_test_user_uuid: UUID
) -> None:
    response = boosters_admin_client.get_active_by_documented_path(api_test_user_uuid)

    assert_response_status(response, 200)
    validate_success_data(response, BoosterStates)
