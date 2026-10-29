from __future__ import annotations

import allure
import pytest
from fixtures.inventory import GrantedInventoryItem

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.regression,
    pytest.mark.serial,
    allure.feature("Goods to Inventory"),
]


@allure.title("Goods admin grant delivers the configured Inventory item")
def test_goods_grant_delivers_configured_inventory_item(
    granted_inventory_item: GrantedInventoryItem,
) -> None:
    assert granted_inventory_item.item_uuid != granted_inventory_item.definition_uuid
    assert granted_inventory_item.item_type.strip()
    assert granted_inventory_item.owner_id != 0
