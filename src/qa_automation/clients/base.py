from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import allure
import httpx
from pydantic import BaseModel, ValidationError

from qa_automation.models.common import ErrorEnvelope, SuccessEnvelope

logger = logging.getLogger(__name__)

_SAFE_DIAGNOSTIC_HEADERS = {
    "content-length",
    "content-type",
    "retry-after",
    "traceparent",
    "x-correlation-id",
    "x-request-id",
}
_SENSITIVE_FIELDS = {
    "account_id",
    "access_token",
    "authorization",
    "client_secret",
    "code",
    "cookie",
    "custom_data",
    "email",
    "hmac",
    "password",
    "phone",
    "refresh_token",
    "sid",
    "telegram_user_id",
    "token",
    "uid",
    "user_id",
}
_SENSITIVE_FIELD_SUFFIXES = {
    "api_key",
    "authorization",
    "client_secret",
    "cookie",
    "event_key",
    "hmac",
    "password",
    "private_key",
    "secret",
    "secret_key",
    "sid",
    "signing_key",
    "token",
    "id",
    "uid",
    "uuid",
}
_SAFE_DIAGNOSTIC_FIELDS = {"correlation_id", "event_id", "request_id", "trace_id"}
_PATH_IDENTIFIER_PATTERN = re.compile(
    r"^(?:\d{4,}|[A-Fa-f0-9]{8}-[A-Fa-f0-9-]{27,}|[A-Za-z0-9_-]{24,})$"
)
_SENSITIVE_TEXT_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"https?://[^\s\"']+", re.IGNORECASE), "<redacted-url>"),
    (
        re.compile(
            r"\b[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[1-5][A-Fa-f0-9]{3}-"
            r"[89ABab][A-Fa-f0-9]{3}-[A-Fa-f0-9]{12}\b"
        ),
        "<redacted-id>",
    ),
    (
        re.compile(
            r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\."
            r"[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?![A-Za-z0-9_-])"
        ),
        "<redacted-token>",
    ),
    (
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
        "<redacted-token>",
    ),
    (
        re.compile(r"\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b"),
        "<redacted-host>",
    ),
    (
        re.compile(
            r"""(?i)"?\b(?:password|access_token|refresh_token|token|client_secret|"""
            r"""authorization|cookie|api[_-]?key|secret(?:_key)?)\b"?\s*[:=]\s*"""
            r"""(?:"[^"]*"|'[^']*'|(?:Bearer\s+)?[^\s,;]+)"""
        ),
        "<redacted-credential>",
    ),
    (
        re.compile(r"\b(?:token|password|secret|authorization|cookie|api[_-]?key)\b", re.I),
        "<redacted-sensitive-term>",
    ),
)


class ApiClient:
    """Central HTTP transport with explicit timeouts and sanitized diagnostics."""

    def __init__(self, base_url: str, bearer_token: str, timeout_seconds: float) -> None:
        self._bearer_token = bearer_token
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={
                "Accept": "application/json",
                "User-Agent": "game-backend-qa-automation/0.1",
            },
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        params: Mapping[str, str | int] | None = None,
        json_body: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        request_headers = dict(headers or {})
        if authenticated:
            request_headers["Authorization"] = f"Bearer {self._bearer_token}"
        response = self._client.request(
            method,
            path.lstrip("/"),
            headers=request_headers or None,
            params=params,
            json=json_body,
        )
        request_id = _request_id(response.headers)
        logger.info(
            "%s %s -> %s%s",
            method.upper(),
            _sanitize_url(response.request.url),
            response.status_code,
            f" request_id={request_id}" if request_id else "",
        )
        return response

    def close(self) -> None:
        self._client.close()


def assert_response_status(response: httpx.Response, expected_status: int) -> None:
    if response.status_code != expected_status:
        attach_response_diagnostics(response)
    assert response.status_code == expected_status, (
        f"{response.request.method} {_sanitize_url(response.request.url)} "
        f"returned {response.status_code}; "
        f"expected {expected_status}. Body: {_printable_body(response)}"
    )

    content_type = response.headers.get("content-type")
    if content_type:
        assert "application/json" in content_type.lower(), (
            f"expected JSON response, got Content-Type {content_type!r}"
        )


def validate_response_model[ResponseModel: BaseModel](
    response: httpx.Response,
    model_type: type[ResponseModel],
) -> ResponseModel:
    try:
        return model_type.model_validate(response.json())
    except (ValueError, ValidationError):
        attach_response_diagnostics(response)
        raise AssertionError(
            f"PRODUCT_DEFECT: response does not match {model_type.__name__}. "
            f"Body: {_printable_body(response)}"
        ) from None


