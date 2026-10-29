from __future__ import annotations

import base64
import binascii
import json
from typing import Any
from uuid import UUID


def _jwt_payload(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("token is not a JWT")
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        parsed = json.loads(decoded)
        if not isinstance(parsed, dict):
            raise ValueError("JWT payload is not an object")
        return parsed
    except (ValueError, TypeError, UnicodeError, binascii.Error) as error:
        raise ValueError("configured token does not contain a valid JWT payload") from error


def jwt_subject(token: str) -> UUID:
    """Read the configured test account UUID without logging or validating the JWT signature."""

    try:
        return UUID(str(_jwt_payload(token)["sub"]))
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError("configured JWT does not contain a valid UUID subject") from error


def jwt_account_role(token: str) -> str:
    """Read a supported account role for configuration preflight only."""

    try:
        role = _jwt_payload(token)["account_role"]
    except (ValueError, KeyError) as error:
        raise ValueError("configured JWT does not contain a supported account role") from error
    if not isinstance(role, str) or role.casefold() not in {"user", "admin"}:
        raise ValueError("configured JWT does not contain a supported account role")
    return role.casefold()


def validate_disposable_account_target(
    target: UUID,
    user_token: str,
    admin_token: str | None,
) -> UUID:
    """Reject shared account subjects before destructive authorization probes."""

    if jwt_account_role(user_token) != "user":
        raise ValueError("destructive RBAC probes require an ordinary-user role")
    if target == jwt_subject(user_token):
        raise ValueError("disposable target matches the ordinary test account")
    if admin_token is not None and target == jwt_subject(admin_token):
        raise ValueError("disposable target matches the admin test account")
    return target
