from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from qa_automation.models.common import ApiModel

Timestamp = Annotated[int, Field(ge=0)]
PlayerLevel = Annotated[int, Field(ge=0)]


class Presence(ApiModel):
    status: str | None = None
    last_seen_at: Timestamp | None = None
    party_id: str | None = None
    match_id: str | None = None


class FriendItem(ApiModel):
    player_id: UUID
    nickname: str
    avatar: str | None = None
    player_level: PlayerLevel
    online: bool
    presence: Presence | None = None
    friends_since: Timestamp


class PaginatedFriendsResponse(ApiModel):
    items: list[FriendItem]
    next_cursor: str | None = None


FriendRequestStatus = Literal["pending", "accepted", "declined", "cancelled"]


class FriendRequestItem(ApiModel):
    id: UUID
    requester_id: UUID
    addressee_id: UUID
    status: FriendRequestStatus
    created_at: Timestamp
    peer_nickname: str
    peer_avatar: str | None = None


class PaginatedFriendRequestsResponse(ApiModel):
    items: list[FriendRequestItem]
    next_cursor: str | None = None


class FriendRequestCreatedResponse(ApiModel):
    id: UUID
    status: FriendRequestStatus
    created_at: Timestamp


class RecommendationItem(ApiModel):
    player_id: UUID
    nickname: str
    avatar: str | None = None
    player_level: PlayerLevel
    reason: str
    online: bool


class RecommendationsResponse(ApiModel):
    items: list[RecommendationItem]


class StatusResponse(ApiModel):
    status: str
    id: UUID | None = None
    accepted_at: Timestamp | None = None


class SocialErrorBody(ApiModel):
    code: str
    message: str


class PublishedSocialErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: SocialErrorBody | None = None


class PublishedPaginatedFriendsResponse(PaginatedFriendsResponse):
    """Exact top-level response currently declared by the Social OpenAPI document."""

    model_config = ConfigDict(extra="forbid")


class PublishedPaginatedFriendRequestsResponse(PaginatedFriendRequestsResponse):
    """Exact top-level response currently declared by the Social OpenAPI document."""

    model_config = ConfigDict(extra="forbid")


class PublishedRecommendationsResponse(RecommendationsResponse):
    """Exact top-level response currently declared by the Social OpenAPI document."""

    model_config = ConfigDict(extra="forbid")
