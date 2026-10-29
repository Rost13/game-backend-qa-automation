from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest
from psycopg import Error as PostgresError

from qa_automation.auth import jwt_subject
from qa_automation.clients.balance import BalanceClient
from qa_automation.clients.base import ApiClient
from qa_automation.config import Settings
from qa_automation.db.balance import BalanceDatabase
from qa_automation.db.kubernetes import KubectlPostgresTunnel, KubernetesDatabaseError
from qa_automation.diagnostics import exception_type_name


@pytest.fixture(scope="session")
def balance_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_balance_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Balance configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


def _balance_client(settings: Settings, bearer_token: str) -> Iterator[BalanceClient]:
    assert settings.balance_base_url is not None
    assert settings.balance_api_path is not None
    transport = ApiClient(
        base_url=str(settings.balance_base_url),
        bearer_token=bearer_token,
        timeout_seconds=settings.timeout_seconds,
    )
    yield BalanceClient(transport, settings.balance_api_path)
    transport.close()


@pytest.fixture(scope="session")
def balance_user_client(balance_live_settings: Settings) -> Iterator[BalanceClient]:
    assert balance_live_settings.user_bearer_token is not None
    yield from _balance_client(balance_live_settings, balance_live_settings.user_bearer_token)


@pytest.fixture(scope="session")
def balance_admin_client(balance_live_settings: Settings) -> Iterator[BalanceClient]:
    missing = balance_live_settings.missing_balance_admin_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Balance admin configuration: {', '.join(missing)}",
            pytrace=False,
        )
    assert balance_live_settings.admin_bearer_token is not None
    yield from _balance_client(balance_live_settings, balance_live_settings.admin_bearer_token)


@pytest.fixture(scope="session")
def balance_test_user_uuid(balance_live_settings: Settings) -> UUID:
    assert balance_live_settings.user_bearer_token is not None
    try:
        return jwt_subject(balance_live_settings.user_bearer_token)
    except ValueError as error:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: invalid Balance test-user JWT ({exception_type_name(error)})",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def balance_admin_uuid(balance_live_settings: Settings) -> UUID:
    assert balance_live_settings.admin_bearer_token is not None
    try:
        return jwt_subject(balance_live_settings.admin_bearer_token)
    except ValueError as error:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: invalid Balance admin JWT ({exception_type_name(error)})",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def balance_mutation_settings(balance_live_settings: Settings) -> Settings:
    if not balance_live_settings.balance_mutations_enabled:
        pytest.skip("Balance mutations are disabled; set BALANCE_MUTATIONS_ENABLED=true")
    return balance_live_settings


def _open_balance_database(settings: Settings) -> BalanceDatabase:
    missing = settings.missing_balance_database_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Balance database configuration: {', '.join(missing)}",
            pytrace=False,
        )
    try:
        return BalanceDatabase(settings)
    except (PostgresError, OSError, ValueError) as error:
        pytest.fail(
            "ENVIRONMENT_DEFECT: Balance PostgreSQL connection failed "
            f"({exception_type_name(error)})",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def balance_database_settings(balance_live_settings: Settings) -> Iterator[Settings | None]:
    if not balance_live_settings.balance_db_assertions_enabled:
        yield None
        return

    if not balance_live_settings.balance_db_kube_forward_enabled:
        yield balance_live_settings
        return

    missing = balance_live_settings.missing_balance_kubernetes_database_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Balance Kubernetes configuration: {', '.join(missing)}",
            pytrace=False,
        )
    try:
        with KubectlPostgresTunnel(
            balance_live_settings,
            database_service="balance",
        ) as forwarded_settings:
            yield forwarded_settings
    except KubernetesDatabaseError as error:
        pytest.fail(
            "INFRASTRUCTURE_DEFECT: Balance Kubernetes PostgreSQL tunnel failed "
            f"({exception_type_name(error)})",
            pytrace=False,
        )


@pytest.fixture
def required_balance_database(
    balance_database_settings: Settings | None,
) -> Iterator[BalanceDatabase]:
    if balance_database_settings is None:
        pytest.skip("Balance DB assertions are disabled; set BALANCE_DB_ASSERTIONS_ENABLED=true")
    database = _open_balance_database(balance_database_settings)
    yield database
    database.close()
