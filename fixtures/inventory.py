from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from threading import Event
from time import monotonic
from uuid import UUID

import pytest

from qa_automation.clients.base import ApiClient, assert_response_status, validate_success_data
from qa_automation.clients.goods import GoodsClient
from qa_automation.clients.inventory import InventoryClient
from qa_automation.config import Settings
from qa_automation.models.goods import CatalogItem, GoodsGrantResponse
from qa_automation.models.inventory import InventoryItem, InventoryItemList, InventoryItems


@dataclass(frozen=True)
class GrantedInventoryItem:
    item_uuid: UUID
    definition_uuid: UUID
    item_type: str
    owner_id: int


def _client(settings: Settings, token: str) -> Iterator[InventoryClient]:
    assert settings.inventory_base_url is not None
    assert settings.inventory_api_path is not None
    transport = ApiClient(str(settings.inventory_base_url), token, settings.timeout_seconds)
    yield InventoryClient(transport, settings.inventory_api_path)
    transport.close()


@pytest.fixture(scope="session")
def inventory_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_inventory_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Inventory configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


@pytest.fixture(scope="session")
def inventory_user_client(inventory_live_settings: Settings) -> Iterator[InventoryClient]:
    assert inventory_live_settings.user_bearer_token is not None
    yield from _client(inventory_live_settings, inventory_live_settings.user_bearer_token)


@pytest.fixture(scope="session")
def inventory_admin_client(inventory_live_settings: Settings) -> Iterator[InventoryClient]:
    if inventory_live_settings.admin_bearer_token is None:
        pytest.fail("ENVIRONMENT_DEFECT: API_ADMIN_BEARER_TOKEN is not configured", pytrace=False)
    yield from _client(inventory_live_settings, inventory_live_settings.admin_bearer_token)


@pytest.fixture(scope="session")
def inventory_user_id(
    inventory_user_client: InventoryClient,
    inventory_live_settings: Settings,
) -> int:
    equipped_response = inventory_user_client.get_equipped()
    assert_response_status(equipped_response, 200)
    equipped = validate_success_data(equipped_response, InventoryItems).root
    candidates = equipped
    if not candidates:
        assert inventory_live_settings.inventory_test_category is not None
        assert inventory_live_settings.inventory_test_class is not None
        items_response = inventory_user_client.get_items(
            inventory_live_settings.inventory_test_category,
            inventory_live_settings.inventory_test_class,
            offset=0,
            limit=100,
        )
        assert_response_status(items_response, 200)
        candidates = validate_success_data(items_response, InventoryItemList).items
    return _single_inventory_owner_id(candidates)


@pytest.fixture(scope="session")
def inventory_grant_settings(inventory_live_settings: Settings) -> Settings:
    if not inventory_live_settings.inventory_grants_enabled:
        pytest.skip("Inventory grants are disabled; set INVENTORY_GRANTS_ENABLED=true")
    missing = inventory_live_settings.missing_inventory_grant_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Inventory grant configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return inventory_live_settings


@pytest.fixture(scope="session")
def granted_inventory_item(
    inventory_grant_settings: Settings,
    goods_admin_client: GoodsClient,
    inventory_admin_client: InventoryClient,
    api_test_user_uuid: UUID,
    inventory_user_id: int,
) -> GrantedInventoryItem:
    goods_uuid = inventory_grant_settings.inventory_test_goods_uuid
    assert goods_uuid is not None
    catalog_response = goods_admin_client.get_catalog_item(goods_uuid)
    assert_response_status(catalog_response, 200)
    catalog = validate_success_data(catalog_response, CatalogItem)
    assert catalog.core.is_item is True, (
        "TEST_DATA_DEFECT: INVENTORY_TEST_GOODS_UUID is not an Inventory item"
    )
    assert catalog.config.item is not None, (
        "TEST_DATA_DEFECT: configured Inventory good has no item config"
    )
    category = catalog.core.goods_type
    item_class = catalog.config.item.class_
    before = _get_items(inventory_admin_client, category, item_class, api_test_user_uuid)
    before_ids = _definition_item_ids(before, goods_uuid)
    quantity_before = _definition_quantity(before, goods_uuid)

    grant_response = goods_admin_client.admin_grant(
        {
            "user_uuid": str(api_test_user_uuid),
            "goods_uuid": str(goods_uuid),
            "quantity": 1,
            "reason": "qa-inventory-stat-integration",
        }
    )
    assert_response_status(grant_response, 200)
    grant = validate_success_data(grant_response, GoodsGrantResponse)
    assert grant.success is True
    assert grant.quantity == 1

    settled = _wait_for_definition_quantity(
        inventory_admin_client,
        category,
        item_class,
        api_test_user_uuid,
        goods_uuid,
        quantity_before + 1,
        inventory_grant_settings.reward_delivery_timeout.total_seconds(),
    )
    created_ids = _definition_item_ids(settled, goods_uuid) - before_ids
    assert len(created_ids) == 1, (
        "PRODUCT_DEFECT: Goods grant must create exactly one new Inventory item UUID; "
        f"created {len(created_ids)}"
    )
    item_uuid = created_ids.pop()
    delivered = next(item for item in settled.items if item.uuid == item_uuid)
    assert delivered.owner_id == inventory_user_id
    return GrantedInventoryItem(
        item_uuid=item_uuid,
        definition_uuid=goods_uuid,
        item_type=delivered.type,
        owner_id=delivered.owner_id,
    )


def _single_inventory_owner_id(items: list[InventoryItem]) -> int:
    owner_ids = {item.owner_id for item in items if item.owner_id != 0}
    if not owner_ids:
        pytest.fail(
            "TEST_DATA_DEFECT: Inventory API returned no item from which to resolve ownerId",
            pytrace=False,
        )
    if len(owner_ids) != 1:
        pytest.fail(
            f"PRODUCT_DEFECT: Inventory API returned multiple ownerId values: {owner_ids}",
            pytrace=False,
        )
    return owner_ids.pop()


def _get_items(
    client: InventoryClient, category: str, item_class: str, user_uuid: UUID
) -> InventoryItemList:
    response = client.get_items_by_uuid(category, user_uuid, item_class)
    assert_response_status(response, 200)
    return validate_success_data(response, InventoryItemList)


def _definition_quantity(items: InventoryItemList, definition_uuid: UUID) -> int:
    return sum(item.quantity for item in items.items if item.def_uuid == definition_uuid)


def _definition_item_ids(items: InventoryItemList, definition_uuid: UUID) -> set[UUID]:
    return {item.uuid for item in items.items if item.def_uuid == definition_uuid}


def _wait_for_definition_quantity(
    client: InventoryClient,
    category: str,
    item_class: str,
    user_uuid: UUID,
    definition_uuid: UUID,
    expected: int,
    timeout_seconds: float,
) -> InventoryItemList:
    deadline = monotonic() + timeout_seconds
    waiter = Event()
    while True:
        current = _get_items(client, category, item_class, user_uuid)
        current_quantity = _definition_quantity(current, definition_uuid)
        if current_quantity == expected:
            return current
        if current_quantity > expected:
            pytest.fail(
                "TEST_DATA_DEFECT: Inventory definition quantity exceeded the exact "
                f"expected value {expected}; got {current_quantity}",
                pytrace=False,
            )
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: Inventory definition {definition_uuid} did not reach "
                f"quantity {expected} within {timeout_seconds:g}s",
                pytrace=False,
            )
        waiter.wait(timeout=min(0.25, remaining))
