from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from qa_automation.auth import jwt_subject, validate_disposable_account_target
from qa_automation.config import Settings, load_settings
from qa_automation.diagnostics import exception_type_name


@pytest.fixture(scope="session")
def qa_settings() -> Settings:
    try:
        return load_settings()
    except ValidationError as error:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: invalid test configuration ({exception_type_name(error)})",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")

    missing = qa_settings.missing_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing required configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


@pytest.fixture(scope="session")
def mutation_settings(live_settings: Settings) -> Settings:
    if not live_settings.promocodes_mutations_enabled:
        pytest.skip("Promocodes mutation tests are disabled; set PROMOCODES_MUTATIONS_ENABLED=true")
    return live_settings


@pytest.fixture(scope="session")
def api_test_user_uuid(qa_settings: Settings) -> UUID:
    if qa_settings.user_bearer_token is None:
        pytest.fail("ENVIRONMENT_DEFECT: API_BEARER_TOKEN is not configured", pytrace=False)
    try:
        return jwt_subject(qa_settings.user_bearer_token)
    except ValueError as error:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: invalid test-user JWT ({exception_type_name(error)})",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def destructive_rbac_target_uuid(qa_settings: Settings) -> UUID:
    if not qa_settings.destructive_rbac_tests_enabled:
        pytest.skip("Destructive RBAC probes are disabled; set DESTRUCTIVE_RBAC_TESTS_ENABLED=true")
    if qa_settings.rbac_disposable_account_uuid is None:
        pytest.fail(
            "TEST_DATA_DEFECT: RBAC_DISPOSABLE_ACCOUNT_UUID is not configured",
            pytrace=False,
        )
    if qa_settings.user_bearer_token is None:
        pytest.fail("ENVIRONMENT_DEFECT: API_BEARER_TOKEN is not configured", pytrace=False)
    try:
        return validate_disposable_account_target(
            qa_settings.rbac_disposable_account_uuid,
            qa_settings.user_bearer_token,
            qa_settings.admin_bearer_token,
        )
    except ValueError as error:
        pytest.fail(
            "TEST_DATA_DEFECT: unsafe destructive RBAC configuration "
            f"({exception_type_name(error)})",
            pytrace=False,
        )
