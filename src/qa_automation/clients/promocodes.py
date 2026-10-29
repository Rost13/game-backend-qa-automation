from __future__ import annotations

from collections.abc import Mapping

import httpx

from qa_automation.clients.base import ApiClient


class PromocodesClient:
    def __init__(self, transport: ApiClient, promo_path: str) -> None:
        self._transport = transport
        self._promo_path = promo_path.rstrip("/")

    def list_promos(
        self,
        *,
        offset: int = 0,
        limit: int = 10,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            self._promo_path,
            authenticated=authenticated,
            params={"offset": offset, "limit": limit},
        )

    def upsert(self, payload: Mapping[str, object]) -> httpx.Response:
        return self._transport.request("POST", self._promo_path, json_body=payload)

    def activate(self, promo_uuid: str) -> httpx.Response:
        return self._set_active("activate", promo_uuid)

    def deactivate(self, promo_uuid: str) -> httpx.Response:
        return self._set_active("deactivate", promo_uuid)

    def apply(self, code: str) -> httpx.Response:
        return self._transport.request(
            "POST",
            f"{self._promo_path}/apply",
            json_body={"code": code},
        )

    def _set_active(self, action: str, promo_uuid: str) -> httpx.Response:
        return self._transport.request(
            "POST",
            f"{self._promo_path}/{action}",
            json_body={"promo_uuid": promo_uuid},
        )
