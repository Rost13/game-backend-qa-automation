from __future__ import annotations

from collections.abc import Iterator

import pytest

from qa_automation.clients.base import ApiClient
from qa_automation.clients.battle_pass import BattlePassClient
from qa_automation.config import Settings


@pytest.fixture(scope="session")
def battle_pass_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_battle_pass_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Battle Pass configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


@pytest.fixture(scope="session")
def battle_pass_user_client(
    battle_pass_live_settings: Settings,
) -> Iterator[BattlePassClient]:
    assert battle_pass_live_settings.battle_pass_base_url is not None
    assert battle_pass_live_settings.battle_pass_api_path is not None
    assert battle_pass_live_settings.user_bearer_token is not None
    transport = ApiClient(
        base_url=str(battle_pass_live_settings.battle_pass_base_url),
        bearer_token=battle_pass_live_settings.user_bearer_token,
        timeout_seconds=battle_pass_live_settings.timeout_seconds,
    )
    yield BattlePassClient(transport, battle_pass_live_settings.battle_pass_api_path)
    transport.close()


@pytest.fixture(scope="session")
def battle_pass_mutation_settings(battle_pass_live_settings: Settings) -> Settings:
    if not battle_pass_live_settings.battle_pass_mutations_enabled:
        pytest.skip("Battle Pass mutations are disabled; set BATTLE_PASS_MUTATIONS_ENABLED=true")
    return battle_pass_live_settings
