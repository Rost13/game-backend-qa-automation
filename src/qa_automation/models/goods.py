from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from qa_automation.models.common import ApiModel

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class GoodsPrice(ApiModel):
    price: str
    price_usd: str = Field(alias="priceUsd")
    last_price: str = Field(alias="lastPrice")
    currency: str


class GoodsListItem(ApiModel):
    uuid: UUID
    type: str
    name: str
    is_available: bool = Field(alias="isAvailable")
    is_item: bool = Field(alias="isItem")
    is_sold_out: bool = Field(alias="isSoldOut")
    pack_amount: NonNegativeInt = Field(alias="packAmount")
    duration_seconds: PositiveInt | None = Field(default=None, alias="durationSeconds")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    prices: list[GoodsPrice]


class GoodsList(ApiModel):
    data: list[GoodsListItem]
    total: NonNegativeInt


class GoodsDetail(ApiModel):
    goods_uuid: UUID = Field(alias="goodsUuid")
    type: str
    name: str
    is_available: bool = Field(alias="isAvailable")
    is_item: bool = Field(alias="isItem")
    is_sold_out: bool = Field(alias="isSoldOut")
    pack_amount: NonNegativeInt = Field(alias="packAmount")
    duration_seconds: PositiveInt | None = Field(default=None, alias="durationSeconds")
    prices: list[GoodsPrice]


class CatalogCore(ApiModel):
    uuid: UUID
    goods_type: str = Field(alias="goodsType")
    name: str
    is_available: bool = Field(alias="isAvailable")
    is_item: bool = Field(alias="isItem")


class ItemConfig(ApiModel):
    class_: str = Field(alias="class")
    display_type: str = Field(alias="displayType")


class SubscriptionConfig(ApiModel):
    duration_seconds: PositiveInt = Field(alias="durationSeconds")


class BoosterConfig(ApiModel):
    booster_type: str = Field(alias="boosterType")
    power_percent: Annotated[int, Field(gt=0)] = Field(alias="powerPercent")
    duration_seconds: PositiveInt = Field(alias="durationSeconds")


class CatalogConfig(ApiModel):
    kind: str
    item: ItemConfig | None = None
    subscription: SubscriptionConfig | None = None
    booster: BoosterConfig | None = None


class CatalogItem(ApiModel):
    core: CatalogCore
    config: CatalogConfig


class CatalogSummary(ApiModel):
    uuid: UUID
    goods_type: str = Field(alias="goodsType")
    name: str
    is_available: bool = Field(alias="isAvailable")
    is_item: bool = Field(alias="isItem")
    updated_at: datetime = Field(alias="updatedAt")


class CatalogItems(ApiModel):
    data: list[CatalogSummary]
    total: NonNegativeInt


class GoodsGrantResponse(ApiModel):
    success: bool
    quantity: PositiveInt
