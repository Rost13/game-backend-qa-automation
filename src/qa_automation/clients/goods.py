from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import httpx

from qa_automation.clients.base import ApiClient


class GoodsClient:
    def __init__(self, transport: ApiClient, goods_path: str) -> None:
        self._transport = transport
        self._path = goods_path.rstrip("/")

    def get_goods(
        self,
        *,
        currency: str,
        goods_type: str | None = None,
        limit: object = 100,
        offset: object = 0,
        authenticated: bool = True,
    ) -> httpx.Response:
        params: dict[str, str] = {
            "currency": currency,
            "limit": str(limit),
            "offset": str(offset),
        }
        if goods_type is not None:
            params["type"] = goods_type
        return self._transport.request(
            "GET", self._path, authenticated=authenticated, params=params
        )

    def get_good(
        self, goods_uuid: UUID | str, *, currency: str, authenticated: bool = True
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._path}/{goods_uuid}",
            authenticated=authenticated,
            params={"currency": currency},
        )

    def get_catalog_items(
        self, *, goods_type: str | None = None, limit: int = 100, offset: int = 0
    ) -> httpx.Response:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if goods_type is not None:
            params["type"] = goods_type
        return self._transport.request("GET", f"{self._path}/admin/catalog/items", params=params)

    def get_catalog_item(self, goods_uuid: UUID | str) -> httpx.Response:
        return self._transport.request("GET", f"{self._path}/admin/catalog/items/{goods_uuid}")

    def admin_grant(self, payload: Mapping[str, object]) -> httpx.Response:
        return self._transport.request("POST", f"{self._path}/admin/grant", json_body=payload)
