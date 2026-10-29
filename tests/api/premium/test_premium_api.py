from __future__ import annotations

from datetime import UTC, datetime

import allure
import pytest

from qa_automation.clients.base import (
    assert_response_status,
    validate_error_response,
    validate_success_data,
)
from qa_automation.clients.goods import GoodsClient
from qa_automation.clients.profile import ProfileClient
from qa_automation.config import Settings
from qa_automation.models.goods import CatalogItems, GoodsDetail, GoodsList
from qa_automation.models.profile import Profile

pytestmark = [
    pytest.mark.api,
    pytest.mark.live,
    allure.feature("Premium (Goods to Profile)"),
]


@allure.title("Premium catalog requires authentication")
@pytest.mark.smoke
def test_premium_catalog_requires_authentication(
    goods_user_client: GoodsClient, goods_live_settings: Settings
) -> None:
    response = goods_user_client.get_goods(
        currency=goods_live_settings.goods_catalog_currency,
        goods_type="subscriptionPremium",
        authenticated=False,
    )

    assert_response_status(response, 401)
    validate_error_response(response)


@allure.title("Premium catalog contains valid subscription goods")
@pytest.mark.smoke
@pytest.mark.contract
def test_premium_catalog_contains_valid_subscriptions(
    goods_user_client: GoodsClient, goods_live_settings: Settings
) -> None:
    response = goods_user_client.get_goods(
        currency=goods_live_settings.goods_catalog_currency,
        goods_type="subscriptionPremium",
    )

    assert_response_status(response, 200)
    catalog = validate_success_data(response, GoodsList)
    assert catalog.data, "TEST_DATA_DEFECT: Premium catalog is empty"
    assert catalog.total >= len(catalog.data)
    uuids = [item.uuid for item in catalog.data]
    assert len(uuids) == len(set(uuids))
    for item in catalog.data:
        assert item.type == "subscriptionPremium"
        assert item.duration_seconds is not None and item.duration_seconds > 0
        assert item.updated_at >= item.created_at


@allure.title("Premium goods detail agrees with its catalog entry")
@pytest.mark.regression
def test_premium_goods_detail_agrees_with_catalog(
    goods_user_client: GoodsClient, goods_live_settings: Settings
) -> None:
    list_response = goods_user_client.get_goods(
        currency=goods_live_settings.goods_catalog_currency,
        goods_type="subscriptionPremium",
    )
    assert_response_status(list_response, 200)
    catalog = validate_success_data(list_response, GoodsList)
    if not catalog.data:
        pytest.fail("TEST_DATA_DEFECT: Premium catalog is empty", pytrace=False)
    selected = catalog.data[0]

    detail_response = goods_user_client.get_good(
        selected.uuid, currency=goods_live_settings.goods_catalog_currency
    )

    assert_response_status(detail_response, 200)
    detail = validate_success_data(detail_response, GoodsDetail)
    assert detail.goods_uuid == selected.uuid
    assert detail.type == selected.type
    assert detail.duration_seconds == selected.duration_seconds
    assert detail.is_available is selected.is_available


@allure.title("Goods validates Premium catalog pagination")
@pytest.mark.regression
@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (101, 0), (10, -1), ("ten", 0)])
def test_premium_catalog_rejects_invalid_pagination(
    goods_user_client: GoodsClient,
    goods_live_settings: Settings,
    limit: object,
    offset: object,
) -> None:
    response = goods_user_client.get_goods(
        currency=goods_live_settings.goods_catalog_currency,
        goods_type="subscriptionPremium",
        limit=limit,
        offset=offset,
    )

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Profile exposes a consistent Premium state")
@pytest.mark.smoke
@pytest.mark.contract
def test_profile_exposes_consistent_premium_state(
    profile_user_client: ProfileClient,
) -> None:
    response = profile_user_client.get_me()

    assert_response_status(response, 200)
    profile = validate_success_data(response, Profile)
    if profile.premium.active:
        assert profile.premium.expiration is not None
        assert profile.premium.expiration > datetime.now(UTC)
    else:
        assert profile.premium.expiration is None


@allure.title("Ordinary user cannot inspect the admin Premium catalog")
@pytest.mark.regression
def test_premium_admin_catalog_rejects_ordinary_user(
    goods_user_client: GoodsClient,
) -> None:
    response = goods_user_client.get_catalog_items(goods_type="subscriptionPremium")

    assert_response_status(response, 403)
    validate_error_response(response)


@allure.title("Admin Premium catalog agrees with the public catalog")
@pytest.mark.regression
def test_admin_and_public_premium_catalogs_agree(
    goods_user_client: GoodsClient,
    goods_admin_client: GoodsClient,
    goods_live_settings: Settings,
) -> None:
    public_response = goods_user_client.get_goods(
        currency=goods_live_settings.goods_catalog_currency,
        goods_type="subscriptionPremium",
    )
    admin_response = goods_admin_client.get_catalog_items(goods_type="subscriptionPremium")

    assert_response_status(public_response, 200)
    assert_response_status(admin_response, 200)
    public = validate_success_data(public_response, GoodsList)
    admin = validate_success_data(admin_response, CatalogItems)
    assert {item.uuid for item in public.data} <= {item.uuid for item in admin.data}
    assert all(item.goods_type == "subscriptionPremium" for item in admin.data)
