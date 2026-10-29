from __future__ import annotations

from collections.abc import Iterator

import pytest

from qa_automation.clients.base import ApiClient
from qa_automation.clients.goods import GoodsClient
from qa_automation.config import Settings


def _client(settings: Settings, token: str) -> Iterator[GoodsClient]:
    assert settings.goods_base_url is not None
    assert settings.goods_api_path is not None
    transport = ApiClient(str(settings.goods_base_url), token, settings.timeout_seconds)
    yield GoodsClient(transport, settings.goods_api_path)
    transport.close()


@pytest.fixture(scope="session")
def goods_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_goods_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Goods configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


@pytest.fixture(scope="session")
def goods_user_client(goods_live_settings: Settings) -> Iterator[GoodsClient]:
    assert goods_live_settings.user_bearer_token is not None
    yield from _client(goods_live_settings, goods_live_settings.user_bearer_token)


@pytest.fixture(scope="session")
def goods_admin_client(goods_live_settings: Settings) -> Iterator[GoodsClient]:
    if goods_live_settings.admin_bearer_token is None:
        pytest.fail("ENVIRONMENT_DEFECT: API_ADMIN_BEARER_TOKEN is not configured", pytrace=False)
    yield from _client(goods_live_settings, goods_live_settings.admin_bearer_token)
