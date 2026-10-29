from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import ConfigDict, Field

from qa_automation.models.common import ApiModel

PurchaseStatus = Literal[
    "created",
    "price_calculated",
    "cancelled",
    "pxg_debited",
    "delivery_requested",
    "completed",
    "delivery_failed",
    "refund_pending",
    "refunded",
]
MarketStatus = Literal["created", "reserved", "held", "transferred", "completed", "failed"]


class CatalogItem(ApiModel):
    product_id: str
    def_uuid: str
    name_key: str | None = None
    description_key: str | None = None
    ton_amount: Decimal
    pxg_amount: Decimal
    available: bool


class CatalogResponse(ApiModel):
    items: list[CatalogItem]


class PublishedCatalogResponse(ApiModel):
    """Catalog success envelope declared by the published OpenAPI document."""

    model_config = ConfigDict(extra="forbid")
    ok: Literal[True]
    data: CatalogResponse
    error_description: str | None = None


class PurchaseResponse(ApiModel):
    purchase_id: str | None = None
    product_id: str | None = None
    def_uuid: str | None = None
    status: PurchaseStatus | None = None
    market_status: MarketStatus | None = None
    market_order_uid: str | None = None
    pxg_amount: Decimal | None = None
    quoted_ton_amount: Decimal | None = None
    settled_ton_amount: Decimal | None = None
    commission_ton_amount: Decimal | None = None
    total_debit_ton_amount: Decimal | None = None
    ton_usd_rate: Decimal | None = None
    pxg_per_usd: Decimal | None = None
    failure_reason: str | None = Field(default=None, repr=False)
    last_error: str | None = Field(default=None, repr=False)
    created_at: str | None = None
    updated_at: str | None = None


class MarketProxyServiceError(ApiModel):
    """Error envelope declared by the shared server.ApiResponse schema."""

    model_config = ConfigDict(extra="forbid")
    ok: Literal[False]
    error_description: str
    data: object | None = None
