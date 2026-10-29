from __future__ import annotations

from uuid import UUID

import allure
import pytest

from qa_automation.clients.base import (
    assert_response_status,
    validate_error_response,
    validate_success_data,
)
from qa_automation.clients.inventory import InventoryClient
from qa_automation.config import Settings
from qa_automation.models.inventory import InventoryItem, InventoryItemList, InventoryItems

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Inventory")]


@allure.title("Inventory user endpoints require authentication")
@pytest.mark.smoke
@pytest.mark.parametrize("operation", ["equipped", "items"])
def test_inventory_user_endpoints_require_authentication(
    inventory_user_client: InventoryClient,
    inventory_live_settings: Settings,
    operation: str,
) -> None:
    if operation == "equipped":
        response = inventory_user_client.get_equipped(authenticated=False)
    else:
        assert inventory_live_settings.inventory_test_category is not None
        assert inventory_live_settings.inventory_test_class is not None
        response = inventory_user_client.get_items(
            inventory_live_settings.inventory_test_category,
            inventory_live_settings.inventory_test_class,
            authenticated=False,
        )

    assert_response_status(response, 401)
    validate_error_response(response)


@allure.title("Guest Inventory endpoints return valid item lists")
@pytest.mark.smoke
@pytest.mark.contract
def test_guest_inventory_endpoints_return_valid_items(
    inventory_user_client: InventoryClient, inventory_live_settings: Settings
) -> None:
    assert inventory_live_settings.inventory_test_category is not None
    equipped_response = inventory_user_client.get_guest_equipped()
    items_response = inventory_user_client.get_guest_items(
        inventory_live_settings.inventory_test_category
    )

    assert_response_status(equipped_response, 200)
    assert_response_status(items_response, 200)
    _assert_unique_items(validate_success_data(equipped_response, InventoryItems).root)
    _assert_unique_items(validate_success_data(items_response, InventoryItems).root)


@allure.title("User Inventory list respects its response contract")
@pytest.mark.smoke
@pytest.mark.contract
def test_user_inventory_list_is_consistent(
    inventory_user_client: InventoryClient, inventory_live_settings: Settings
) -> None:
    assert inventory_live_settings.inventory_test_category is not None
    assert inventory_live_settings.inventory_test_class is not None
    response = inventory_user_client.get_items(
        inventory_live_settings.inventory_test_category,
        inventory_live_settings.inventory_test_class,
        sort="newest",
        offset=0,
        limit=10,
    )

    assert_response_status(response, 200)
    result = validate_success_data(response, InventoryItemList)
    assert len(result.items) <= 10
    assert result.total >= len(result.items)
    _assert_unique_items(result.items)


@allure.title("Inventory exposes one consistent internal user ID")
@pytest.mark.contract
def test_inventory_exposes_consistent_internal_user_id(inventory_user_id: int) -> None:
    assert inventory_user_id != 0


@allure.title("Inventory rejects invalid list filters: {case}")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("case", "item_class", "sort", "offset", "limit"),
    [
        ("missing class", None, None, None, None),
        ("invalid sort", "configured", "oldest", None, None),
        ("invalid offset", "configured", None, "zero", None),
        ("invalid limit", "configured", None, None, "ten"),
    ],
)
def test_inventory_rejects_invalid_list_filters(
    inventory_user_client: InventoryClient,
    inventory_live_settings: Settings,
    case: str,
    item_class: str | None,
    sort: str | None,
    offset: object | None,
    limit: object | None,
) -> None:
    assert inventory_live_settings.inventory_test_category is not None
    configured_class = inventory_live_settings.inventory_test_class
    selected_class = configured_class if item_class == "configured" else item_class
    response = inventory_user_client.get_items(
        inventory_live_settings.inventory_test_category,
        selected_class,
        sort=sort,
        offset=offset,
        limit=limit,
    )

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Ordinary user cannot use Inventory admin routes")
@pytest.mark.regression
def test_inventory_admin_routes_reject_ordinary_user(
    inventory_user_client: InventoryClient,
) -> None:
    response = inventory_user_client.grant_item({"user_id": 1, "item_def_id": "x"})

    assert_response_status(response, 403)
    validate_error_response(response)


@allure.title("Inventory admin grant validates its request")
@pytest.mark.regression
def test_inventory_admin_grant_validates_request(
    inventory_admin_client: InventoryClient,
) -> None:
    response = inventory_admin_client.grant_item({"user_id": 0, "item_def_id": ""})

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Inventory admin list matches the user's list")
@pytest.mark.regression
def test_inventory_admin_list_matches_user_list(
    inventory_user_client: InventoryClient,
    inventory_admin_client: InventoryClient,
    inventory_live_settings: Settings,
    api_test_user_uuid: UUID,
) -> None:
    assert inventory_live_settings.inventory_test_category is not None
    assert inventory_live_settings.inventory_test_class is not None
    user_response = inventory_user_client.get_items(
        inventory_live_settings.inventory_test_category,
        inventory_live_settings.inventory_test_class,
        offset=0,
        limit=100,
    )
    admin_response = inventory_admin_client.get_items_by_uuid(
        inventory_live_settings.inventory_test_category,
        api_test_user_uuid,
        inventory_live_settings.inventory_test_class,
    )

    assert_response_status(user_response, 200)
    assert_response_status(admin_response, 200)
    user_items = validate_success_data(user_response, InventoryItemList)
    admin_items = validate_success_data(admin_response, InventoryItemList)
    assert admin_items == user_items


@allure.title("Published Swagger Inventory list path is callable")
@pytest.mark.contract
def test_documented_inventory_list_path_is_callable(
    inventory_user_client: InventoryClient, inventory_live_settings: Settings
) -> None:
    assert inventory_live_settings.inventory_test_category is not None
    assert inventory_live_settings.inventory_test_class is not None
    response = inventory_user_client.get_documented_items(
        inventory_live_settings.inventory_test_category,
        inventory_live_settings.inventory_test_class,
    )

    assert_response_status(response, 200)
    validate_success_data(response, InventoryItemList)


def _assert_unique_items(items: list[InventoryItem]) -> None:
    item_ids = [item.uuid for item in items]
    assert len(item_ids) == len(set(item_ids)), "Inventory item UUIDs must be unique"
    for item in items:
        assert item.type.strip()
        assert item.quantity >= 0
