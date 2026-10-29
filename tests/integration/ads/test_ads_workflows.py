from __future__ import annotations

from hashlib import sha1
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

import allure
import pytest

from qa_automation.clients.ads import AdsClient
from qa_automation.clients.balance import BalanceClient
from qa_automation.clients.base import (
    assert_response_status,
    validate_response_model,
    validate_success_data,
)
from qa_automation.config import Settings
from qa_automation.models.ads import (
    AdminAdProvider,
    AdminGlobalConfig,
    AdminRewardedAdView,
    AdminRewardedSource,
    AdminRewardIssueAttempts,
    AdminSourceProvider,
    Availability,
    PlacementState,
    ProviderOptionAvailability,
    RewardStatus,
    SourceAvailability,
    StartAdResponse,
)
from qa_automation.models.balance import BalanceResponse

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.serial,
    allure.feature("Ads Service"),
]


@allure.title("Ads creates a requested placement owned by the authenticated user")
@pytest.mark.regression
def test_rewarded_start_creates_owned_requested_placement(
    ads_user_client: AdsClient,
    ads_admin_client: AdsClient,
    ads_start_settings: Settings,
    api_test_user_uuid: UUID,
) -> None:
    source, option, client_session_id = _select_available_option(ads_user_client)

    start_response = ads_user_client.start_rewarded_ad(
        {
            "source_code": source.source_code,
            "source_provider_id": str(option.source_provider_id),
            "client_session_id": str(client_session_id),
            "context": {},
        }
    )

    assert_response_status(start_response, 200)
    started = validate_success_data(start_response, StartAdResponse)
    assert started.user_id == api_test_user_uuid
    assert started.source_code == source.source_code
    assert started.source_provider_id == option.source_provider_id
    assert started.provider_code == option.provider_code
    assert started.ad_unit_id == option.ad_unit_id
    assert started.start_expires_at < started.callback_accept_until
    assert started.custom_data.count(".") == 1

    placement_response = ads_user_client.get_placement(started.placement_token)
    admin_response = ads_admin_client.admin_get_view(started.placement_token)
    assert_response_status(placement_response, 200)
    assert_response_status(admin_response, 200)
    placement = validate_success_data(placement_response, PlacementState)
    admin_view = validate_success_data(admin_response, AdminRewardedAdView)
    assert placement.placement_token == started.placement_token
    assert placement.status == "requested"
    assert admin_view.account_uuid == api_test_user_uuid
    assert admin_view.client_session_id == client_session_id
    assert admin_view.status == "requested"


@allure.title("Ads admin update routes preserve configuration values across patch and upsert")
@pytest.mark.regression
def test_admin_global_config_roundtrip(
    ads_admin_client: AdsClient,
    ads_admin_mutation_settings: Settings,
) -> None:
    before_response = ads_admin_client.admin_get_global_config()
    assert_response_status(before_response, 200)
    before = validate_success_data(before_response, AdminGlobalConfig)
    payload = _global_config_payload(before)

    patch_response = ads_admin_client.admin_patch_global_config(payload)
    assert_response_status(patch_response, 200)
    patched = validate_success_data(patch_response, AdminGlobalConfig)
    _assert_same_global_config(patched, before)

    put_response = ads_admin_client.admin_upsert_global_config(payload)
    assert_response_status(put_response, 200)
    upserted = validate_success_data(put_response, AdminGlobalConfig)
    _assert_same_global_config(upserted, before)


