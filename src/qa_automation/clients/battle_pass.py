from __future__ import annotations

from uuid import UUID

import httpx

from qa_automation.clients.base import ApiClient


class BattlePassClient:
    def __init__(self, transport: ApiClient, battle_pass_path: str) -> None:
        self._transport = transport
        self._battle_pass_path = battle_pass_path.rstrip("/")

    def get_config(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request("GET", self._path("config"), authenticated=authenticated)

    def get_active(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request("GET", self._path("active"), authenticated=authenticated)

    def get_banner(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request("GET", self._path("banner"), authenticated=authenticated)

    def get_archive_rewards(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET", self._path("archive/rewards"), authenticated=authenticated
        )

    def claim_reward(
        self,
        season_uuid: UUID | str,
        track: str,
        level: object,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "POST",
            self._path(f"seasons/{season_uuid}/tracks/{track}/levels/{level}/claim"),
            authenticated=authenticated,
        )

    def claim_all_rewards(
        self,
        season_uuid: UUID | str,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "POST",
            self._path(f"seasons/{season_uuid}/rewards/claim-all"),
            authenticated=authenticated,
        )

    def claim_all_archive_rewards(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "POST",
            self._path("archive/rewards/claim-all"),
            authenticated=authenticated,
        )

    def add_test_xp(
        self,
        xp: object,
        idempotency_key: str,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        return self._transport.request(
            "POST",
            self._path("test/xp/add"),
            authenticated=authenticated,
            json_body={"xp": xp, "idempotency_key": idempotency_key},
        )

    def reset_test_user(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "POST",
            self._path("test/reset"),
            authenticated=authenticated,
        )

    def _path(self, suffix: str) -> str:
        return f"{self._battle_pass_path}/{suffix}"
