from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx
import pytest
from psycopg import Error as PostgresError

from qa_automation.clients.base import (
    ApiClient,
    attach_response_diagnostics,
    validate_success_data,
)
from qa_automation.clients.promocodes import PromocodesClient
from qa_automation.config import Settings
from qa_automation.db.kubernetes import KubectlPostgresTunnel, KubernetesDatabaseError
from qa_automation.db.promocodes import PromocodesDatabase
from qa_automation.diagnostics import exception_type_name
from qa_automation.models.promocodes import UpsertPromoResponse
from qa_automation.test_data.promocodes import PromoRewardCurrency, campaign_payload

logger = logging.getLogger(__name__)


def _promocodes_client(
    settings: Settings,
    bearer_token: str,
) -> Iterator[PromocodesClient]:
    assert settings.promocodes_base_url is not None
    assert settings.promocodes_api_path is not None
    transport = ApiClient(
        base_url=str(settings.promocodes_base_url),
        bearer_token=bearer_token,
        timeout_seconds=settings.timeout_seconds,
    )
    yield PromocodesClient(transport, settings.promocodes_api_path)
    transport.close()


@pytest.fixture(scope="session")
def promocodes_user_client(live_settings: Settings) -> Iterator[PromocodesClient]:
    assert live_settings.promocodes_base_url is not None
    assert live_settings.promocodes_api_path is not None
    assert live_settings.user_bearer_token is not None
    yield from _promocodes_client(live_settings, live_settings.user_bearer_token)


@pytest.fixture(scope="session")
def promocodes_admin_client(live_settings: Settings) -> Iterator[PromocodesClient]:
    missing = live_settings.missing_admin_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing admin configuration: {', '.join(missing)}",
            pytrace=False,
        )
    assert live_settings.admin_bearer_token is not None
    yield from _promocodes_client(live_settings, live_settings.admin_bearer_token)


@dataclass
class PromoFactory:
    client: PromocodesClient
    settings: Settings
    _created_promo_uuids: list[str] = field(default_factory=list)

    def create_active_campaign(
        self,
        *,
        reward_currency: PromoRewardCurrency = "SFT",
    ) -> tuple[httpx.Response, dict[str, object]]:
        payload = campaign_payload(
            prefix=self.settings.promocodes_code_prefix,
            reward_amount=self.settings.promocodes_reward_amount,
            max_claims=self.settings.promocodes_max_claims,
            reward_currency=reward_currency,
        )
        response = self.client.upsert(payload)
        if response.status_code == 200:
            created = validate_success_data(response, UpsertPromoResponse)
            self._created_promo_uuids.append(str(created.promo_uuid))
        return response, payload

    def cleanup(self) -> None:
        for promo_uuid in reversed(self._created_promo_uuids):
            try:
                response = self.client.deactivate(promo_uuid)
            except httpx.HTTPError as error:
                logger.warning(
                    "Cleanup could not deactivate a created promo (error_type=%s)",
                    exception_type_name(error),
                )
                continue
            if response.status_code != 200:
                attach_response_diagnostics(response)
                logger.warning(
                    "Cleanup could not deactivate a created promo: status=%s",
                    response.status_code,
                )


@pytest.fixture
def promo_factory(
    promocodes_admin_client: PromocodesClient,
    mutation_settings: Settings,
) -> Iterator[PromoFactory]:
    factory = PromoFactory(promocodes_admin_client, mutation_settings)
    yield factory
    factory.cleanup()


def _open_database(settings: Settings) -> PromocodesDatabase:
    missing = settings.missing_database_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing database configuration: {', '.join(missing)}",
            pytrace=False,
        )
    try:
        return PromocodesDatabase(settings)
    except (PostgresError, OSError, ValueError) as error:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: PostgreSQL connection failed ({exception_type_name(error)})",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def promo_database_settings(live_settings: Settings) -> Iterator[Settings | None]:
    if not live_settings.promocodes_db_assertions_enabled:
        yield None
        return

    if not live_settings.promocodes_db_kube_forward_enabled:
        yield live_settings
        return

    try:
        with KubectlPostgresTunnel(live_settings) as forwarded_settings:
            yield forwarded_settings
    except KubernetesDatabaseError as error:
        pytest.fail(
            "INFRASTRUCTURE_DEFECT: Kubernetes PostgreSQL tunnel failed "
            f"({exception_type_name(error)})",
            pytrace=False,
        )


@pytest.fixture
def promo_database(
    promo_database_settings: Settings | None,
) -> Iterator[PromocodesDatabase | None]:
    if promo_database_settings is None:
        yield None
        return

    database = _open_database(promo_database_settings)
    yield database
    database.close()


@pytest.fixture
def required_promo_database(
    promo_database_settings: Settings | None,
) -> Iterator[PromocodesDatabase]:
    if promo_database_settings is None:
        pytest.skip(
            "Promocodes database assertions are disabled; set PROMOCODES_DB_ASSERTIONS_ENABLED=true"
        )
    database = _open_database(promo_database_settings)
    yield database
    database.close()
