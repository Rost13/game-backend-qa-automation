from __future__ import annotations

from collections.abc import Iterator

import pytest

from qa_automation.clients.base import ApiClient
from qa_automation.clients.profile import ProfileClient
from qa_automation.config import Settings


def _profile_client(settings: Settings, token: str) -> Iterator[ProfileClient]:
    assert settings.profile_base_url is not None
    assert settings.profile_api_path is not None
    transport = ApiClient(
        str(settings.profile_base_url),
        token,
        settings.timeout_seconds,
    )
    yield ProfileClient(transport, settings.profile_api_path)
    transport.close()


@pytest.fixture(scope="session")
def profile_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_profile_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Profile configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


@pytest.fixture(scope="session")
def profile_user_client(profile_live_settings: Settings) -> Iterator[ProfileClient]:
    assert profile_live_settings.user_bearer_token is not None
    yield from _profile_client(profile_live_settings, profile_live_settings.user_bearer_token)


@pytest.fixture(scope="session")
def profile_admin_client(profile_live_settings: Settings) -> Iterator[ProfileClient]:
    if profile_live_settings.admin_bearer_token is None:
        pytest.fail("ENVIRONMENT_DEFECT: API_ADMIN_BEARER_TOKEN is not configured", pytrace=False)
    yield from _profile_client(profile_live_settings, profile_live_settings.admin_bearer_token)


@pytest.fixture(scope="session")
def profile_share_client(profile_live_settings: Settings) -> Iterator[ProfileClient]:
    if profile_live_settings.profile_share_token is None:
        pytest.skip(
            "TEST_DATA_DEFECT: positive share checks require "
            "PROFILE_SHARE_BEARER_TOKEN for a Telegram-linked account"
        )
    yield from _profile_client(profile_live_settings, profile_live_settings.profile_share_token)


@pytest.fixture(scope="session")
def profile_mutation_settings(profile_live_settings: Settings) -> Settings:
    if not profile_live_settings.profile_mutations_enabled:
        pytest.skip("Profile mutations are disabled; set PROFILE_MUTATIONS_ENABLED=true")
    return profile_live_settings


@pytest.fixture(scope="session")
def premium_grant_settings(profile_live_settings: Settings) -> Settings:
    if not profile_live_settings.premium_grants_enabled:
        pytest.skip("Premium grants are disabled; set PREMIUM_GRANTS_ENABLED=true")
    missing = profile_live_settings.missing_premium_grant_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Premium grant configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return profile_live_settings
