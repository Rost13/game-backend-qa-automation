from __future__ import annotations

from collections.abc import Mapping

import httpx

from qa_automation.clients.base import ApiClient


class LotteryClient:
    def __init__(self, transport: ApiClient, lottery_path: str) -> None:
        self._transport = transport
        self._path = lottery_path.rstrip("/")

    def get_lottery(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request("GET", self._path, authenticated=authenticated)

    def list_openings(
        self,
        *,
        cursor: object | None = None,
        limit: object | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._path}/openings",
            authenticated=authenticated,
            params=_query_parameters(cursor=cursor, limit=limit),
        )

    def open_chest(
        self,
        chest_id: str,
        quantity: object | None,
        idempotency_key: str | None,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        payload: dict[str, object] = {}
        if quantity is not None:
            payload["quantity"] = quantity
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key is not None else None
        return self._transport.request(
            "POST",
            f"{self._path}/chests/{chest_id}/open",
            authenticated=authenticated,
            json_body=payload,
            headers=headers,
        )

    def list_configs(
        self,
        *,
        status: object | None = None,
        cursor: object | None = None,
        limit: object | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._path}/admin/configs",
            authenticated=authenticated,
            params=_query_parameters(status=status, cursor=cursor, limit=limit),
        )

    def create_config(
        self,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "POST",
            f"{self._path}/admin/configs",
            authenticated=authenticated,
            json_body=payload,
        )

    def get_config(self, version: object, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._path}/admin/configs/{version}",
            authenticated=authenticated,
        )

    def update_config(
        self,
        version: object,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "PUT",
            f"{self._path}/admin/configs/{version}",
            authenticated=authenticated,
            json_body=payload,
        )

    def archive_config(self, version: object, *, authenticated: bool = True) -> httpx.Response:
        return self._config_action(version, "archive", authenticated=authenticated)

    def clone_config(self, version: object, *, authenticated: bool = True) -> httpx.Response:
        return self._config_action(version, "clone", authenticated=authenticated)

    def get_probabilities(self, version: object, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._path}/admin/configs/{version}/probabilities",
            authenticated=authenticated,
        )

    def publish_config(self, version: object, *, authenticated: bool = True) -> httpx.Response:
        return self._config_action(version, "publish", authenticated=authenticated)

    def validate_config(self, version: object, *, authenticated: bool = True) -> httpx.Response:
        return self._config_action(version, "validate", authenticated=authenticated)

    def _config_action(
        self,
        version: object,
        action: str,
        *,
        authenticated: bool,
    ) -> httpx.Response:
        return self._transport.request(
            "POST",
            f"{self._path}/admin/configs/{version}/{action}",
            authenticated=authenticated,
        )


def _query_parameters(**values: object | None) -> dict[str, str]:
    return {name: str(value) for name, value in values.items() if value is not None}
