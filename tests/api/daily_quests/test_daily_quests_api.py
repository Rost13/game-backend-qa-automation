from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import allure
import httpx
import pytest

from qa_automation.clients.base import assert_response_status, validate_response_model
from qa_automation.clients.daily_quests import DailyQuestsClient
from qa_automation.models.daily_quests import (
    DailyQuestsConfigResponse,
    DailyQuestsResponse,
    DailyRewardsState,
    ReadyClaimCountResponse,
)

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Daily Quests")]

UnauthenticatedCall = Callable[[DailyQuestsClient], httpx.Response]


def _get_quests_without_auth(client: DailyQuestsClient) -> httpx.Response:
    return client.get_quests(authenticated=False)


def _claim_quest_without_auth(client: DailyQuestsClient) -> httpx.Response:
    return client.claim_quest(str(uuid4()), authenticated=False)


def _get_config_without_auth(client: DailyQuestsClient) -> httpx.Response:
    return client.get_config(authenticated=False)


def _get_ready_count_without_auth(client: DailyQuestsClient) -> httpx.Response:
    return client.get_ready_claim_count(authenticated=False)


def _get_daily_rewards_without_auth(client: DailyQuestsClient) -> httpx.Response:
    return client.get_daily_rewards(authenticated=False)


def _claim_daily_reward_without_auth(client: DailyQuestsClient) -> httpx.Response:
    return client.claim_daily_reward(1, 1, authenticated=False)


def _progress_daily_reward_without_auth(client: DailyQuestsClient) -> httpx.Response:
    return client.mark_daily_reward_progress(authenticated=False)


@allure.title("Daily Quests endpoint requires authentication: {operation}")
@pytest.mark.smoke
@pytest.mark.parametrize(
    ("operation", "call"),
    [
        ("get quests", _get_quests_without_auth),
        ("claim quest", _claim_quest_without_auth),
        ("get config", _get_config_without_auth),
        ("get ready claim count", _get_ready_count_without_auth),
        ("get daily rewards", _get_daily_rewards_without_auth),
        ("claim daily reward", _claim_daily_reward_without_auth),
        ("mark daily reward progress", _progress_daily_reward_without_auth),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_daily_quests_endpoint_requires_authentication(
    daily_quests_user_client: DailyQuestsClient,
    operation: str,
    call: UnauthenticatedCall,
) -> None:
    response = call(daily_quests_user_client)

    assert_response_status(response, 401)


@allure.title("User receives valid active daily quests")
@pytest.mark.smoke
@pytest.mark.contract
def test_user_can_get_active_daily_quests(
    daily_quests_user_client: DailyQuestsClient,
) -> None:
    response = daily_quests_user_client.get_quests()

    assert_response_status(response, 200)
    result = validate_response_model(response, DailyQuestsResponse)
    quest_ids = [quest.quest_uuid for quest in result.quests]
    assert len(quest_ids) == len(set(quest_ids)), "quest_uuid values must be unique"
    for quest in result.quests:
        assert quest.description.strip(), "quest description must not be blank"
        assert quest.created_at < quest.expired_at
        if quest.reward.issued:
            assert quest.progress.current >= quest.progress.target, (
                "an issued quest reward must belong to a completed quest"
            )


@allure.title("Daily quest configuration contains valid unique templates")
@pytest.mark.smoke
@pytest.mark.contract
def test_user_can_get_daily_quest_config(
    daily_quests_user_client: DailyQuestsClient,
) -> None:
    response = daily_quests_user_client.get_config()

    assert_response_status(response, 200)
    result = validate_response_model(response, DailyQuestsConfigResponse)
    assert result.quest_templates, "TEST_DATA_DEFECT: Daily Quests config has no templates"
    template_ids = [template.template_uuid for template in result.quest_templates]
    assert len(template_ids) == len(set(template_ids)), "template_uuid values must be unique"
    for template in result.quest_templates:
        assert template.description.strip(), "quest template description must not be blank"
        assert len(template.whitelist) == len(set(template.whitelist))


@allure.title("Ready claim count equals the number of completed unclaimed quests")
@pytest.mark.regression
def test_ready_claim_count_matches_daily_quest_state(
    daily_quests_user_client: DailyQuestsClient,
) -> None:
    quests_response = daily_quests_user_client.get_quests()
    count_response = daily_quests_user_client.get_ready_claim_count()

    assert_response_status(quests_response, 200)
    assert_response_status(count_response, 200)
    quests = validate_response_model(quests_response, DailyQuestsResponse)
    count = validate_response_model(count_response, ReadyClaimCountResponse)
    expected = sum(
        not quest.reward.issued and quest.progress.current >= quest.progress.target
        for quest in quests.quests
    )
    assert count.ready_claim_count == expected


@allure.title("User receives a consistent weekly daily-reward state")
@pytest.mark.smoke
@pytest.mark.contract
def test_user_can_get_consistent_daily_rewards_state(
    daily_quests_user_client: DailyQuestsClient,
) -> None:
    response = daily_quests_user_client.get_daily_rewards()

    assert_response_status(response, 200)
    state = validate_response_model(response, DailyRewardsState)
    _assert_daily_rewards_state(state)


@allure.title("Quest claim rejects invalid quest_uuid: {case}")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("case", "quest_uuid"),
    [
        ("missing", None),
        ("malformed", "not-a-uuid"),
        ("wrong type", 123),
    ],
)
def test_quest_claim_rejects_invalid_quest_uuid(
    daily_quests_user_client: DailyQuestsClient,
    case: str,
    quest_uuid: object | None,
) -> None:
    response = daily_quests_user_client.claim_quest(quest_uuid)

    assert_response_status(response, 400)


@allure.title("Quest claim returns not found for an unknown quest")
@pytest.mark.regression
def test_quest_claim_returns_not_found_for_unknown_quest(
    daily_quests_user_client: DailyQuestsClient,
) -> None:
    response = daily_quests_user_client.claim_quest(str(uuid4()))

    assert_response_status(response, 404)


@allure.title("Daily reward claim validates week and day: {case}")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("case", "week", "day"),
    [
        ("missing week", None, 1),
        ("missing day", 1, None),
        ("zero week", 0, 1),
        ("zero day", 1, 0),
        ("day above seven", 1, 8),
        ("invalid week type", "one", 1),
    ],
)
def test_daily_reward_claim_rejects_invalid_week_or_day(
    daily_quests_user_client: DailyQuestsClient,
    case: str,
    week: object | None,
    day: object | None,
) -> None:
    response = daily_quests_user_client.claim_daily_reward(week, day)

    assert_response_status(response, 400)


