from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from qa_automation.models.common import ApiModel

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class AdConfig(ApiModel):
    provider: str
    user_id: str
    platform: Literal["android", "ios"]
    ad_unit_id: str
    placement: str
    custom_data: str
    reward_amount: NonNegativeInt
    reward_currency: str
    callback_url: str


class UserAdStatus(ApiModel):
    user_id: str
    reward_balance: NonNegativeInt
    processed_count: NonNegativeInt


class GlobalAvailability(ApiModel):
    enabled: bool
    daily_limit: NonNegativeInt
    daily_used: NonNegativeInt
    daily_remaining: NonNegativeInt
    session_limit: NonNegativeInt
    session_used: NonNegativeInt
    session_remaining: NonNegativeInt
    cooldown_until: datetime | None
    disabled_reason: str | None


class SourceLimits(ApiModel):
    daily_limit: NonNegativeInt
    daily_used: NonNegativeInt
    daily_remaining: NonNegativeInt
    cooldown_until: datetime | None


class ProviderOptionLimits(SourceLimits):
    pass


class ProviderOptionAvailability(ApiModel):
    source_provider_id: UUID
    provider_code: str
    ad_unit_id: str
    available: bool
    priority: int
    limits: ProviderOptionLimits
    disabled_reason: str | None


class SourceAvailability(ApiModel):
    source_code: str
    client_location: str
    ad_format: str
    available: bool
    reward_type: str
    reward_preview: dict[str, object]
    limits: SourceLimits
    provider_options: list[ProviderOptionAvailability]
    requires_context: bool
    disabled_reason: str | None


class Availability(ApiModel):
    global_: GlobalAvailability = Field(alias="global")
    sources: list[SourceAvailability]


class StartAdResponse(ApiModel):
    placement_token: UUID
    source_code: str
    source_provider_id: UUID
    ad_format: str
    provider_code: str
    ad_unit_id: str
    user_id: UUID
    custom_data: str
    start_expires_at: datetime
    callback_accept_until: datetime


class PlacementState(ApiModel):
    placement_token: UUID
    source_code: str
    status: Literal["requested", "callback_received", "rewarding", "rewarded", "rejected", "failed"]
    rewarded_at: datetime | None = None
    reject_reason: str | None


class RewardStatus(ApiModel):
    status: str
    event_id: str
    user_id: UUID
    amount: int | None = None
    currency: str | None = None
    balance: int | None = None


class AdminAdProvider(ApiModel):
    provider_code: str
    enabled: bool
    callback_path: str
    validation_mode: str
    created_at: datetime
    updated_at: datetime


class AdminAdProviders(ApiModel):
    items: list[AdminAdProvider]
    total: NonNegativeInt


class AdminRewardedSource(ApiModel):
    source_code: str
    enabled: bool
    ad_format: str
    provider_code: str
    ad_unit_id: str
    platform_ad_unit_ids: dict[str, str]
    cooldown_sec: NonNegativeInt
    daily_limit_24h: NonNegativeInt
    reward_type: str
    reward_payload: dict[str, object]
    priority: int
    client_location: str
    requires_context: bool
    context_schema: dict[str, object] | None = None
    min_app_version: str | None
    platforms: list[str]
    created_at: datetime
    updated_at: datetime


class AdminRewardedSources(ApiModel):
    items: list[AdminRewardedSource]
    total: NonNegativeInt


class AdminSourceProvider(ApiModel):
    source_provider_id: UUID
    source_code: str
    provider_code: str
    ad_unit_id: str
    allowed_login_providers: list[str]
    enabled: bool
    priority: int
    daily_limit_24h: NonNegativeInt
    session_limit: NonNegativeInt
    cooldown_sec: NonNegativeInt
    min_app_version: str | None
    created_at: datetime
    updated_at: datetime


class AdminSourceProviders(ApiModel):
    items: list[AdminSourceProvider]
    total: NonNegativeInt


class AdminGlobalConfig(ApiModel):
    enabled: bool
    daily_limit_24h: NonNegativeInt
    session_limit: NonNegativeInt
    cooldown_sec: NonNegativeInt
    session_inactivity_threshold_sec: NonNegativeInt
    created_at: datetime
    updated_at: datetime


class AdminRewardedAdView(ApiModel):
    id: UUID
    placement_token: UUID
    account_uuid: UUID
    source_code: str
    reward_context_key: str | None
    provider_code: str
    ad_format: str
    client_session_id: UUID
    status: str
    ad_unit_id: str
    provider_transaction_id: str | None
    provider_event_token: str | None
    reward_type: str
    reward_payload_snapshot: dict[str, object]
    context: dict[str, object]
    raw_callback: dict[str, object] | None = None
    reject_reason: str | None
    started_at: datetime
    callback_received_at: datetime | None
    rewarded_at: datetime | None
    failed_at: datetime | None
    start_expires_at: datetime
    callback_accept_until: datetime


class AdminRewardedAdViews(ApiModel):
    items: list[AdminRewardedAdView]
    total: NonNegativeInt


class AdminRewardIssueAttempt(ApiModel):
    id: UUID
    view_id: UUID
    idempotency_key: str
    reward_type: str
    target_service: str
    request_payload: dict[str, object]
    response_payload: dict[str, object] | None = None
    status: str
    error: str | None
    created_at: datetime
    updated_at: datetime


class AdminRewardIssueAttempts(ApiModel):
    items: list[AdminRewardIssueAttempt]
    total: NonNegativeInt


class AdminRewardedStatsSummary(ApiModel):
    views_total: NonNegativeInt
    callbacks_received: NonNegativeInt
    rewarded: NonNegativeInt
    rejected: NonNegativeInt
    failed: NonNegativeInt
    reward_attempts_total: NonNegativeInt
    reward_attempts_failed: NonNegativeInt


class AdminRewardedGroupStat(ApiModel):
    key: str
    total: NonNegativeInt


class AdminRewardedGroupStats(ApiModel):
    items: list[AdminRewardedGroupStat]
    total: NonNegativeInt


class AdminUserDiagnostics(ApiModel):
    account_uuid: UUID
    summary: AdminRewardedStatsSummary
    by_source: list[AdminRewardedGroupStat]
    by_provider: list[AdminRewardedGroupStat]
    by_reject_reason: list[AdminRewardedGroupStat]
    recent_views: list[AdminRewardedAdView]
