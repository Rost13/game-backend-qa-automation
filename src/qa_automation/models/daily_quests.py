from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from qa_automation.models.common import ApiModel

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]
DailyRewardDay = Annotated[int, Field(ge=1, le=7)]

QuestType = Literal["login", "map", "mode", "weapon", "weapon_id", "headshot_kill"]
QuestDifficulty = Literal["easy", "normal", "hard"]
DailyRewardStatus = Literal["locked", "available", "claimed"]


class QuestProgress(ApiModel):
    current: NonNegativeInt
    target: PositiveInt


class QuestReward(ApiModel):
    issued: bool
    xp: NonNegativeInt
    soft: NonNegativeInt
    pxg: NonNegativeDecimal
    keys: NonNegativeInt
    battle_pass_xp: NonNegativeInt


class Quest(ApiModel):
    quest_uuid: UUID
    quest_type: QuestType
    whitelist: str
    description: str
    created_at: datetime
    expired_at: datetime
    progress: QuestProgress
    reward: QuestReward


class DailyQuestsResponse(ApiModel):
    quests: list[Quest]


class QuestClaimReward(ApiModel):
    xp: NonNegativeInt
    soft: NonNegativeInt
    pxg: NonNegativeDecimal
    keys: NonNegativeInt
    battle_pass_xp: NonNegativeInt


class QuestClaimResponse(ApiModel):
    reward: QuestClaimReward


class QuestTemplate(ApiModel):
    template_uuid: UUID
    version: PositiveInt
    difficult: QuestDifficulty
    type: QuestType
    description: str
    whitelist: list[str]
    value: PositiveInt
    xp: NonNegativeInt
    soft: NonNegativeInt
    pxg: NonNegativeDecimal
    battle_pass_xp: NonNegativeInt | None = None


class DailyQuestsConfigResponse(ApiModel):
    quest_templates: list[QuestTemplate]


class ReadyClaimCountResponse(ApiModel):
    ready_claim_count: NonNegativeInt


class DailyRewardSlot(ApiModel):
    week: PositiveInt
    day: DailyRewardDay
    icon_url: str
    reward_type: str
    reward_payload: dict[str, object]
    status: DailyRewardStatus


class DailyRewardsState(ApiModel):
    current_week: PositiveInt
    current_day: Annotated[int, Field(ge=0, le=7)]
    streak_total_day: NonNegativeInt
    completed: bool
    is_visible: bool
    has_available_rewards: bool
    is_config_completed: bool
    next_reward_at: datetime | None
    rewards: list[DailyRewardSlot]


class DailyReward(ApiModel):
    week: PositiveInt
    day: DailyRewardDay
    icon_url: str
    reward_type: str
    reward_payload: dict[str, object]


class DailyRewardClaimResponse(ApiModel):
    reward: DailyReward
