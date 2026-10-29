from __future__ import annotations

from collections.abc import Iterator

import pytest

from qa_automation.clients.base import ApiClient
from qa_automation.clients.boosters import BoostersClient
from qa_automation.config import Settings


def _client(settings: Settings, token: str) -> Iterator[BoostersClient]:
    assert settings.boosters_base_url is not None
    assert settings.boosters_api_path is not None
    transport = ApiClient(str(settings.boosters_base_url), token, settings.timeout_seconds)
    yield BoostersClient(transport, settings.boosters_api_path)
    transport.close()


@pytest.fixture(scope="session")
def boosters_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_boosters_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Boosters configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


@pytest.fixture(scope="session")
def boosters_user_client(boosters_live_settings: Settings) -> Iterator[BoostersClient]:
    assert boosters_live_settings.user_bearer_token is not None
    yield from _client(boosters_live_settings, boosters_live_settings.user_bearer_token)


@pytest.fixture(scope="session")
def boosters_admin_client(boosters_live_settings: Settings) -> Iterator[BoostersClient]:
    if boosters_live_settings.admin_bearer_token is None:
        pytest.fail("ENVIRONMENT_DEFECT: API_ADMIN_BEARER_TOKEN is not configured", pytrace=False)
    yield from _client(boosters_live_settings, boosters_live_settings.admin_bearer_token)


@pytest.fixture(scope="session")
def booster_grant_settings(boosters_live_settings: Settings) -> Settings:
    if not boosters_live_settings.booster_grants_enabled:
        pytest.skip("Booster grants are disabled; set BOOSTER_GRANTS_ENABLED=true")
    missing = boosters_live_settings.missing_booster_grant_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Booster grant configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return boosters_live_settings
