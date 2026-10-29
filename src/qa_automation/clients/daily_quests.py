from __future__ import annotations

import httpx

from qa_automation.clients.base import ApiClient


class DailyQuestsClient:
    def __init__(self, transport: ApiClient, daily_quests_path: str) -> None:
        self._transport = transport
        self._daily_quests_path = daily_quests_path.rstrip("/")

    def get_quests(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET",
            self._daily_quests_path,
            authenticated=authenticated,
        )

    def claim_quest(
        self,
        quest_uuid: object | None,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        payload: dict[str, object] = {}
        if quest_uuid is not None:
            payload["quest_uuid"] = quest_uuid
        return self._transport.request(
            "POST",
            f"{self._daily_quests_path}/claim",
            authenticated=authenticated,
            json_body=payload,
        )

    def get_config(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._daily_quests_path}/config",
            authenticated=authenticated,
        )

    def get_ready_claim_count(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._daily_quests_path}/ready-claim-count",
            authenticated=authenticated,
        )

    def get_daily_rewards(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "GET",
            f"{self._daily_quests_path}/rewards",
            authenticated=authenticated,
        )

    def claim_daily_reward(
        self,
        week: object | None,
        day: object | None,
        *,
        authenticated: bool = True,
    ) -> httpx.Response:
        payload: dict[str, object] = {}
        if week is not None:
            payload["week"] = week
        if day is not None:
            payload["day"] = day
        return self._transport.request(
            "POST",
            f"{self._daily_quests_path}/rewards/claim",
            authenticated=authenticated,
            json_body=payload,
        )

    def mark_daily_reward_progress(self, *, authenticated: bool = True) -> httpx.Response:
        return self._transport.request(
            "POST",
            f"{self._daily_quests_path}/rewards/progress",
            authenticated=authenticated,
        )
