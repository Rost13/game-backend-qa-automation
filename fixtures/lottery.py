from __future__ import annotations

from collections.abc import Iterator

import pytest

from qa_automation.clients.base import ApiClient
from qa_automation.clients.lottery import LotteryClient
from qa_automation.config import Settings


def _lottery_client(settings: Settings, token: str) -> Iterator[LotteryClient]:
    assert settings.lottery_base_url is not None
    assert settings.lottery_api_path is not None
    transport = ApiClient(str(settings.lottery_base_url), token, settings.timeout_seconds)
    yield LotteryClient(transport, settings.lottery_api_path)
    transport.close()


@pytest.fixture(scope="session")
def lottery_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_lottery_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Lottery configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


@pytest.fixture(scope="session")
def lottery_user_client(lottery_live_settings: Settings) -> Iterator[LotteryClient]:
    assert lottery_live_settings.user_bearer_token is not None
    yield from _lottery_client(lottery_live_settings, lottery_live_settings.user_bearer_token)


@pytest.fixture(scope="session")
def lottery_admin_client(lottery_live_settings: Settings) -> Iterator[LotteryClient]:
    missing = lottery_live_settings.missing_lottery_admin_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Lottery admin configuration: {', '.join(missing)}",
            pytrace=False,
        )
    assert lottery_live_settings.admin_bearer_token is not None
    yield from _lottery_client(lottery_live_settings, lottery_live_settings.admin_bearer_token)


@pytest.fixture(scope="session")
def lottery_opening_settings(lottery_live_settings: Settings) -> Settings:
    if not lottery_live_settings.lottery_openings_enabled:
        pytest.skip("Lottery openings are disabled; set LOTTERY_OPENINGS_ENABLED=true")
    missing = lottery_live_settings.missing_lottery_opening_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Lottery opening configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return lottery_live_settings


@pytest.fixture(scope="session")
def lottery_config_mutation_settings(lottery_live_settings: Settings) -> Settings:
    if not lottery_live_settings.lottery_config_mutations_enabled:
        pytest.skip(
            "Lottery config mutations are disabled; set LOTTERY_CONFIG_MUTATIONS_ENABLED=true"
        )
    return lottery_live_settings
