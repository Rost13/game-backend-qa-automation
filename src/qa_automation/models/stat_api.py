from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from qa_automation.models.common import ApiModel

NonNegativeInt = Annotated[int, Field(ge=0)]
LeaderboardRange = Literal["day", "week", "month"]


class StatStatus(ApiModel):
    status: Literal["ok"]


class StatSummary(ApiModel):
    wins: NonNegativeInt
    defeats: NonNegativeInt
    draws: NonNegativeInt
    winrate: int
    matches: NonNegativeInt
    accuracy: int
    headshots: int
    kills: NonNegativeInt
    deaths: NonNegativeInt
    killrate: int
    period_start: datetime
    period_end: datetime


class MatchesPlayed(ApiModel):
    matches_played: NonNegativeInt


class MatchHistoryItem(ApiModel):
    finished_at: datetime
    kills: NonNegativeInt
    map_id: str
    mode: str
    result: str
    started_at: datetime


class StatHistory(ApiModel):
    matches: list[MatchHistoryItem]
    total: NonNegativeInt


class PlayerLeaderboardEntry(ApiModel):
    uuid: UUID
    nickname: str
    image_url: str
    mask_image_url: str
    level: NonNegativeInt
    place: NonNegativeInt
    points: NonNegativeInt
    fee_percent: int
    has_premium: bool


class PlayerLeaderboardList(ApiModel):
    page: int
    players: list[PlayerLeaderboardEntry]
    total: NonNegativeInt


class PlayerLeaderboard(ApiModel):
    list: PlayerLeaderboardList
    range: LeaderboardRange
    user: PlayerLeaderboardEntry | None = None


class PlayerLeaderboardResponse(ApiModel):
    leaderboard: PlayerLeaderboard


class SquadLeaderboardEntry(ApiModel):
    avatar: str
    members_amount: NonNegativeInt
    name: str
    place: NonNegativeInt
    points: NonNegativeInt
    squad_id: int


class SquadLeaderboardList(ApiModel):
    page: int
    squads: list[SquadLeaderboardEntry]
    total: NonNegativeInt


class SquadLeaderboard(ApiModel):
    list: SquadLeaderboardList
    range: LeaderboardRange
    squad: SquadLeaderboardEntry | None = None


class SquadLeaderboardResponse(ApiModel):
    leaderboard: SquadLeaderboard


class TeamLeaderboardEntry(ApiModel):
    avatar: str
    name: str
    place: NonNegativeInt
    points: NonNegativeInt
    team_id: int


class TeamLeaderboardList(ApiModel):
    page: int
    teams: list[TeamLeaderboardEntry]
    total: NonNegativeInt


class TeamLeaderboard(ApiModel):
    list: TeamLeaderboardList
    range: LeaderboardRange
    team: TeamLeaderboardEntry | None = None


class TeamLeaderboardResponse(ApiModel):
    leaderboard: TeamLeaderboard


class ClanWarsTeam(ApiModel):
    avatar: str
    id: int
    name: str


class ClanWarsMap(ApiModel):
    map_id: str
    owner: ClanWarsTeam | None = None
    resolution_status: Literal["pending"] | None = None
    segment_ends_at: datetime
    segment_started_at: datetime
    segment_type: Literal["neutral", "battle", "ownership"]


class ClanWarsMapsResponse(ApiModel):
    maps: list[ClanWarsMap]
