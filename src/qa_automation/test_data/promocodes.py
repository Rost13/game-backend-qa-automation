from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Literal

_ALPHABET = string.ascii_uppercase + string.digits
_PROMO_CODE_LENGTH = 12

PromoRewardCurrency = Literal["SFT", "PXG"]


def unique_promo_code(prefix: str) -> str:
    normalized = prefix.strip().upper()
    if (
        not normalized
        or len(normalized) > 4
        or not normalized.isascii()
        or not normalized.isalnum()
    ):
        raise ValueError("promo prefix must be 1-4 ASCII letters or digits")
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(_PROMO_CODE_LENGTH - len(normalized)))
    return normalized + suffix


def campaign_payload(
    *,
    prefix: str,
    reward_amount: int,
    max_claims: int,
    reward_currency: PromoRewardCurrency = "SFT",
) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "code": unique_promo_code(prefix),
        "type": "CAMPAIGN",
        "is_active": True,
        "reward_currency": reward_currency,
        "reward_amount": reward_amount,
        "max_claims": max_claims,
        "start_at_ms": int((now - timedelta(minutes=1)).timestamp() * 1_000),
        "expire_at_ms": int((now + timedelta(minutes=30)).timestamp() * 1_000),
    }
