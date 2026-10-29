from __future__ import annotations

import httpx

from qa_automation.clients.base import ApiClient


class SocialClient:
    def __init__(self, transport: ApiClient, social_path: str) -> None:
        self._transport = transport
        self._social_path = social_path.rstrip("/")

    def get_friends(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._social_path}/friends",
            authenticated=authenticated,
            params=_pagination_params(cursor=cursor, limit=limit),
        )

    def delete_friend(self, player_id: str, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "DELETE",
            f"{self._social_path}/friends/{player_id}",
            authenticated=authenticated,
        )

    def send_friend_request(
        self,
        target_player_id: str | None,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        payload: dict[str, object] = {}
        if target_player_id is not None:
            payload["target_player_id"] = target_player_id
        return self._transport.request(
            "POST",
            f"{self._social_path}/friend-requests",
            authenticated=authenticated,
            json_body=payload,
        )

    def get_incoming_requests(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._social_path}/friend-requests/incoming",
            authenticated=authenticated,
            params=_pagination_params(cursor=cursor, limit=limit),
        )

    def get_outgoing_requests(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._social_path}/friend-requests/outgoing",
            authenticated=authenticated,
            params=_pagination_params(cursor=cursor, limit=limit),
        )

    def accept_request(self, request_id: str, *, authenticated: bool = True) -> httpx.Response:
        return self._request_action(request_id, "accept", authenticated=authenticated)

    def decline_request(self, request_id: str, *, authenticated: bool = True) -> httpx.Response:
        return self._request_action(request_id, "decline", authenticated=authenticated)

    def cancel_request(self, request_id: str, *, authenticated: bool = True) -> httpx.Response:
        return self._request_action(request_id, "cancel", authenticated=authenticated)

    def heartbeat(
        self,
        *,
        party_id: str | None = None,
        match_id: str | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        payload: dict[str, object] = {}
        if party_id is not None:
            payload["party_id"] = party_id
        if match_id is not None:
            payload["match_id"] = match_id
        return self._transport.request(
            "POST",
            f"{self._social_path}/presence/heartbeat",
            authenticated=authenticated,
            json_body=payload,
        )

    def set_offline(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "POST",
            f"{self._social_path}/presence/offline",
            authenticated=authenticated,
        )

    def get_recommendations(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._social_path}/friend-recommendations",
            authenticated=authenticated,
        )

    def _request_action(
        self,
        request_id: str,
        action: str,
        *,
        authenticated: bool,
    ) -> httpx.Response:
        return self._transport.request(
            "POST",
            f"{self._social_path}/friend-requests/{request_id}/{action}",
            authenticated=authenticated,
        )


def _pagination_params(*, cursor: str | None, limit: int | None) -> dict[str, str | int]:
    params: dict[str, str | int] = {}
    if cursor is not None:
        params["cursor"] = cursor
    if limit is not None:
        params["limit"] = limit
    return params
