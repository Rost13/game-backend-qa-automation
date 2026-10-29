from __future__ import annotations

import logging
from typing import Any, cast

import httpx
from fixtures.promocodes import PromoFactory

from qa_automation.config import Settings
from qa_automation.diagnostics import exception_type_name
from qa_automation.models.market_proxy import PurchaseResponse


class _FailingPromocodesClient:
    def deactivate(self, promo_uuid: str) -> httpx.Response:
        host = "private" + ".example.internal"
        request = httpx.Request(
            "POST",
            f"https://{host}/promos/{promo_uuid}",
        )
        raise httpx.RequestError("transport-secret-value", request=request)


def test_exception_type_name_does_not_render_exception_message() -> None:
    secret = "database-host-and-password"

    diagnostic = exception_type_name(RuntimeError(secret))

    assert diagnostic == "RuntimeError"
    assert secret not in diagnostic


def test_market_purchase_repr_omits_server_controlled_failure_text() -> None:
    failure_reason = "server-controlled failure reason"
    host = "private" + ".example.internal"
    last_error = f"https://{host}/error?token=opaque-value"
    purchase = PurchaseResponse(
        status="delivery_failed",
        failure_reason=failure_reason,
        last_error=last_error,
    )

    rendered = repr(purchase)

    assert failure_reason not in rendered
    assert last_error not in rendered


def test_promocode_cleanup_log_omits_uuid_and_http_exception(
    caplog: Any,
) -> None:
    promo_uuid = "550e8400-e29b-41d4-a716-446655440000"
    host = "private" + ".example.internal"
    factory = PromoFactory(
        client=cast(Any, _FailingPromocodesClient()),
        settings=Settings(_env_file=None),
    )
    factory._created_promo_uuids.append(promo_uuid)

    with caplog.at_level(logging.WARNING):
        factory.cleanup()

    rendered = caplog.text
    assert "RequestError" in rendered
    assert promo_uuid not in rendered
    assert "transport-secret-value" not in rendered
    assert host not in rendered
