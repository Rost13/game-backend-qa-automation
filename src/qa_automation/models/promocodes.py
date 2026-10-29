from __future__ import annotations

from typing import Literal
from uuid import UUID

from qa_automation.models.common import ApiModel


class Promo(ApiModel):
    uuid: UUID
    code: str
    type: Literal["CAMPAIGN", "INFLUENCER"]
    is_active: bool
    reward_currency: str
    reward_amount: int | None = None
    reward_items: list[str] | None = None
    max_claims: int | None = None
    claims_used: int | None = None
    start_at_ms: int | None = None
    expire_at_ms: int | None = None
    influencer_uuid: UUID | None = None


class ListPromosResponse(ApiModel):
    items: list[Promo]
    total: int
    limit: int
    offset: int


class UpsertPromoResponse(ApiModel):
    promo_uuid: UUID
    code: str
    created: bool


class SetActivePromoResponse(ApiModel):
    promo_uuid: UUID
    is_active: bool
    changed: bool
    message: str


class ApplyPromoResponse(ApiModel):
    promo_uuid: UUID
    code: str
    reward_currency: str | None = None
    reward_amount: int | None = None
    reward_items: list[str] | None = None
    referral_applied: bool


class ServiceError(ApiModel):
    code: str
    message: str
    err: object | None = None
