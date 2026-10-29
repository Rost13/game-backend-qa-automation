from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import httpx

from qa_automation.clients.base import ApiClient


class InventoryClient:
    def __init__(self, transport: ApiClient, inventory_path: str) -> None:
        self._transport = transport
        self._path = inventory_path.rstrip("/")

    def get_equipped(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request("GET", f"{self._path}/equipped", authenticated=authenticated)

    def get_guest_equipped(self) -> httpx.Response:
        return self._transport.request("GET", f"{self._path}/equipped/guest", authenticated=False)

    def get_items(
        self,
        category: str,
        item_class: str | None,
        *,
        sort: str | None = None,
        offset: object | None = None,
        limit: object | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        params: dict[str, str] = {}
        if item_class is not None:
            params["class"] = item_class
        if sort is not None:
            params["sort"] = sort
        if offset is not None:
            params["offset"] = str(offset)
        if limit is not None:
            params["limit"] = str(limit)
        return self._transport.request(
            "GET",
            f"{self._path}/{category}",
            authenticated=authenticated,
            params=params,
        )

    def get_items_by_uuid(
        self,
        category: str,
        user_uuid: UUID | str,
        item_class: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._path}/{category}/{user_uuid}",
            params={"class": item_class, "offset": offset, "limit": limit},
        )

    def get_guest_items(self, category: str) -> httpx.Response:
        return self._transport.request("GET", f"{self._path}/{category}/guest", authenticated=False)

    def get_documented_items(self, category: str, item_class: str) -> httpx.Response:
        return self._transport.request(
            "GET", f"{self._path}/items/{category}", params={"class": item_class}
        )

    def grant_item(
        self, payload: Mapping[str, object], *, authenticated: bool = True
    ) -> httpx.Response:
        return self._transport.request(
            "POST",
            f"{self._path}/admin/grant",
            authenticated=authenticated,
            json_body=payload,
        )
