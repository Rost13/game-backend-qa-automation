from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

from qa_automation.clients.base import ApiClient
from qa_automation.clients.stat_api import StatApiClient
from qa_automation.config import Settings
from qa_automation.db.clickhouse_kubernetes import KubectlClickHouseTunnel
from qa_automation.db.kubernetes import KubernetesDatabaseError
from qa_automation.db.stat_api import StatClickHouseDatabase
from qa_automation.diagnostics import exception_type_name


def _client(settings: Settings, token: str) -> Iterator[StatApiClient]:
    assert settings.stat_api_base_url is not None
    assert settings.stat_api_path is not None
    transport = ApiClient(str(settings.stat_api_base_url), token, settings.timeout_seconds)
    yield StatApiClient(transport, settings.stat_api_path)
    transport.close()


@pytest.fixture(scope="session")
def stat_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_stat_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Stat API configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


@pytest.fixture(scope="session")
def stat_user_client(stat_live_settings: Settings) -> Iterator[StatApiClient]:
    assert stat_live_settings.user_bearer_token is not None
    yield from _client(stat_live_settings, stat_live_settings.user_bearer_token)


@pytest.fixture(scope="session")
def stat_admin_client(stat_live_settings: Settings) -> Iterator[StatApiClient]:
    if stat_live_settings.admin_bearer_token is None:
        pytest.fail("ENVIRONMENT_DEFECT: API_ADMIN_BEARER_TOKEN is not configured", pytrace=False)
    yield from _client(stat_live_settings, stat_live_settings.admin_bearer_token)


@pytest.fixture(scope="session")
def stat_event_settings(stat_live_settings: Settings) -> Settings:
    if not stat_live_settings.stat_events_enabled:
        pytest.skip("Stat event writes are disabled; set STAT_EVENTS_ENABLED=true")
    return stat_live_settings


@pytest.fixture(scope="session")
def stat_clickhouse_settings(stat_live_settings: Settings) -> Iterator[Settings | None]:
    if not stat_live_settings.stat_clickhouse_assertions_enabled:
        yield None
        return

    if not stat_live_settings.stat_clickhouse_kube_forward_enabled:
        yield stat_live_settings
        return

    try:
        with KubectlClickHouseTunnel(stat_live_settings) as forwarded_settings:
            yield forwarded_settings
    except KubernetesDatabaseError as error:
        pytest.fail(
            f"INFRASTRUCTURE_DEFECT: Stat ClickHouse tunnel failed ({exception_type_name(error)})",
            pytrace=False,
        )


@pytest.fixture
def required_stat_database(
    stat_clickhouse_settings: Settings | None,
) -> Iterator[StatClickHouseDatabase]:
    if stat_clickhouse_settings is None:
        pytest.skip(
            "Stat ClickHouse assertions are disabled; set STAT_CLICKHOUSE_ASSERTIONS_ENABLED=true"
        )
    missing = stat_clickhouse_settings.missing_stat_clickhouse_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Stat ClickHouse configuration: {', '.join(missing)}",
            pytrace=False,
        )
    try:
        database = StatClickHouseDatabase(stat_clickhouse_settings)
    except (httpx.HTTPError, OSError, ValueError) as error:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: Stat ClickHouse connection failed ({exception_type_name(error)})",
            pytrace=False,
        )
    yield database
    database.close()
