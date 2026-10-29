from __future__ import annotations

import base64
import json
from uuid import UUID

import pytest

from qa_automation.auth import (
    jwt_account_role,
    jwt_subject,
    validate_disposable_account_target,
)


def _unsigned_jwt(payload: dict[str, object]) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{encoded}.signature"


def test_jwt_subject_returns_uuid_without_exposing_token() -> None:
    expected = UUID("550e8400-e29b-41d4-a716-446655440000")

    assert jwt_subject(_unsigned_jwt({"sub": str(expected)})) == expected


def test_jwt_subject_rejects_missing_uuid_subject() -> None:
    with pytest.raises(ValueError, match="valid UUID subject"):
        jwt_subject(_unsigned_jwt({"role": "user"}))


def test_jwt_account_role_returns_supported_account_role() -> None:
    token = _unsigned_jwt({"account_role": "user"})

    assert jwt_account_role(token) == "user"


@pytest.mark.parametrize("payload", [{}, {"account_role": "owner"}, {"account_role": 1}])
def test_jwt_account_role_rejects_missing_or_unsupported_role(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="supported account role"):
        jwt_account_role(_unsigned_jwt(payload))


def test_disposable_target_must_not_match_user_or_admin_subject() -> None:
    user_uuid = UUID("550e8400-e29b-41d4-a716-446655440000")
    admin_uuid = UUID("2f1c7a0a-a8ba-4e15-97ce-fb1a29a60000")
    user_token = _unsigned_jwt({"sub": str(user_uuid), "account_role": "user"})
    admin_token = _unsigned_jwt({"sub": str(admin_uuid), "account_role": "admin"})

    with pytest.raises(ValueError, match="ordinary test account"):
        validate_disposable_account_target(user_uuid, user_token, admin_token)
    with pytest.raises(ValueError, match="admin test account"):
        validate_disposable_account_target(admin_uuid, user_token, admin_token)


def test_disposable_target_requires_ordinary_user_token_and_accepts_distinct_target() -> None:
    user_uuid = UUID("550e8400-e29b-41d4-a716-446655440000")
    target_uuid = UUID("6e590c2f-2237-488f-b0b3-22cf08f00000")
    user_token = _unsigned_jwt({"sub": str(user_uuid), "account_role": "user"})

    assert validate_disposable_account_target(target_uuid, user_token, None) == target_uuid

    admin_as_user_token = _unsigned_jwt({"sub": str(user_uuid), "account_role": "admin"})
    with pytest.raises(ValueError, match="ordinary-user role"):
        validate_disposable_account_target(target_uuid, admin_as_user_token, None)
