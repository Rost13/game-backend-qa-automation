from __future__ import annotations

from uuid import UUID, uuid4

import allure
import pytest

from qa_automation.clients.base import (
    assert_response_status,
    validate_error_response,
    validate_response_model,
    validate_success_data,
)
from qa_automation.clients.market_proxy import MarketProxyClient
from qa_automation.models.market_proxy import (
    CatalogResponse,
    MarketProxyServiceError,
    PublishedCatalogResponse,
)

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Market Proxy")]


@allure.title("Market catalog requires authentication")
@pytest.mark.smoke
def test_market_catalog_requires_authentication(
    market_proxy_user_client: MarketProxyClient,
) -> None:
    response = market_proxy_user_client.get_catalog(authenticated=False)

    assert_response_status(response, 401)
    assert validate_error_response(response).error_description == "missing or invalid access token"


@allure.title("Unauthorized catalog response follows the published OpenAPI schema")
@pytest.mark.contract
def test_market_catalog_unauthorized_error_matches_openapi_contract(
    market_proxy_user_client: MarketProxyClient,
) -> None:
    response = market_proxy_user_client.get_catalog(authenticated=False)

    assert_response_status(response, 401)
    error = validate_response_model(response, MarketProxyServiceError)
    assert error.ok is False
    assert error.error_description == "missing or invalid access token"


@allure.title("User can get the current Market catalog")
@pytest.mark.smoke
def test_user_can_get_market_catalog(market_proxy_user_client: MarketProxyClient) -> None:
    response = market_proxy_user_client.get_catalog()

    assert_response_status(response, 200)
    catalog = validate_success_data(response, CatalogResponse)
    assert catalog.items, "Market catalog must contain at least one item"
    product_ids = [item.product_id for item in catalog.items]
    assert len(product_ids) == len(set(product_ids)), "catalog product_id values must be unique"
    assert any(item.available for item in catalog.items), "catalog must contain an available item"
    for item in catalog.items:
        assert item.product_id.strip()
        UUID(item.def_uuid)
        assert item.ton_amount >= 0
        assert item.pxg_amount >= 0


@allure.title("Market catalog follows the published OpenAPI success schema")
@pytest.mark.contract
def test_market_catalog_matches_openapi_contract(
    market_proxy_user_client: MarketProxyClient,
) -> None:
    response = market_proxy_user_client.get_catalog()

    assert_response_status(response, 200)
    catalog = validate_response_model(response, PublishedCatalogResponse)
    assert catalog.ok is True
    assert catalog.data.items


@allure.title("Purchase creation requires authentication")
@pytest.mark.smoke
def test_purchase_creation_requires_authentication(
    market_proxy_user_client: MarketProxyClient,
) -> None:
    response = market_proxy_user_client.create_purchase(
        "unavailable-product",
        idempotency_key=f"qa-market-unauthorized-{uuid4()}",
        authenticated=False,
    )

    assert_response_status(response, 401)
    assert validate_error_response(response).error_description == "missing or invalid access token"


@allure.title("Purchase creation requires Idempotency-Key")
@pytest.mark.regression
def test_purchase_creation_requires_idempotency_key(
    market_proxy_user_client: MarketProxyClient,
) -> None:
    response = market_proxy_user_client.create_purchase(None, idempotency_key=None)

    assert_response_status(response, 400)
    assert validate_error_response(response).error_description == (
        "Idempotency-Key header is required"
    )


@allure.title("Purchase creation rejects missing product_id")
@pytest.mark.regression
def test_purchase_creation_rejects_missing_product_id(
    market_proxy_user_client: MarketProxyClient,
) -> None:
    response = market_proxy_user_client.create_purchase(
        None,
        idempotency_key=f"qa-market-missing-product-{uuid4()}",
    )

    assert_response_status(response, 400)
    assert validate_error_response(response).error_description == "invalid request"


@allure.title("Purchase creation rejects an unavailable product")
@pytest.mark.regression
def test_purchase_creation_rejects_unavailable_product(
    market_proxy_user_client: MarketProxyClient,
) -> None:
    response = market_proxy_user_client.create_purchase(
        f"qa-missing-product:{uuid4()}",
        idempotency_key=f"qa-market-unavailable-{uuid4()}",
    )

    assert_response_status(response, 400)
    assert validate_error_response(response).error_description.endswith("product unavailable")


@allure.title("Purchase status requires authentication")
@pytest.mark.smoke
def test_purchase_status_requires_authentication(
    market_proxy_user_client: MarketProxyClient,
) -> None:
    response = market_proxy_user_client.get_purchase(str(uuid4()), authenticated=False)

    assert_response_status(response, 401)
    assert validate_error_response(response).error_description == "missing or invalid access token"


@allure.title("Unknown purchase returns not found")
@pytest.mark.regression
def test_unknown_purchase_returns_not_found(
    market_proxy_user_client: MarketProxyClient,
) -> None:
    response = market_proxy_user_client.get_purchase(str(uuid4()))

    assert_response_status(response, 404)
    assert validate_error_response(response).error_description == "get purchase: not found"
