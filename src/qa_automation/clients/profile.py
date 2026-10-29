from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import httpx

from qa_automation.clients.base import ApiClient


class ProfileClient:
    def __init__(self, transport: ApiClient, profile_path: str) -> None:
        self._transport = transport
        self._path = profile_path.rstrip("/")

    def get_me(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request("GET", f"{self._path}/me", authenticated=authenticated)

    def get_profile(
        self, account_uuid: UUID | str, *, authenticated: bool = True
    ) -> httpx.Response:
        return self._transport.request(
            "GET", f"{self._path}/{account_uuid}", authenticated=authenticated
        )

    def get_statistics(self) -> httpx.Response:
        return self._transport.request("GET", f"{self._path}/statistics", authenticated=False)

    def get_settings(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request("GET", f"{self._path}/settings", authenticated=authenticated)

    def update_settings(
        self,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "PATCH",
            f"{self._path}/settings",
            authenticated=authenticated,
            json_body=payload,
        )

    def update_localization(
        self,
        locale: str | None,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        payload: dict[str, object] = {}
        if locale is not None:
            payload["locale"] = locale
        return self._transport.request(
            "POST",
            f"{self._path}/localization",
            authenticated=authenticated,
            json_body=payload,
        )

    def update_username(
        self,
        username: str | None,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        payload: dict[str, object] = {}
        if username is not None:
            payload["username"] = username
        return self._transport.request(
            "PUT",
            f"{self._path}/username",
            authenticated=authenticated,
            json_body=payload,
        )

    def get_referrals(
        self,
        *,
        limit: object | None = None,
        offset: object | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._path}/referrals",
            authenticated=authenticated,
            params=_pagination(limit, offset),
        )

    def restore_referral(
        self,
        referred_by: str | None,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        payload: dict[str, object] = {}
        if referred_by is not None:
            payload["referred_by"] = referred_by
        return self._transport.request(
            "POST",
            f"{self._path}/referrals/restore",
            authenticated=authenticated,
            json_body=payload,
        )

    def get_share_message(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request("GET", f"{self._path}/share", authenticated=authenticated)

    def get_room_share_message(
        self, room_id: object | None, *, authenticated: bool = True
    ) -> httpx.Response:
        params = {"room_id": str(room_id)} if room_id is not None else None
        return self._transport.request(
            "GET",
            f"{self._path}/share/room",
            authenticated=authenticated,
            params=params,
        )

    def get_team_share_message(
        self, team_id: object | None, *, authenticated: bool = True
    ) -> httpx.Response:
        params = {"team_id": str(team_id)} if team_id is not None else None
        return self._transport.request(
            "GET",
            f"{self._path}/share/team",
            authenticated=authenticated,
            params=params,
        )

    def get_context_info(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET", f"{self._path}/context/info", authenticated=authenticated
        )

    def admin_search(self, query: str | None, *, authenticated: bool = True) -> httpx.Response:
        params = {"q": query} if query is not None else None
        return self._transport.request(
            "GET",
            f"{self._path}/admin/search",
            authenticated=authenticated,
            params=params,
        )

    def admin_get_referrals(
        self,
        account_uuid: UUID | str,
        *,
        limit: object | None = None,
        offset: object | None = None,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._path}/admin/referrals/{account_uuid}",
            params=_pagination(limit, offset),
        )

    def admin_assign_referral(
        self,
        account_uuid: UUID | str,
        referred_by: str | None,
    ) -> httpx.Response:
        payload: dict[str, object] = {}
        if referred_by is not None:
            payload["referred_by"] = referred_by
        return self._transport.request(
            "POST",
            f"{self._path}/admin/referrals/{account_uuid}/assign",
            json_body=payload,
        )

    def admin_delete_referral(self, account_uuid: UUID | str) -> httpx.Response:
        return self._transport.request("DELETE", f"{self._path}/admin/referrals/{account_uuid}")

    def admin_ban(self, account_uuid: UUID | str) -> httpx.Response:
        return self._transport.request("POST", f"{self._path}/{account_uuid}/ban")

    def admin_unban(self, account_uuid: UUID | str) -> httpx.Response:
        return self._transport.request("POST", f"{self._path}/{account_uuid}/unban")

    def admin_delete_account(self, account_uuid: UUID | str) -> httpx.Response:
        return self._transport.request("POST", f"{self._path}/{account_uuid}/delete")

    def delete_me(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request("DELETE", f"{self._path}/me", authenticated=authenticated)

    def restore_me(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "POST", f"{self._path}/me/restore", authenticated=authenticated
        )

    def restore_documented_account(
        self, account_uuid: UUID | str, *, authenticated: bool = True
    ) -> httpx.Response:
        return self._transport.request(
            "POST",
            f"{self._path}/{account_uuid}/restore",
            authenticated=authenticated,
        )


def _pagination(limit: object | None, offset: object | None) -> dict[str, str]:
    params: dict[str, str] = {}
    if limit is not None:
        params["limit"] = str(limit)
    if offset is not None:
        params["offset"] = str(offset)
    return params