@allure.title("Ads admin can create, patch, and upsert isolated disabled configuration")
@pytest.mark.regression
def test_admin_configuration_lifecycle(
    ads_admin_client: AdsClient,
    ads_admin_mutation_settings: Settings,
) -> None:
    unique = uuid4().hex[:16]
    provider_code = f"qa_{unique}"
    source_code = f"qa_{unique}"
    source_provider_id = uuid4()

    provider_payload = {
        "provider_code": provider_code,
        "enabled": False,
        "callback_path": f"/api/v2/ads/qa/{unique}/callback",
        "validation_mode": "qa_disabled",
    }
    provider_response = ads_admin_client.admin_create_provider(provider_payload)
    assert_response_status(provider_response, 200)
    provider = validate_success_data(provider_response, AdminAdProvider)
    assert provider.provider_code == provider_code
    assert provider.enabled is False

    provider_patch = ads_admin_client.admin_patch_provider(
        provider_code,
        {"validation_mode": "qa_disabled_patched"},
    )
    assert_response_status(provider_patch, 200)
    patched_provider = validate_success_data(provider_patch, AdminAdProvider)
    assert patched_provider.validation_mode == "qa_disabled_patched"

    provider_put = ads_admin_client.admin_upsert_provider(provider_code, provider_payload)
    assert_response_status(provider_put, 200)
    assert validate_success_data(provider_put, AdminAdProvider).validation_mode == "qa_disabled"

    source_payload: dict[str, object] = {
        "source_code": source_code,
        "enabled": False,
        "ad_format": "rewarded",
        "provider_code": provider_code,
        "ad_unit_id": f"qa-unit-{unique}",
        "platform_ad_unit_ids": {},
        "cooldown_sec": 0,
        "daily_limit_24h": 0,
        "reward_type": "balance_currency",
        "reward_payload": {"currency": "soft", "amount": 1},
        "priority": 0,
        "client_location": "qa_automation",
        "requires_context": False,
        "context_schema": {},
        "min_app_version": None,
        "platforms": [],
    }
    source_response = ads_admin_client.admin_create_source(source_payload)
    assert_response_status(source_response, 200)
    source = validate_success_data(source_response, AdminRewardedSource)
    assert source.source_code == source_code
    assert source.enabled is False

    source_patch = ads_admin_client.admin_patch_source(source_code, {"priority": 1})
    assert_response_status(source_patch, 200)
    assert validate_success_data(source_patch, AdminRewardedSource).priority == 1

    source_put = ads_admin_client.admin_upsert_source(source_code, source_payload)
    assert_response_status(source_put, 200)
    assert validate_success_data(source_put, AdminRewardedSource).priority == 0

    option_payload: dict[str, object] = {
        "source_provider_id": str(source_provider_id),
        "source_code": source_code,
        "provider_code": provider_code,
        "ad_unit_id": f"qa-unit-{unique}",
        "allowed_login_providers": ["google"],
        "enabled": False,
        "priority": 0,
        "daily_limit_24h": 0,
        "session_limit": 0,
        "cooldown_sec": 0,
        "min_app_version": None,
    }
    option_response = ads_admin_client.admin_create_source_provider(option_payload)
    assert_response_status(option_response, 200)
    option = validate_success_data(option_response, AdminSourceProvider)
    assert option.source_provider_id == source_provider_id
    assert option.enabled is False

    option_patch = ads_admin_client.admin_patch_source_provider(
        source_provider_id,
        {"priority": 1},
    )
    assert_response_status(option_patch, 200)
    assert validate_success_data(option_patch, AdminSourceProvider).priority == 1

    option_put = ads_admin_client.admin_upsert_source_provider(
        source_provider_id,
        option_payload,
    )
    assert_response_status(option_put, 200)
    assert validate_success_data(option_put, AdminSourceProvider).priority == 0


@allure.title("AppLovin callback rewards Balance exactly once and persists diagnostics")
@pytest.mark.regression
def test_applovin_callback_rewards_balance_exactly_once(
    ads_user_client: AdsClient,
    ads_admin_client: AdsClient,
    balance_user_client: BalanceClient,
    ads_callback_settings: Settings,
    api_test_user_uuid: UUID,
) -> None:
    source, option, client_session_id = _select_available_option(
        ads_user_client,
        provider_code="applovin",
        reward_type="balance_currency",
    )
    currency, amount = _balance_reward(source)
    before = _get_balance(balance_user_client)
    start_response = ads_user_client.start_rewarded_ad(
        {
            "source_code": source.source_code,
            "source_provider_id": str(option.source_provider_id),
            "client_session_id": str(client_session_id),
            "context": {},
        }
    )
    assert_response_status(start_response, 200)
    started = validate_success_data(start_response, StartAdResponse)
    event_id = f"qa-{uuid4()}"
    event_key = ads_callback_settings.ads_applovin_event_key_value
    assert event_key is not None
    signature = sha1(f"{event_id}{event_key}".encode()).hexdigest()
    callback_params: dict[str, str | int] = {
        "user_id": str(api_test_user_uuid),
        "ad_unit_id": started.ad_unit_id,
        "placement": source.source_code,
        "custom_data": started.custom_data,
        "event_id": event_id,
        "token": signature,
        "amount": amount,
        "currency": currency,
    }

    first_callback = ads_user_client.applovin_callback(callback_params)
    assert_response_status(first_callback, 200)
    first_status = validate_response_model(first_callback, RewardStatus)
    assert first_status.status == "rewarded"
    assert first_status.event_id == event_id
    assert first_status.user_id == api_test_user_uuid

    timeout_seconds = ads_callback_settings.ads_event_timeout.total_seconds()
    expected_balance = _expected_balance(before, currency, amount)
    settled = _wait_for_balance(
        balance_user_client,
        currency,
        expected_balance,
        timeout_seconds=timeout_seconds,
    )
    _wait_for_placement_status(
        ads_user_client,
        started.placement_token,
        "rewarded",
        timeout_seconds=timeout_seconds,
    )

    duplicate_callback = ads_user_client.applovin_callback(callback_params)
    assert_response_status(duplicate_callback, 200)
    duplicate_status = validate_response_model(duplicate_callback, RewardStatus)
    assert duplicate_status.status == "rewarded"
    assert _currency_value(_get_balance(balance_user_client), currency) == _currency_value(
        settled, currency
    )

    view_response = ads_admin_client.admin_get_view(started.placement_token)
    attempts_response = ads_admin_client.admin_get_view_reward_attempts(started.placement_token)
    assert_response_status(view_response, 200)
    assert_response_status(attempts_response, 200)
    view = validate_success_data(view_response, AdminRewardedAdView)
    attempts = validate_success_data(attempts_response, AdminRewardIssueAttempts)
    assert view.status == "rewarded"
    assert view.provider_transaction_id == event_id
    assert view.rewarded_at is not None
    assert attempts.total == 1
    assert len(attempts.items) == 1
    assert attempts.items[0].status == "success"
    assert attempts.items[0].idempotency_key == f"reward:{started.placement_token}"


