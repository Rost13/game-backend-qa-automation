from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import httpx

from qa_automation.clients.base import ApiClient


class AdsClient:
    """HTTP facade for the published Ads Service API."""

    def __init__(self, transport: ApiClient, ads_path: str) -> None:
        self._transport = transport
        self._ads_path = ads_path.rstrip("/")

    def get_config(
        self,
        user_id: str | UUID | None,
        *,
        platform: str | None = None,
        authenticated: bool = False,
    ) -> httpx.Response:
        params: dict[str, str] = {}
        if user_id is not None:
            params["user_id"] = str(user_id)
        if platform is not None:
            params["platform"] = platform
        return self._transport.request(
            "GET", self._path("config"), authenticated=authenticated, params=params
        )

    def get_status(
        self,
        user_id: str | UUID | None,
        *,
        authenticated: bool = False,
    ) -> httpx.Response:
        params = {} if user_id is None else {"user_id": str(user_id)}
        return self._transport.request(
            "GET", self._path("status"), authenticated=authenticated, params=params
        )

    def get_availability(
        self,
        client_session_id: str | UUID | None,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        params = {} if client_session_id is None else {"client_session_id": str(client_session_id)}
        return self._transport.request(
            "GET",
            self._path("rewarded/availability"),
            authenticated=authenticated,
            params=params,
        )

    def start_rewarded_ad(
        self,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "POST",
            self._path("rewarded/start"),
            authenticated=authenticated,
            json_body=payload,
        )

    def get_placement(
        self,
        placement_token: str | UUID,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "GET",
            self._path(f"rewarded/placements/{placement_token}"),
            authenticated=authenticated,
        )

    def applovin_callback(self, params: Mapping[str, str | int]) -> httpx.Response:
        return self._transport.request(
            "GET",
            self._path("applovin/rewarded-callback"),
            authenticated=False,
            params=params,
        )

    def unity_callback(self, params: Mapping[str, str | int]) -> httpx.Response:
        return self._transport.request(
            "GET",
            self._path("unity/rewarded-callback"),
            authenticated=False,
            params=params,
        )

    def admin_get_global_config(self, *, authenticated: bool = True) -> httpx.Response:
        return self._admin_request("GET", "global-config", authenticated=authenticated)

    def admin_patch_global_config(
        self,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "PATCH", "global-config", authenticated=authenticated, json_body=payload
        )

    def admin_upsert_global_config(
        self,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "PUT", "global-config", authenticated=authenticated, json_body=payload
        )

    def admin_list_providers(self, *, authenticated: bool = True) -> httpx.Response:
        return self._admin_request("GET", "providers", authenticated=authenticated)

    def admin_get_provider(
        self, provider_code: str, *, authenticated: bool = True
    ) -> httpx.Response:
        return self._admin_request("GET", f"providers/{provider_code}", authenticated=authenticated)

    def admin_create_provider(
        self,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "POST", "providers", authenticated=authenticated, json_body=payload
        )

    def admin_patch_provider(
        self,
        provider_code: str,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "PATCH",
            f"providers/{provider_code}",
            authenticated=authenticated,
            json_body=payload,
        )

    def admin_upsert_provider(
        self,
        provider_code: str,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "PUT",
            f"providers/{provider_code}",
            authenticated=authenticated,
            json_body=payload,
        )

    def admin_list_sources(self, *, authenticated: bool = True) -> httpx.Response:
        return self._admin_request("GET", "sources", authenticated=authenticated)

    def admin_get_source(self, source_code: str, *, authenticated: bool = True) -> httpx.Response:
        return self._admin_request("GET", f"sources/{source_code}", authenticated=authenticated)

    def admin_create_source(
        self,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "POST", "sources", authenticated=authenticated, json_body=payload
        )

    def admin_patch_source(
        self,
        source_code: str,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "PATCH",
            f"sources/{source_code}",
            authenticated=authenticated,
            json_body=payload,
        )

    def admin_upsert_source(
        self,
        source_code: str,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "PUT",
            f"sources/{source_code}",
            authenticated=authenticated,
            json_body=payload,
        )

    def admin_list_source_providers(
        self,
        *,
        authenticated: bool = True,
        **filters: str | int | bool,
    ) -> httpx.Response:
        return self._admin_request(
            "GET", "source-providers", authenticated=authenticated, params=filters
        )

    def admin_get_source_provider(
        self,
        source_provider_id: str | UUID,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "GET", f"source-providers/{source_provider_id}", authenticated=authenticated
        )

    def admin_create_source_provider(
        self,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "POST", "source-providers", authenticated=authenticated, json_body=payload
        )

    def admin_patch_source_provider(
        self,
        source_provider_id: str | UUID,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "PATCH",
            f"source-providers/{source_provider_id}",
            authenticated=authenticated,
            json_body=payload,
        )

    def admin_upsert_source_provider(
        self,
        source_provider_id: str | UUID,
        payload: Mapping[str, object],
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._admin_request(
            "PUT",
            f"source-providers/{source_provider_id}",
            authenticated=authenticated,
            json_body=payload,
        )

    def admin_list_views(
        self,
        *,
        authenticated: bool = True,
        **filters: str | int,
    ) -> httpx.Response:
        return self._admin_request("GET", "views", authenticated=authenticated, params=filters)

    def admin_get_view(
        self, placement_token: str | UUID, *, authenticated: bool = True
    ) -> httpx.Response:
        return self._admin_request("GET", f"views/{placement_token}", authenticated=authenticated)

    def admin_get_view_reward_attempts(
        self, placement_token: str | UUID, *, authenticated: bool = True
    ) -> httpx.Response:
        return self._admin_request(
            "GET", f"views/{placement_token}/reward-attempts", authenticated=authenticated
        )

    def admin_get_user_summary(
        self, account_uuid: str | UUID, *, authenticated: bool = True
    ) -> httpx.Response:
        return self._admin_request(
            "GET", f"users/{account_uuid}/summary", authenticated=authenticated
        )

    def admin_get_user_views(
        self, account_uuid: str | UUID, *, authenticated: bool = True
    ) -> httpx.Response:
        return self._admin_request(
            "GET", f"users/{account_uuid}/views", authenticated=authenticated
        )

    def admin_get_user_limits(
        self, account_uuid: str | UUID, *, authenticated: bool = True
    ) -> httpx.Response:
        return self._admin_request(
            "GET", f"users/{account_uuid}/limits", authenticated=authenticated
        )

    def admin_get_user_reward_attempts(
        self, account_uuid: str | UUID, *, authenticated: bool = True
    ) -> httpx.Response:
        return self._admin_request(
            "GET", f"users/{account_uuid}/reward-attempts", authenticated=authenticated
        )

    def admin_get_stats(self, dimension: str, *, authenticated: bool = True) -> httpx.Response:
        return self._admin_request("GET", f"stats/{dimension}", authenticated=authenticated)

    def _path(self, suffix: str) -> str:
        return f"{self._ads_path}/{suffix.lstrip('/')}"

    def _admin_request(
        self,
        method: str,
        suffix: str,
        *,
        authenticated: bool,
        params: Mapping[str, str | int | bool] | None = None,
        json_body: Mapping[str, object] | None = None,
    ) -> httpx.Response:
        return self._transport.request(
            method,
            self._path(f"admin/{suffix}"),
            authenticated=authenticated,
            params=params,
            json_body=json_body,
        )
