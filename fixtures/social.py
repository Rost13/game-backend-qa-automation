from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest

from qa_automation.auth import jwt_subject
from qa_automation.clients.base import ApiClient
from qa_automation.clients.social import SocialClient
from qa_automation.config import Settings
from qa_automation.diagnostics import exception_type_name


@pytest.fixture(scope="session")
def social_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_social_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Social configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


def _social_client(settings: Settings, bearer_token: str) -> Iterator[SocialClient]:
    assert settings.social_base_url is not None
    assert settings.social_api_path is not None
    transport = ApiClient(
        base_url=str(settings.social_base_url),
        bearer_token=bearer_token,
        timeout_seconds=settings.timeout_seconds,
    )
    yield SocialClient(transport, settings.social_api_path)
    transport.close()


@pytest.fixture(scope="session")
def social_user_client(social_live_settings: Settings) -> Iterator[SocialClient]:
    assert social_live_settings.user_bearer_token is not None
    yield from _social_client(social_live_settings, social_live_settings.user_bearer_token)


@pytest.fixture(scope="session")
def social_user_uuid(social_live_settings: Settings) -> UUID:
    assert social_live_settings.user_bearer_token is not None
    try:
        return jwt_subject(social_live_settings.user_bearer_token)
    except ValueError as error:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: invalid Social test-user JWT ({exception_type_name(error)})",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def social_mutation_settings(social_live_settings: Settings) -> Settings:
    if not social_live_settings.social_mutations_enabled:
        pytest.skip("Social mutations are disabled; set SOCIAL_MUTATIONS_ENABLED=true")
    return social_live_settings


@pytest.fixture(scope="session")
def social_peer_settings(social_mutation_settings: Settings) -> Settings:
    missing = social_mutation_settings.missing_social_peer_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Social peer configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return social_mutation_settings


@pytest.fixture(scope="session")
def social_peer_client(social_peer_settings: Settings) -> Iterator[SocialClient]:
    assert social_peer_settings.social_peer_token is not None
    yield from _social_client(social_peer_settings, social_peer_settings.social_peer_token)


@pytest.fixture(scope="session")
def social_peer_uuid(social_peer_settings: Settings, social_user_uuid: UUID) -> UUID:
    assert social_peer_settings.social_peer_token is not None
    try:
        peer_uuid = jwt_subject(social_peer_settings.social_peer_token)
    except ValueError as error:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: invalid Social peer-user JWT ({exception_type_name(error)})",
            pytrace=False,
        )
    if peer_uuid == social_user_uuid:
        pytest.fail(
            "TEST_DATA_DEFECT: Social primary and peer tokens belong to the same user",
            pytrace=False,
        )
    return peer_uuid
