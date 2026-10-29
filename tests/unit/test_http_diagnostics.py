from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from qa_automation.clients.base import (
    _decoded_and_sanitized,
    _sanitize_headers,
    _sanitize_url,
    assert_response_status,
    sanitize_diagnostic_text,
    validate_response_model,
)


class _ExpectedPayload(BaseModel):
    count: int


def test_public_diagnostic_text_sanitizer_redacts_server_controlled_values() -> None:
    host = "private-api.example.internal"
    account_id = "550e8400-e29b-41d4-a716-446655440000"
    token = ".".join(("eyJ" + "a" * 11, "b" * 11, "c" * 11))
    raw = (
        f"upstream https://{host}/failed account={account_id} "
        f"authorization={token} password rejected"
    )

    sanitized = sanitize_diagnostic_text(raw)

    assert host not in sanitized
    assert account_id not in sanitized
    assert token not in sanitized
    assert "password" not in sanitized.casefold()
    assert "<redacted-url>" in sanitized
    assert "<redacted-id>" in sanitized
    assert "<redacted-credential>" in sanitized


def test_diagnostic_text_sanitizer_redacts_credential_assignment_values() -> None:
    password_value = "synthetic-password-value"
    token_value = "opaque-token-value"
    authorization_value = "opaque-bearer-value"
    cookie_value = "opaque-cookie-value"
    raw = (
        f"password={password_value} token: {token_value} "
        f"Authorization: Bearer {authorization_value} Cookie=session={cookie_value}"
    )

    sanitized = sanitize_diagnostic_text(raw)

    for sensitive_value in (
        password_value,
        token_value,
        authorization_value,
        cookie_value,
    ):
        assert sensitive_value not in sanitized


def test_sanitize_url_redacts_callback_credentials_and_preserves_context() -> None:
    url = httpx.URL(
        "https://example.test/callback",
        params={
            "event_id": "qa-event",
            "token": "provider-signature",
            "hmac": "provider-hmac",
            "sid": "signed-custom-data",
            "custom_data": "another-signed-value",
            "placementToken": "camel-case-secret",
            "user_uuid": "550e8400-e29b-41d4-a716-446655440000",
        },
    )

    sanitized = _sanitize_url(url)

    assert "qa-event" in sanitized
    assert "example.test" not in sanitized
    assert "provider-signature" not in sanitized
    assert "provider-hmac" not in sanitized
    assert "signed-custom-data" not in sanitized
    assert "another-signed-value" not in sanitized
    assert "camel-case-secret" not in sanitized
    assert "550e8400-e29b-41d4-a716-446655440000" not in sanitized
    assert sanitized.count("%3Credacted%3E") == 6


def test_status_failure_omits_host_identifier_query_secret_and_plaintext_body() -> None:
    host = "private" + ".example.internal"
    account_id = "550e8400-e29b-41d4-a716-446655440000"
    query_secret = "provider-secret-value"
    plaintext_secret = "database-password-value"
    request = httpx.Request(
        "GET",
        f"https://{host}/users/{account_id}?token={query_secret}",
    )
    response = httpx.Response(
        500,
        request=request,
        text=f"upstream failed: {plaintext_secret}",
    )

    with pytest.raises(AssertionError) as captured:
        assert_response_status(response, 200)

    diagnostic = str(captured.value)
    assert host not in diagnostic
    assert account_id not in diagnostic
    assert query_secret not in diagnostic
    assert plaintext_secret not in diagnostic
    assert "/users/%3Credacted%3E" in diagnostic


def test_non_json_diagnostics_report_only_content_length() -> None:
    plaintext_secret = "plaintext-secret-that-must-not-be-attached"
    content = plaintext_secret.encode("utf-8")

    sanitized = _decoded_and_sanitized(content)

    assert sanitized == {"omitted_non_json_body_bytes": len(content)}
    assert plaintext_secret not in str(sanitized)


def test_json_diagnostics_redact_secret_like_field_suffixes() -> None:
    content = (
        b'{"placement_token":"one","apiKey":"two",'
        b'"nested":{"database_password":"three"},'
        b'"user_uuid":"four","item_id":"five","event_id":"qa-event",'
        b'"status":"ok"}'
    )

    sanitized = _decoded_and_sanitized(content)

    assert sanitized == {
        "placement_token": "<redacted>",
        "apiKey": "<redacted>",
        "nested": {"database_password": "<redacted>"},
        "user_uuid": "<redacted>",
        "item_id": "<redacted>",
        "event_id": "qa-event",
        "status": "ok",
    }


def test_headers_redact_host_and_redirect_location() -> None:
    host = "private-api.example.internal"
    query_secret = "redirect-secret-value"
    headers = httpx.Headers(
        {
            "Host": host,
            "Location": f"https://{host}/callback?token={query_secret}",
            "Content-Type": "application/json",
            "X-Backend-Node": "private-node-name",
        }
    )

    sanitized = _sanitize_headers(headers)

    assert sanitized["host"] == "<redacted>"
    assert sanitized["location"] == "<redacted>"
    assert sanitized["content-type"] == "application/json"
    assert sanitized["x-backend-node"] == "<redacted>"
    assert host not in str(sanitized)
    assert query_secret not in str(sanitized)


def test_json_message_values_redact_embedded_url_identifier_and_secret() -> None:
    host = "private-api.example.internal"
    account_id = "550e8400-e29b-41d4-a716-446655440000"
    query_secret = "embedded-secret-value"
    content = (
        f'{{"message":"failed at https://{host}/users/{account_id}'
        f'?token={query_secret}","status":"failed"}}'
    ).encode()

    sanitized = _decoded_and_sanitized(content)

    rendered = str(sanitized)
    assert host not in rendered
    assert account_id not in rendered
    assert query_secret not in rendered
    assert sanitized["status"] == "failed"


def test_validation_failure_suppresses_raw_pydantic_error_context() -> None:
    host = "private" + ".example.internal"
    embedded_secret = "validation-input-secret"
    request = httpx.Request("GET", f"https://{host}/data")
    response = httpx.Response(
        200,
        request=request,
        json={"count": embedded_secret, "token": embedded_secret},
    )

    with pytest.raises(AssertionError) as captured:
        validate_response_model(response, _ExpectedPayload)

    assert captured.value.__cause__ is None
    assert captured.value.__suppress_context__ is True
    assert embedded_secret not in str(captured.value)
