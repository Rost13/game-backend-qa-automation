from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from qa_automation.models.common import ApiModel

NonNegativeInt = Annotated[int, Field(ge=0)]
Currency = Literal["hard", "soft", "xp", "keys"]
Event = Literal["spend", "receive"]
PXG_MINOR_UNITS = 100


class BalanceResponse(ApiModel):
    soft: NonNegativeInt | None = None
    xp: NonNegativeInt | None = None
    hard: NonNegativeInt | None = None
    keys: NonNegativeInt | None = None
    hard_display: Decimal | None = None
    offline_rewards: dict[str, NonNegativeInt] | None = None


class PublishedBalanceResponse(ApiModel):
    """Exact response body currently declared for GET /api/v2/balance in OpenAPI."""

    model_config = ConfigDict(extra="forbid")

    soft: NonNegativeInt | None = None
    xp: NonNegativeInt | None = None
    hard: NonNegativeInt | None = None
    hard_display: str | None = None
    offline_rewards: dict[str, NonNegativeInt] | None = None


class HistoryMeta(ApiModel):
    limit: NonNegativeInt
    offset: NonNegativeInt


class Transaction(ApiModel):
    id: str | None = None
    uid: str | None = None
    event: Event | None = None
    currency: Currency | None = None
    amount: NonNegativeInt | None = None
    source_type: str | None = None
    source_id: str | None = None
    created_at: str | None = None
    ts: str | None = None
    amount_display: str | None = None
    hard_display: str | None = None


class HistoryResponse(ApiModel):
    items: list[Transaction]
    meta: HistoryMeta


class ReferralRewardPreview(ApiModel):
    description_short: str | None = None
    icon_url: str | None = None
    title: str | None = None
    type: str | None = None


class ReferralMilestone(ApiModel):
    count: NonNegativeInt
    id: str
    reward_preview: ReferralRewardPreview | None = None
    state: Literal["LOCKED", "NEXT", "CLAIMED"]


class ReferralNextMilestone(ApiModel):
    count: NonNegativeInt
    id: str


class ReferralStatusResponse(ApiModel):
    milestones: list[ReferralMilestone]
    next_milestone: ReferralNextMilestone | None = None
    qualified_count: NonNegativeInt
    ref_code: str | None = None
    ref_url: str | None = None


class ReferralBalances(ApiModel):
    xp: NonNegativeInt | None = None


class ReferralInvitedItem(ApiModel):
    avatar_url: str | None = None
    balances: ReferralBalances | None = None
    invited_at: str | None = None
    qualified_at: str | None = None
    user_uuid: str | None = None
    username: str | None = None


class ReferralInvitedResponse(ApiModel):
    items: list[ReferralInvitedItem]
    total: NonNegativeInt


class BalanceServiceError(ApiModel):
    code: str
    message: str
    err: object | None = None


class ReplenishResponse(ApiModel):
    message: str
