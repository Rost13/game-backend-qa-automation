from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest

from qa_automation.clients.balance import BalanceClient
from qa_automation.clients.base import ApiClient
from qa_automation.clients.daily_quests import DailyQuestsClient
from qa_automation.config import Settings


@pytest.fixture(scope="session")
def daily_quests_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_daily_quests_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Daily Quests configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


@pytest.fixture(scope="session")
def daily_quests_user_client(
    daily_quests_live_settings: Settings,
) -> Iterator[DailyQuestsClient]:
    assert daily_quests_live_settings.daily_quests_base_url is not None
    assert daily_quests_live_settings.daily_quests_api_path is not None
    assert daily_quests_live_settings.user_bearer_token is not None
    transport = ApiClient(
        base_url=str(daily_quests_live_settings.daily_quests_base_url),
        bearer_token=daily_quests_live_settings.user_bearer_token,
        timeout_seconds=daily_quests_live_settings.timeout_seconds,
    )
    yield DailyQuestsClient(transport, daily_quests_live_settings.daily_quests_api_path)
    transport.close()


@pytest.fixture(scope="session")
def daily_quest_claim_settings(daily_quests_live_settings: Settings) -> Settings:
    if not daily_quests_live_settings.daily_quest_claims_enabled:
        pytest.skip("Daily quest claim tests are disabled; set DAILY_QUEST_CLAIMS_ENABLED=true")
    return daily_quests_live_settings


@pytest.fixture(scope="session")
def daily_rewards_mutation_settings(daily_quests_live_settings: Settings) -> Settings:
    if not daily_quests_live_settings.daily_rewards_mutations_enabled:
        pytest.skip(
            "Daily reward mutation tests are disabled; set DAILY_REWARDS_MUTATIONS_ENABLED=true"
        )
    return daily_quests_live_settings


@pytest.fixture(scope="session")
def daily_quest_claim_balance_context(
    daily_quest_claim_settings: Settings,
    balance_admin_client: BalanceClient,
    balance_test_user_uuid: UUID,
) -> tuple[BalanceClient, UUID]:
    return balance_admin_client, balance_test_user_uuid


@pytest.fixture(scope="session")
def daily_reward_balance_context(
    daily_rewards_mutation_settings: Settings,
    balance_admin_client: BalanceClient,
    balance_test_user_uuid: UUID,
) -> tuple[BalanceClient, UUID]:
    return balance_admin_client, balance_test_user_uuid