@allure.title("A locked daily reward cannot be claimed")
@pytest.mark.regression
def test_locked_daily_reward_cannot_be_claimed(
    daily_quests_user_client: DailyQuestsClient,
) -> None:
    before_response = daily_quests_user_client.get_daily_rewards()
    assert_response_status(before_response, 200)
    before = validate_response_model(before_response, DailyRewardsState)
    locked = next((reward for reward in before.rewards if reward.status == "locked"), None)
    if locked is None:
        pytest.skip("TEST_DATA_DEFECT: current daily-reward state has no locked slot")

    claim_response = daily_quests_user_client.claim_daily_reward(locked.week, locked.day)
    after_response = daily_quests_user_client.get_daily_rewards()

    assert_response_status(claim_response, 400)
    assert_response_status(after_response, 200)
    after = validate_response_model(after_response, DailyRewardsState)
    assert _reward_state_fingerprint(after) == _reward_state_fingerprint(before)


def _assert_daily_rewards_state(state: DailyRewardsState) -> None:
    assert state.completed is state.is_config_completed
    positions = [(reward.week, reward.day) for reward in state.rewards]
    assert positions == sorted(positions), "daily rewards must be ordered by week and day"
    assert len(positions) == len(set(positions)), "daily reward week/day values must be unique"
    current_position = (state.current_week, state.current_day)
    for reward in state.rewards:
        unlocked = (reward.week, reward.day) <= current_position
        assert (reward.status != "locked") is unlocked
        assert reward.reward_type.strip(), "daily reward type must not be blank"
    assert state.has_available_rewards is any(
        reward.status == "available" for reward in state.rewards
    )
    assert state.is_visible is (bool(state.rewards) and not state.is_config_completed)


def _reward_state_fingerprint(state: DailyRewardsState) -> tuple[object, ...]:
    return (
        state.current_week,
        state.current_day,
        state.streak_total_day,
        state.completed,
        state.is_visible,
        state.has_available_rewards,
        state.is_config_completed,
        [(reward.week, reward.day, reward.status) for reward in state.rewards],
    )
