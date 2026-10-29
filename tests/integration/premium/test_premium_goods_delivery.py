from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Event
from time import monotonic
from uuid import UUID

import allure
import pytest

from qa_automation.clients.base import assert_response_status, validate_success_data
from qa_automation.clients.goods import GoodsClient
from qa_automation.clients.profile import ProfileClient
from qa_automation.config import Settings
from qa_automation.models.goods import CatalogItem, GoodsGrantResponse
from qa_automation.models.profile import Profile

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.regression,
    pytest.mark.serial,
    allure.feature("Goods to Profile Premium"),
]


@allure.title("Goods admin grant extends Profile Premium by the configured duration")
def test_goods_grant_extends_profile_premium(
    premium_grant_settings: Settings,
    goods_admin_client: GoodsClient,
    profile_user_client: ProfileClient,
    api_test_user_uuid: UUID,
) -> None:
    goods_uuid = premium_grant_settings.premium_test_goods_uuid
    assert goods_uuid is not None
    catalog_response = goods_admin_client.get_catalog_item(goods_uuid)
    assert_response_status(catalog_response, 200)
    catalog = validate_success_data(catalog_response, CatalogItem)
    assert catalog.core.goods_type == "subscriptionPremium", (
        "TEST_DATA_DEFECT: PREMIUM_TEST_GOODS_UUID is not a Premium subscription"
    )
    assert catalog.config.subscription is not None, (
        "TEST_DATA_DEFECT: Premium good has no subscription config"
    )
    duration = timedelta(seconds=catalog.config.subscription.duration_seconds)
    before = _get_profile(profile_user_client)
    started_at = datetime.now(UTC)

    grant_response = goods_admin_client.admin_grant(
        {
            "user_uuid": str(api_test_user_uuid),
            "goods_uuid": str(goods_uuid),
            "quantity": 1,
            "reason": "qa-premium-integration",
        }
    )
    completed_at = datetime.now(UTC)

    assert_response_status(grant_response, 200)
    grant = validate_success_data(grant_response, GoodsGrantResponse)
    assert grant.success is True
    assert grant.quantity == 1
    after = _wait_for_premium_change(
        profile_user_client,
        before.premium.expiration,
        premium_grant_settings.reward_delivery_timeout.total_seconds(),
    )
    assert after.account_uuid == api_test_user_uuid
    assert after.premium.active is True
    assert after.premium.expiration is not None
    if before.premium.active and before.premium.expiration is not None:
        assert after.premium.expiration == before.premium.expiration + duration
    else:
        assert started_at + duration <= after.premium.expiration <= completed_at + duration


def _get_profile(client: ProfileClient) -> Profile:
    response = client.get_me()
    assert_response_status(response, 200)
    return validate_success_data(response, Profile)


def _wait_for_premium_change(
    client: ProfileClient,
    previous_expiration: datetime | None,
    timeout_seconds: float,
) -> Profile:
    deadline = monotonic() + timeout_seconds
    waiter = Event()
    while True:
        profile = _get_profile(client)
        if profile.premium.expiration is not None and (
            previous_expiration is None or profile.premium.expiration > previous_expiration
        ):
            return profile
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: Profile Premium did not change within {timeout_seconds:g}s",
                pytrace=False,
            )
        waiter.wait(timeout=min(0.25, remaining))
