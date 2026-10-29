from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import httpx

from qa_automation.clients.base import ApiClient


class StatApiClient:
    def __init__(self, transport: ApiClient, stat_path: str) -> None:
        self._transport = transport
        self._path = stat_path.rstrip("/")

    def get_summary(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request("GET", f"{self._path}/summary", authenticated=authenticated)

    def get_matches_played(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET", f"{self._path}/matches-played", authenticated=authenticated
        )

    def get_history(
        self,
        *,
        period: str | None = None,
        limit: object | None = None,
        offset: object | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        params = _pagination_params(period=period, limit=limit, offset=offset)
        return self._transport.request(
            "GET",
            f"{self._path}/history",
            authenticated=authenticated,
            params=params,
        )

    def get_admin_history(
        self,
        account_uuid: UUID | str | None,
        *,
        period: str | None = None,
        limit: object | None = None,
        offset: object | None = None,
    ) -> httpx.Response:
        params = _pagination_params(period=period, limit=limit, offset=offset)
        if account_uuid is not None:
            params["account_uuid"] = str(account_uuid)
        return self._transport.request("GET", f"{self._path}/admin/history", params=params)

    def get_players_leaderboard(
        self,
        *,
        range_: str | None = None,
        page: object | None = None,
        limit: object | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._leaderboard_request(
            "players", range_=range_, page=page, limit=limit, authenticated=authenticated
        )

    def get_squads_leaderboard(
        self,
        *,
        range_: str | None = None,
        page: object | None = None,
        limit: object | None = None,
        squad_id: object | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        params = _leaderboard_params(range_=range_, page=page, limit=limit)
        if squad_id is not None:
            params["squad_id"] = str(squad_id)
        return self._transport.request(
            "GET",
            f"{self._path}/leaderboard/squads",
            authenticated=authenticated,
            params=params,
        )

    def get_teams_leaderboard(
        self,
        *,
        range_: str | None = None,
        page: object | None = None,
        limit: object | None = None,
        team_id: object | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        params = _leaderboard_params(range_=range_, page=page, limit=limit)
        if team_id is not None:
            params["team_id"] = str(team_id)
        return self._transport.request(
            "GET",
            f"{self._path}/leaderboard/teams",
            authenticated=authenticated,
            params=params,
        )

    def get_clan_wars_maps(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET", f"{self._path}/clan-wars/maps", authenticated=authenticated
        )

    def send_client_event(
        self,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "POST",
            f"{self._path}/dreamcatcher/webhook",
            authenticated=authenticated,
            json_body=payload,
        )

    def _leaderboard_request(
        self,
        resource: str,
        *,
        range_: str | None,
        page: object | None,
        limit: object | None,
        authenticated: bool,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._path}/leaderboard/{resource}",
            authenticated=authenticated,
            params=_leaderboard_params(range_=range_, page=page, limit=limit),
        )


def _pagination_params(
    *, period: str | None, limit: object | None, offset: object | None
) -> dict[str, str]:
    params: dict[str, str] = {}
    if period is not None:
        params["period"] = period
    if limit is not None:
        params["limit"] = str(limit)
    if offset is not None:
        params["offset"] = str(offset)
    return params


def _leaderboard_params(
    *, range_: str | None, page: object | None, limit: object | None
) -> dict[str, str]:
    params: dict[str, str] = {}
    if range_ is not None:
        params["range"] = range_
    if page is not None:
        params["page"] = str(page)
    if limit is not None:
        params["limit"] = str(limit)
    return params
