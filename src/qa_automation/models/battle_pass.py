from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from qa_automation.models.common import ApiModel

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Track = Literal["default", "premium"]


class Price(ApiModel):
    amount: NonNegativeInt
    currency: str
    icon_url: str


class PremiumOffer(ApiModel):
    title: str
    subtitle: str
    benefits: list[str]


class SeasonLevel(ApiModel):
    level: PositiveInt
    xp_from_previous: NonNegativeInt
    total_xp_required: NonNegativeInt
    id: PositiveInt


class RewardItem(ApiModel):
    id: PositiveInt
    type: str
    payload: dict[str, object]
    title: str
    description: str
    icon_url: str
    image_url: str
    tags: list[str]
    is_major: bool


class SeasonMetadata(ApiModel):
    uuid: UUID
    display: str
    title: str
    description: str
    status: Literal["active", "ended"]
    starts_at: datetime
    ends_at: datetime
    pass_icon_url: str
    background_image_url: str
    info_url: str


class Season(SeasonMetadata):
    premium_goods_uuid: str
    premium_price: Price
    premium_offer: PremiumOffer
    default_levels: list[SeasonLevel]
    premium_levels: list[SeasonLevel]


class BattlePassConfig(ApiModel):
    type: Literal["battlePass"]
    version: PositiveInt
    levels_count: PositiveInt
    seasons: list[Season]


class RewardsConfig(ApiModel):
    type: Literal["battlePassRewards"]
    version: PositiveInt
    items: list[RewardItem]


class PublicConfigResponse(ApiModel):
    enabled: bool
    battle_pass: BattlePassConfig | None = None
    rewards: RewardsConfig | None = None


class PlayerProgress(ApiModel):
    level: PositiveInt
    total_xp: NonNegativeInt
    has_premium: bool
    ready_to_claim_count: NonNegativeInt
    archive_reward_count: NonNegativeInt = 0


class LevelWithReward(ApiModel):
    level: PositiveInt
    xp_from_previous: NonNegativeInt
    total_xp_required: NonNegativeInt
    reward: RewardItem
    claimed: bool
    available: bool


class SeasonView(SeasonMetadata):
    premium_goods_uuid: str
    premium_price: Price
    premium_offer: PremiumOffer
    default_levels: list[LevelWithReward]
    premium_levels: list[LevelWithReward]
    progress: PlayerProgress


class BannerPlayer(ApiModel):
    level: PositiveInt
    ready_to_claim_count: NonNegativeInt
    has_premium: bool


class BannerView(ApiModel):
    season: SeasonMetadata
    player: BannerPlayer


class ClaimResult(ApiModel):
    season_uuid: UUID
    track: Track
    level: PositiveInt
    reward: RewardItem
    claimed: bool


class ClaimAllResult(ApiModel):
    season_uuid: UUID | None = None
    rewards: list[ClaimResult]


class ArchiveReward(ApiModel):
    season_uuid: UUID
    season_title: str
    track: Track
    level: PositiveInt
    reward: RewardItem
    available: bool


class ArchiveRewardsResponse(ApiModel):
    items: list[ArchiveReward]


class XPGrantResponse(ApiModel):
    progress: PlayerProgress
    applied: bool


class BattlePassError(ApiModel):
    error: str
