from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import httpx

from qa_automation.clients.base import ApiClient


class BalanceClient:
    def __init__(self, transport: ApiClient, balance_path: str) -> None:
        self._transport = transport
        self._balance_path = balance_path.rstrip("/")

    def get_balance(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request("GET", self._balance_path, authenticated=authenticated)

    def get_history(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        currency: str | None = None,
        transaction_type: str | None = None,
    ) -> httpx.Response:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if currency is not None:
            params["currency"] = currency
        if transaction_type is not None:
            params["type"] = transaction_type
        return self._transport.request("GET", f"{self._balance_path}/history", params=params)

    def get_referral_status(self) -> httpx.Response:
        return self._transport.request("GET", f"{self._balance_path}/referrals/status")

    def get_invited_referrals(self, *, limit: int = 20, offset: int = 0) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._balance_path}/referrals/invited",
            params={"limit": limit, "offset": offset},
        )

    def get_balance_by_uuid(self, user_uuid: UUID | str) -> httpx.Response:
        return self._transport.request("GET", f"{self._balance_path}/{user_uuid}")

    def get_referral_status_by_uuid(self, user_uuid: UUID | str) -> httpx.Response:
        return self._transport.request("GET", f"{self._balance_path}/referrals/{user_uuid}/status")

    def get_invited_referrals_by_uuid(
        self,
        user_uuid: UUID | str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._balance_path}/referrals/{user_uuid}/invited",
            params={"limit": limit, "offset": offset},
        )

    def replenish(self, payload: Mapping[str, object]) -> httpx.Response:
        return self._transport.request("POST", f"{self._balance_path}/replenish", json_body=payload)

    def backfill_referrals(self, payload: Mapping[str, object]) -> httpx.Response:
        return self._transport.request(
            "POST", f"{self._balance_path}/referrals/backfill", json_body=payload
        )
