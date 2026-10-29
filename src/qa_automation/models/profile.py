from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, RootModel

from qa_automation.models.common import ApiModel

NonNegativeInt = Annotated[int, Field(ge=0)]


class Squad(ApiModel):
    id: int | None = None
    logo: str | None = None
    name: str | None = None
    slug: str | None = None


class PublishedSquad(ApiModel):
    id: int
    logo: str
    name: str
    slug: str


class PremiumState(ApiModel):
    active: bool
    expiration: datetime | None = None


class Profile(ApiModel):
    account_uuid: UUID
    username: str
    first_name: str
    last_name: str
    locale: str
    avatar: str
    created_at: datetime
    deleted_at: datetime | None
    is_guest: bool
    squad: Squad | None = None
    premium: PremiumState


class PublishedProfile(ApiModel):
    account_uuid: UUID
    username: str
    first_name: str
    last_name: str
    locale: str
    avatar: str
    created_at: datetime
    deleted_at: datetime | None
    is_guest: bool
    squad: PublishedSquad | None = None
    premium: PremiumState


class PublicProfile(ApiModel):
    account_uuid: UUID
    username: str
    first_name: str
    last_name: str
    locale: str
    avatar: str
    created_at: datetime
    is_guest: bool
    squad: Squad | None = None
    premium: PremiumState | None = None


class ProfileStatistics(ApiModel):
    total_players: NonNegativeInt


class ProfileSettings(ApiModel):
    version: NonNegativeInt
    updated_at: datetime | None = None
    settings: dict[str, Any]


class ReferralBalances(ApiModel):
    xp: NonNegativeInt


class Referral(ApiModel):
    account_uuid: UUID
    username: str
    first_name: str
    last_name: str
    locale: str
    avatar: str
    created_at: datetime
    balances: ReferralBalances


class ReferralsPage(ApiModel):
    referrals: list[Referral]
    total: NonNegativeInt
    limit: Annotated[int, Field(ge=1, le=50)]
    offset: NonNegativeInt
    reward_counter: NonNegativeInt


class PreparedShareMessage(ApiModel):
    prepared_message_id: str


class LocalizationResponse(ApiModel):
    locale: str


class UsernameResponse(ApiModel):
    username: str
    success: bool


class ProfileContextResponse(ApiModel):
    ok: Literal[True]


class ProfileSearchResults(RootModel[list[PublicProfile]]):
    pass


class ProfileServiceError(ApiModel):
    code: str
    message: str
    err: object | None = None
