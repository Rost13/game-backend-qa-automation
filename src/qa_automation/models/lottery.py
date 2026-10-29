from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from qa_automation.models.common import ApiModel

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]


class RewardConfig(ApiModel):
    id: str
    type: str
    payload: dict[str, object] | None = None
    display_metadata: dict[str, object] | None = None
    probability: NonNegativeFloat
    weight: NonNegativeInt


class ChestConfig(ApiModel):
    id: str
    name: str
    active: bool
    asset_ids: list[str]
    cost_keys: NonNegativeInt
    reward_pool: list[RewardConfig]
    sort_order: int


class ThemeConfig(ApiModel):
    id: str
    asset_ids: list[str]


class SeasonConfig(ApiModel):
    id: str
    name: str
    starts_at: datetime
    ends_at: datetime
    theme: ThemeConfig
    chests: list[ChestConfig]


class LotteryConfig(ApiModel):
    max_open_quantity: NonNegativeInt
    seasons: list[SeasonConfig]


class LotteryResponse(ApiModel):
    config_version: PositiveInt
    keys_balance: NonNegativeInt
    season: SeasonConfig | None


class OpeningResult(ApiModel):
    open_index: NonNegativeInt
    opening_id: UUID
    reward_id: str
    reward_payload: dict[str, object] | None = None
    reward_probability: NonNegativeFloat
    reward_type: str


class OpenChestResponse(ApiModel):
    chest_id: str
    config_version: PositiveInt
    open_batch_id: UUID
    openings: list[OpeningResult]
    quantity: PositiveInt
    season_id: str
    total_cost_keys: NonNegativeInt


class Opening(ApiModel):
    account_uuid: UUID
    chest_id: str
    cost_keys: NonNegativeInt
    created_at: datetime
    open_batch_id: UUID
    open_index: NonNegativeInt
    opening_id: UUID
    reward_id: str
    reward_payload: dict[str, object] | None = None
    reward_probability: NonNegativeFloat
    reward_type: str
    season_id: str
    status: str


class ListOpeningsResponse(ApiModel):
    items: list[Opening]
    next_cursor: str | None = None


class ConfigVersion(ApiModel):
    config: LotteryConfig
    created_at: datetime
    created_by: str
    published_at: datetime | None = None
    published_by: str | None = None
    status: str
    updated_at: datetime
    validation_errors: list[str] | None = None
    version: PositiveInt


class ListConfigsResponse(ApiModel):
    items: list[ConfigVersion]
    next_cursor: NonNegativeInt | None = None


class ProbabilitiesResponse(ApiModel):
    config: LotteryConfig
    version: PositiveInt
