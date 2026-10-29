from __future__ import annotations

from uuid import UUID

import httpx

from qa_automation.clients.base import ApiClient


class BoostersClient:
    def __init__(self, transport: ApiClient, boosters_path: str) -> None:
        self._transport = transport
        self._path = boosters_path.rstrip("/")

    def get_active(
        self, *, at_ms: object | None = None, authenticated: bool = True
    ) -> httpx.Response:
        params = None if at_ms is None else {"at_ms": str(at_ms)}
        return self._transport.request(
            "GET", self._path, authenticated=authenticated, params=params
        )

    def get_active_by_uuid(
        self, user_uuid: UUID | str, *, at_ms: object | None = None
    ) -> httpx.Response:
        params = None if at_ms is None else {"at_ms": str(at_ms)}
        return self._transport.request("GET", f"{self._path}/admin/{user_uuid}", params=params)

    def get_active_by_documented_path(self, user_uuid: UUID | str) -> httpx.Response:
        prefix = self._path.rsplit("/", 1)[0]
        return self._transport.request("GET", f"{prefix}/admin/boosters/{user_uuid}")
