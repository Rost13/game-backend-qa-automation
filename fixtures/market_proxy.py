from __future__ import annotations

from collections.abc import Iterator

import pytest

from qa_automation.clients.base import ApiClient
from qa_automation.clients.market_proxy import MarketProxyClient
from qa_automation.config import Settings


@pytest.fixture(scope="session")
def market_proxy_live_settings(qa_settings: Settings) -> Settings:
    if not qa_settings.api_tests_enabled:
        pytest.skip("Live API tests are disabled; set API_TESTS_ENABLED=true")
    missing = qa_settings.missing_market_proxy_api_configuration()
    if missing:
        pytest.fail(
            f"ENVIRONMENT_DEFECT: missing Market Proxy configuration: {', '.join(missing)}",
            pytrace=False,
        )
    return qa_settings


@pytest.fixture(scope="session")
def market_proxy_user_client(
    market_proxy_live_settings: Settings,
) -> Iterator[MarketProxyClient]:
    assert market_proxy_live_settings.market_proxy_base_url is not None
    assert market_proxy_live_settings.market_proxy_api_path is not None
    assert market_proxy_live_settings.user_bearer_token is not None
    transport = ApiClient(
        base_url=str(market_proxy_live_settings.market_proxy_base_url),
        bearer_token=market_proxy_live_settings.user_bearer_token,
        timeout_seconds=market_proxy_live_settings.timeout_seconds,
    )
    yield MarketProxyClient(transport, market_proxy_live_settings.market_proxy_api_path)
    transport.close()


@pytest.fixture(scope="session")
def market_proxy_purchase_settings(market_proxy_live_settings: Settings) -> Settings:
    if not market_proxy_live_settings.market_proxy_purchases_enabled:
        pytest.skip("Market Proxy purchases are disabled; set MARKET_PROXY_PURCHASES_ENABLED=true")
    return market_proxy_live_settings
