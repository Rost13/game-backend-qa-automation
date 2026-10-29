from __future__ import annotations

from datetime import timedelta
from threading import Event
from time import monotonic
from uuid import UUID

import allure
import pytest

from qa_automation.clients.base import assert_response_status, validate_success_data
from qa_automation.clients.boosters import BoostersClient
from qa_automation.clients.goods import GoodsClient
from qa_automation.config import Settings
from qa_automation.models.boosters import BoosterState, BoosterStates
from qa_automation.models.goods import CatalogItem, GoodsGrantResponse

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.regression,
    pytest.mark.serial,
    allure.feature("Goods to Boosters"),
]


@allure.title("Goods admin grant activates the configured booster exactly once")
def test_goods_grant_activates_configured_booster(
    booster_grant_settings: Settings,
    goods_admin_client: GoodsClient,
    boosters_admin_client: BoostersClient,
    api_test_user_uuid: UUID,
) -> None:
    goods_uuid = booster_grant_settings.booster_test_goods_uuid
    assert goods_uuid is not None
    catalog_response = goods_admin_client.get_catalog_item(goods_uuid)
    assert_response_status(catalog_response, 200)
    catalog = validate_success_data(catalog_response, CatalogItem)
    assert catalog.core.goods_type == "boosters", (
        "TEST_DATA_DEFECT: BOOSTER_TEST_GOODS_UUID is not a booster good"
    )
    assert catalog.config.booster is not None, (
        "TEST_DATA_DEFECT: configured booster good has no booster config"
    )
    config = catalog.config.booster
    before = _get_boosters(boosters_admin_client, api_test_user_uuid)
    previous = next((item for item in before if item.type == config.booster_type), None)

    grant_response = goods_admin_client.admin_grant(
        {
            "user_uuid": str(api_test_user_uuid),
            "goods_uuid": str(goods_uuid),
            "quantity": 1,
            "reason": "qa-booster-integration",
        }
    )

    assert_response_status(grant_response, 200)
    grant = validate_success_data(grant_response, GoodsGrantResponse)
    assert grant.success is True
    assert grant.quantity == 1
    activated = _wait_for_booster(
        boosters_admin_client,
        api_test_user_uuid,
        config.booster_type,
        previous,
        booster_grant_settings.reward_delivery_timeout.total_seconds(),
    )
    assert activated.power_percent == config.power_percent
    if previous is None:
        assert activated.expires_at - activated.updated_at == timedelta(
            seconds=config.duration_seconds
        )
    else:
        assert activated.expires_at - previous.expires_at == timedelta(
            seconds=config.duration_seconds
        )


def _get_boosters(client: BoostersClient, user_uuid: UUID) -> list[BoosterState]:
    response = client.get_active_by_uuid(user_uuid)
    assert_response_status(response, 200)
    return validate_success_data(response, BoosterStates).root


def _wait_for_booster(
    client: BoostersClient,
    user_uuid: UUID,
    booster_type: str,
    previous: BoosterState | None,
    timeout_seconds: float,
) -> BoosterState:
    deadline = monotonic() + timeout_seconds
    waiter = Event()
    while True:
        current = next(
            (item for item in _get_boosters(client, user_uuid) if item.type == booster_type),
            None,
        )
        if current is not None and (previous is None or current.expires_at > previous.expires_at):
            return current
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: booster {booster_type!r} was not delivered within "
                f"{timeout_seconds:g}s",
                pytrace=False,
            )
        waiter.wait(timeout=min(0.25, remaining))