def validate_success_data[ResponseModel: BaseModel](
    response: httpx.Response,
    model_type: type[ResponseModel],
) -> ResponseModel:
    try:
        envelope = SuccessEnvelope.model_validate(response.json())
        return model_type.model_validate(envelope.data)
    except (ValueError, ValidationError):
        attach_response_diagnostics(response)
        raise AssertionError(
            f"PRODUCT_DEFECT: successful response does not match "
            f"SuccessEnvelope[{model_type.__name__}]. Body: {_printable_body(response)}"
        ) from None


def validate_error_response(response: httpx.Response) -> ErrorEnvelope:
    try:
        return ErrorEnvelope.model_validate(response.json())
    except (ValueError, ValidationError):
        attach_response_diagnostics(response)
        raise AssertionError(
            f"PRODUCT_DEFECT: error response does not match ErrorEnvelope. "
            f"Body: {_printable_body(response)}"
        ) from None


def attach_response_diagnostics(response: httpx.Response) -> None:
    request = response.request
    request_details = {
        "method": request.method,
        "url": _sanitize_url(request.url),
        "headers": _sanitize_headers(request.headers),
        "body": _decoded_and_sanitized(request.content),
    }
    response_details = {
        "status_code": response.status_code,
        "headers": _sanitize_headers(response.headers),
        "body": _decoded_and_sanitized(response.content),
    }
    allure.attach(
        json.dumps(request_details, ensure_ascii=False, indent=2, default=str),
        "sanitized-request",
        allure.attachment_type.JSON,
    )
    allure.attach(
        json.dumps(response_details, ensure_ascii=False, indent=2, default=str),
        "sanitized-response",
        allure.attachment_type.JSON,
    )


def _sanitize_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        key: value if key.lower() in _SAFE_DIAGNOSTIC_HEADERS else "<redacted>"
        for key, value in headers.items()
    }


def _decoded_and_sanitized(content: bytes) -> Any:
    if not content:
        return None
    try:
        return _sanitize_value(json.loads(content))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"omitted_non_json_body_bytes": len(content)}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "<redacted>" if _is_sensitive_field(key) else _sanitize_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return sanitize_diagnostic_text(value)
    return value


def sanitize_diagnostic_text(value: str) -> str:
    """Redact sensitive patterns from server-controlled diagnostic text."""

    sanitized = value
    placeholders: dict[str, str] = {}
    for index, (pattern, replacement) in enumerate(_SENSITIVE_TEXT_REPLACEMENTS):
        placeholder = f"\x00QA_REDACTION_{index}\x00"
        sanitized, replacement_count = pattern.subn(placeholder, sanitized)
        if replacement_count:
            placeholders[placeholder] = replacement
    for placeholder, replacement in placeholders.items():
        sanitized = sanitized.replace(placeholder, replacement)
    return sanitized


def _is_sensitive_field(key: object) -> bool:
    text = str(key)
    snake_case = re.sub(r"(?<!^)(?=[A-Z])", "_", text).replace("-", "_").replace(".", "_")
    normalized = snake_case.casefold()
    if normalized in _SAFE_DIAGNOSTIC_FIELDS:
        return False
    return normalized in _SENSITIVE_FIELDS or any(
        normalized == suffix or normalized.endswith(f"_{suffix}")
        for suffix in _SENSITIVE_FIELD_SUFFIXES
    )


def _printable_body(response: httpx.Response) -> str:
    return json.dumps(
        _decoded_and_sanitized(response.content),
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )[:2_000]


def _request_id(headers: httpx.Headers) -> str | None:
    for name in ("x-request-id", "x-correlation-id", "traceparent"):
        if value := headers.get(name):
            return str(value)
    return None


def _sanitize_url(url: httpx.URL) -> str:
    sanitized_path = "/".join(
        "%3Credacted%3E"
        if _PATH_IDENTIFIER_PATTERN.fullmatch(segment) or "@" in segment
        else quote(segment, safe="-._~")
        for segment in url.path.split("/")
    )
    sanitized_params: list[tuple[str, str | int | float | bool | None]] = [
        (key, "<redacted>" if _is_sensitive_field(key) else value)
        for key, value in url.params.multi_items()
    ]
    query = str(httpx.QueryParams(sanitized_params))
    return f"{sanitized_path}?{query}" if query else sanitized_path
