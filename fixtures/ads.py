from __future__ import annotations

from collections.abc import Iterator

import pytest

from qa_automation.clients.ads import AdsClient
from qa_automation.clients.base import ApiClient
from qa_automation.config import Settings


def _ads_client(settings: Settings, token: str) -> Iterator[AdsClient]:
    assert settings.ads_base_url is not None
    assert settings.ads_api_path is not None
    transport = ApiClient(
        str(settings.ads_base_url),
        token,
        settings.timeout_seconds,
    )
    yield AdsClient(transport, settings.ads_api_path)
    transport.close()


@pytest.fixture(scope="session")
def ads_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_ads_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Ads Service configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


@pytest.fixture(scope="session")
def ads_user_client(ads_live_settings: Settings) -> Iterator[AdsClient]:
    assert ads_live_settings.user_bearer_token is not None
    yield from _ads_client(ads_live_settings, ads_live_settings.user_bearer_token)


@pytest.fixture(scope="session")
def ads_admin_client(ads_live_settings: Settings) -> Iterator[AdsClient]:
    if ads_live_settings.admin_bearer_token is None:
        pytest.fail("ENVIRONMENT_DEFECT: API_ADMIN_BEARER_TOKEN is not configured", pytrace=False)
    yield from _ads_client(ads_live_settings, ads_live_settings.admin_bearer_token)


@pytest.fixture(scope="session")
def ads_start_settings(ads_live_settings: Settings) -> Settings:
    if not ads_live_settings.ads_starts_enabled:
        pytest.skip("Ads placement creation is disabled; set ADS_STARTS_ENABLED=true")
    return ads_live_settings


@pytest.fixture(scope="session")
def ads_admin_mutation_settings(ads_live_settings: Settings) -> Settings:
    if not ads_live_settings.ads_admin_mutations_enabled:
        pytest.skip("Ads admin mutations are disabled; set ADS_ADMIN_MUTATIONS_ENABLED=true")
    missing = ads_live_settings.missing_ads_admin_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Ads admin configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return ads_live_settings


@pytest.fixture(scope="session")
def ads_callback_settings(ads_live_settings: Settings) -> Settings:
    if not ads_live_settings.ads_callbacks_enabled:
        pytest.skip("Ads callbacks are disabled; set ADS_CALLBACKS_ENABLED=true")
    missing = ads_live_settings.missing_ads_callback_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Ads callback configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return ads_live_settings
