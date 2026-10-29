from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import Field, RootModel

from qa_automation.models.common import ApiModel

NonNegativeInt = Annotated[int, Field(ge=0)]


class InventoryItem(ApiModel):
    uuid: UUID
    def_uuid: UUID = Field(alias="defUuid")
    owner_id: int = Field(alias="ownerId")
    name: str
    type: str
    display_type: str = Field(alias="displayType")
    description: str
    icon_url: str = Field(alias="iconUrl")
    collection: str
    tags: str
    default_tags: str = Field(alias="defaultTags")
    weapon_id: str | None = Field(default=None, alias="weaponId")
    weapon_level: NonNegativeInt | None = Field(default=None, alias="weaponLevel")
    app_files: str = Field(alias="appFiles")
    supply: int
    is_equippable: bool = Field(alias="isEquippable")
    equipped: bool
    last_equipped: bool = Field(alias="lastEquipped")
    equip_slot: str = Field(alias="equipSlot")
    quantity: NonNegativeInt
    rarity: str
    serial: int
    hold_till: NonNegativeInt = Field(alias="holdTill")
    issued: int | None = None
    max_supply: int | None = Field(default=None, alias="maxSupply")


class InventoryItems(RootModel[list[InventoryItem]]):
    pass


class InventoryItemList(ApiModel):
    items: list[InventoryItem]
    total: NonNegativeInt


class InventoryGrantResponse(ApiModel):
    status: str
    user_id: int
    item_def_id: UUID
    quantity: Annotated[int, Field(gt=0)]
    item_ids: list[UUID]
    hold_till: str
    payment_id: int
