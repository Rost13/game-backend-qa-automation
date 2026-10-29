from __future__ import annotations

import httpx

from qa_automation.clients.base import ApiClient


class MarketProxyClient:
    def __init__(self, transport: ApiClient, market_path: str) -> None:
        self._transport = transport
        self._market_path = market_path.rstrip("/")

    def get_catalog(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._market_path}/catalog",
            authenticated=authenticated,
        )

    def create_purchase(
        self,
        product_id: str | None,
        *,
        idempotency_key: str | None,
        authenticated: bool = True,
    ) -> httpx.Response:
        payload: dict[str, object] = {}
        if product_id is not None:
            payload["product_id"] = product_id
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key is not None else None
        return self._transport.request(
            "POST",
            f"{self._market_path}/purchases",
            authenticated=authenticated,
            json_body=payload,
            headers=headers,
        )

    def get_purchase(
        self,
        purchase_id: str,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._market_path}/purchases/{purchase_id}",
            authenticated=authenticated,
        )