def _select_available_option(
    client: AdsClient,
    *,
    provider_code: str | None = None,
    reward_type: str | None = None,
) -> tuple[SourceAvailability, ProviderOptionAvailability, UUID]:
    client_session_id = uuid4()
    response = client.get_availability(client_session_id)
    assert_response_status(response, 200)
    availability = validate_success_data(response, Availability)
    for source in availability.sources:
        if not source.available or source.requires_context:
            continue
        if reward_type is not None and source.reward_type != reward_type:
            continue
        for option in source.provider_options:
            if option.available and (
                provider_code is None or option.provider_code == provider_code
            ):
                return source, option, client_session_id
    pytest.skip(
        "TEST_DATA_DEFECT: no compatible available Ads source/provider option exists for the "
        "test account"
    )


def _global_config_payload(config: AdminGlobalConfig) -> dict[str, object]:
    return {
        "enabled": config.enabled,
        "daily_limit_24h": config.daily_limit_24h,
        "session_limit": config.session_limit,
        "cooldown_sec": config.cooldown_sec,
        "session_inactivity_threshold_sec": config.session_inactivity_threshold_sec,
    }


def _assert_same_global_config(actual: AdminGlobalConfig, expected: AdminGlobalConfig) -> None:
    assert _global_config_payload(actual) == _global_config_payload(expected)
    assert actual.updated_at >= expected.updated_at


def _balance_reward(source: SourceAvailability) -> tuple[str, int]:
    currency = source.reward_preview.get("currency")
    if not isinstance(currency, str) or currency.lower() not in {"soft", "hard", "xp"}:
        pytest.fail(
            f"TEST_DATA_DEFECT: unsupported Ads balance reward currency {currency!r}",
            pytrace=False,
        )
    amount_field = "amount_minor" if currency.lower() == "hard" else "amount"
    amount = source.reward_preview.get(amount_field)
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        pytest.fail(
            f"TEST_DATA_DEFECT: Ads reward {amount_field} must be a positive integer",
            pytrace=False,
        )
    return currency.lower(), amount


def _get_balance(client: BalanceClient) -> BalanceResponse:
    response = client.get_balance()
    assert_response_status(response, 200)
    return validate_success_data(response, BalanceResponse)


def _expected_balance(before: BalanceResponse, currency: str, amount: int) -> int:
    return _currency_value(before, currency) + amount


def _currency_value(balance: BalanceResponse, currency: str) -> int:
    value = getattr(balance, currency)
    return 0 if value is None else value


def _wait_for_balance(
    client: BalanceClient,
    currency: str,
    expected: int,
    *,
    timeout_seconds: float,
) -> BalanceResponse:
    deadline = monotonic() + timeout_seconds
    waiter = Event()
    while True:
        balance = _get_balance(client)
        actual = _currency_value(balance, currency)
        if actual == expected:
            return balance
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: Ads {currency} reward did not settle to {expected} within "
                f"{timeout_seconds:g}s; actual={actual}",
                pytrace=False,
            )
        waiter.wait(timeout=min(0.25, remaining))


def _wait_for_placement_status(
    client: AdsClient,
    placement_token: UUID,
    expected: str,
    *,
    timeout_seconds: float,
) -> PlacementState:
    deadline = monotonic() + timeout_seconds
    waiter = Event()
    while True:
        response = client.get_placement(placement_token)
        assert_response_status(response, 200)
        placement = validate_success_data(response, PlacementState)
        if placement.status == expected:
            return placement
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: Ads placement {placement_token} did not reach {expected!r} "
                f"within {timeout_seconds:g}s; actual={placement.status!r}",
                pytrace=False,
            )
        waiter.wait(timeout=min(0.25, remaining))
