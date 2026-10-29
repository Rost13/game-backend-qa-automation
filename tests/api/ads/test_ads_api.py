from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast
from uuid import UUID, uuid4

import allure
import httpx
import pytest

from qa_automation.clients.ads import AdsClient
from qa_automation.clients.base import (
    assert_response_status,
    validate_error_response,
    validate_response_model,
    validate_success_data,
)
from qa_automation.models.ads import (
    AdConfig,
    AdminAdProvider,
    AdminAdProviders,
    AdminGlobalConfig,
    AdminRewardedAdViews,
    AdminRewardedGroupStats,
    AdminRewardedSources,
    AdminRewardedStatsSummary,
    AdminRewardIssueAttempts,
    AdminSourceProviders,
    AdminUserDiagnostics,
    Availability,
    UserAdStatus,
)

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Ads Service")]

_PROTECTED_OPERATIONS = [
    "availability",
    "start",
    "placement",
    "admin-get-global-config",
    "admin-patch-global-config",
    "admin-put-global-config",
    "admin-list-providers",
    "admin-create-provider",
    "admin-get-provider",
    "admin-patch-provider",
    "admin-put-provider",
    "admin-list-sources",
    "admin-create-source",
    "admin-get-source",
    "admin-patch-source",
    "admin-put-source",
    "admin-list-source-providers",
    "admin-create-source-provider",
    "admin-get-source-provider",
    "admin-patch-source-provider",
    "admin-put-source-provider",
    "admin-list-views",
    "admin-get-view",
    "admin-view-attempts",
    "admin-user-summary",
    "admin-user-views",
    "admin-user-limits",
    "admin-user-attempts",
    "admin-stats-summary",
    "admin-stats-timeseries",
    "admin-stats-by-source",
    "admin-stats-by-provider",
    "admin-stats-by-source-provider",
    "admin-stats-reject-reasons",
]

_ADMIN_OPERATIONS = _PROTECTED_OPERATIONS[3:]


@allure.title("Ads operation requires authentication: {operation}")
@pytest.mark.regression
@pytest.mark.parametrize("operation", _PROTECTED_OPERATIONS)
def test_ads_operations_require_authentication(
    ads_user_client: AdsClient,
    api_test_user_uuid: UUID,
    operation: str,
) -> None:
    response = _call_protected_operation(
        ads_user_client,
        api_test_user_uuid,
        operation,
        authenticated=False,
    )

    assert_response_status(response, 401)
    validate_error_response(response)


@allure.title("Ordinary user cannot call Ads admin operation: {operation}")
@pytest.mark.regression
@pytest.mark.parametrize("operation", _ADMIN_OPERATIONS)
def test_ads_admin_operations_reject_ordinary_user(
    ads_user_client: AdsClient,
    api_test_user_uuid: UUID,
    operation: str,
) -> None:
    response = _call_protected_operation(
        ads_user_client,
        api_test_user_uuid,
        operation,
        authenticated=True,
    )

    assert_response_status(response, 403)
    validate_error_response(response)


@allure.title("Legacy ad config is public and consistent for {platform}")
@pytest.mark.smoke
@pytest.mark.parametrize("platform", ["android", "ios"])
def test_public_ad_config_is_consistent(
    ads_user_client: AdsClient,
    api_test_user_uuid: UUID,
    platform: str,
) -> None:
    response = ads_user_client.get_config(api_test_user_uuid, platform=platform)

    assert_response_status(response, 200)
    config = validate_response_model(response, AdConfig)
    assert config.user_id == str(api_test_user_uuid)
    assert config.platform == platform
    assert config.provider
    assert config.ad_unit_id
    assert config.custom_data
    assert config.callback_url.startswith("/api/v2/ads/")


@allure.title("Legacy ad config validates required user and platform")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("user_id", "platform"),
    [(None, "android"), ("qa-user", "windows")],
)
def test_public_ad_config_rejects_invalid_input(
    ads_user_client: AdsClient,
    user_id: str | None,
    platform: str,
) -> None:
    response = ads_user_client.get_config(user_id, platform=platform)

    assert_response_status(response, 400)
    assert isinstance(response.json().get("error"), str)


@allure.title("Legacy ad status is public and internally consistent")
@pytest.mark.regression
def test_public_ad_status_is_consistent(
    ads_user_client: AdsClient,
    api_test_user_uuid: UUID,
) -> None:
    response = ads_user_client.get_status(api_test_user_uuid)

    assert_response_status(response, 200)
    status = validate_response_model(response, UserAdStatus)
    assert status.user_id == str(api_test_user_uuid)


@allure.title("Legacy ad status rejects a missing user_id")
@pytest.mark.regression
def test_public_ad_status_requires_user_id(ads_user_client: AdsClient) -> None:
    response = ads_user_client.get_status(None)

    assert_response_status(response, 400)
    assert isinstance(response.json().get("error"), str)


@allure.title("AppLovin callback rejects an invalid provider signature")
@pytest.mark.regression
def test_applovin_callback_rejects_invalid_signature(
    ads_user_client: AdsClient,
    api_test_user_uuid: UUID,
) -> None:
    response = ads_user_client.applovin_callback(
        {
            "user_id": str(api_test_user_uuid),
            "ad_unit_id": "qa-invalid-unit",
            "placement": "qa-invalid-placement",
            "custom_data": "qa.invalid",
            "event_id": f"qa-invalid-{uuid4()}",
            "token": "invalid-signature",
            "amount": 1,
            "currency": "soft",
        }
    )

    assert_response_status(response, 401)
    assert response.json().get("error") == "unauthorized"


@allure.title("Unity callback validates all required provider parameters")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("params", "expected_fragment"),
    [
        ({}, "oid"),
        ({"oid": "qa-offer"}, "sid"),
        ({"oid": "qa-offer", "sid": "qa-session"}, "hmac"),
    ],
)
def test_unity_callback_requires_provider_parameters(
    ads_user_client: AdsClient,
    params: dict[str, str],
    expected_fragment: str,
) -> None:
    response = ads_user_client.unity_callback(params)

    assert response.status_code == 400
    assert "text/plain" in response.headers.get("content-type", "")
    assert expected_fragment in response.text


@allure.title("Unity callback rejects an invalid HMAC")
@pytest.mark.regression
def test_unity_callback_rejects_invalid_hmac(ads_user_client: AdsClient) -> None:
    response = ads_user_client.unity_callback(
        {"sid": "qa.invalid", "oid": f"qa-{uuid4()}", "hmac": "00"}
    )

    assert response.status_code == 401
    assert response.text == "unauthorized"


@allure.title("Rewarded availability exposes coherent limits and provider options")
@pytest.mark.smoke
def test_rewarded_availability_is_coherent(ads_user_client: AdsClient) -> None:
    response = ads_user_client.get_availability(uuid4())

    assert_response_status(response, 200)
    availability = validate_success_data(response, Availability)
    _assert_limit_state(
        availability.global_.daily_limit,
        availability.global_.daily_used,
        availability.global_.daily_remaining,
    )
    _assert_limit_state(
        availability.global_.session_limit,
        availability.global_.session_used,
        availability.global_.session_remaining,
    )
    source_codes = [source.source_code for source in availability.sources]
    assert len(source_codes) == len(set(source_codes))
    for source in availability.sources:
        _assert_limit_state(
            source.limits.daily_limit,
            source.limits.daily_used,
            source.limits.daily_remaining,
        )
        option_ids = [option.source_provider_id for option in source.provider_options]
        assert len(option_ids) == len(set(option_ids))
        assert source.provider_options
        if source.available:
            assert availability.global_.enabled
            assert any(option.available for option in source.provider_options)
            assert source.disabled_reason is None
        else:
            assert source.disabled_reason is not None
        for option in source.provider_options:
            _assert_limit_state(
                option.limits.daily_limit,
                option.limits.daily_used,
                option.limits.daily_remaining,
            )
            assert bool(option.disabled_reason) is not option.available


@allure.title("Rewarded availability requires client_session_id")
@pytest.mark.regression
def test_rewarded_availability_requires_client_session_id(ads_user_client: AdsClient) -> None:
    response = ads_user_client.get_availability(None)

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Rewarded start validates required and typed identifiers")
@pytest.mark.regression
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "source_code": "qa-missing",
            "source_provider_id": str(uuid4()),
            "client_session_id": "not-a-uuid",
        },
        {
            "source_code": "qa-missing",
            "source_provider_id": "not-a-uuid",
            "client_session_id": str(uuid4()),
        },
    ],
)
def test_rewarded_start_rejects_invalid_request(
    ads_user_client: AdsClient,
    payload: dict[str, object],
) -> None:
    response = ads_user_client.start_rewarded_ad(payload)

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Placement lookup rejects malformed and unknown tokens")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("placement_token", "expected_status"),
    [("not-a-uuid", 400), (str(uuid4()), 404)],
)
def test_placement_lookup_rejects_invalid_token(
    ads_user_client: AdsClient,
    placement_token: str,
    expected_status: int,
) -> None:
    response = ads_user_client.get_placement(placement_token)

    assert_response_status(response, expected_status)
    validate_error_response(response)


@allure.title("Ads admin configuration lists are internally consistent")
@pytest.mark.smoke
def test_admin_configuration_lists_are_consistent(ads_admin_client: AdsClient) -> None:
    providers_response = ads_admin_client.admin_list_providers()
    sources_response = ads_admin_client.admin_list_sources()
    options_response = ads_admin_client.admin_list_source_providers(limit=20, offset=0)

    assert_response_status(providers_response, 200)
    assert_response_status(sources_response, 200)
    assert_response_status(options_response, 200)
    providers = validate_success_data(providers_response, AdminAdProviders)
    sources = validate_success_data(sources_response, AdminRewardedSources)
    options = validate_success_data(options_response, AdminSourceProviders)
    assert providers.total == len(providers.items)
    assert sources.total == len(sources.items)
    assert options.total >= len(options.items)
    provider_codes = {provider.provider_code for provider in providers.items}
    source_codes = {source.source_code for source in sources.items}
    assert len(provider_codes) == len(providers.items)
    assert len(source_codes) == len(sources.items)
    for source in sources.items:
        assert source.provider_code in provider_codes
    for option in options.items:
        assert option.provider_code in provider_codes
        assert option.source_code in source_codes


@allure.title("Ads admin item endpoints match their list representations")
@pytest.mark.regression
def test_admin_item_endpoints_match_lists(ads_admin_client: AdsClient) -> None:
    providers_response = ads_admin_client.admin_list_providers()
    sources_response = ads_admin_client.admin_list_sources()
    options_response = ads_admin_client.admin_list_source_providers(limit=1, offset=0)
    assert_response_status(providers_response, 200)
    assert_response_status(sources_response, 200)
    assert_response_status(options_response, 200)
    providers = validate_success_data(providers_response, AdminAdProviders)
    sources = validate_success_data(sources_response, AdminRewardedSources)
    options = validate_success_data(options_response, AdminSourceProviders)

    if providers.items:
        item_response = ads_admin_client.admin_get_provider(providers.items[0].provider_code)
        assert_response_status(item_response, 200)
        assert validate_success_data(item_response, AdminAdProvider) == providers.items[0]
    if sources.items:
        item_response = ads_admin_client.admin_get_source(sources.items[0].source_code)
        assert_response_status(item_response, 200)
        assert validate_success_data(item_response, type(sources.items[0])) == sources.items[0]
    if options.items:
        item_response = ads_admin_client.admin_get_source_provider(
            options.items[0].source_provider_id
        )
        assert_response_status(item_response, 200)
        assert validate_success_data(item_response, type(options.items[0])) == options.items[0]


@allure.title("Ads global admin configuration has valid limits")
@pytest.mark.smoke
def test_admin_global_config_has_valid_limits(ads_admin_client: AdsClient) -> None:
    response = ads_admin_client.admin_get_global_config()

    assert_response_status(response, 200)
    config = validate_success_data(response, AdminGlobalConfig)
    assert config.created_at <= config.updated_at


@allure.title("Ads admin configuration rejects negative limits without persisting them")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("operation", "payload"),
    [
        ("global", {"daily_limit_24h": -1}),
        (
            "provider-option",
            {
                "source_provider_id": str(uuid4()),
                "source_code": "qa-missing",
                "provider_code": "qa-missing",
                "ad_unit_id": "qa-invalid",
                "allowed_login_providers": ["google"],
                "enabled": False,
                "priority": 0,
                "daily_limit_24h": -1,
                "session_limit": 0,
                "cooldown_sec": 0,
            },
        ),
    ],
)
def test_admin_configuration_rejects_negative_limits(
    ads_admin_client: AdsClient,
    operation: str,
    payload: dict[str, object],
) -> None:
    if operation == "global":
        response = ads_admin_client.admin_patch_global_config(payload)
    else:
        response = ads_admin_client.admin_create_source_provider(payload)

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Ads admin views support documented filters and response contract")
@pytest.mark.smoke
def test_admin_views_are_consistent(
    ads_admin_client: AdsClient,
    api_test_user_uuid: UUID,
) -> None:
    response = ads_admin_client.admin_list_views(
        account_uuid=str(api_test_user_uuid), limit=10, offset=0
    )

    assert_response_status(response, 200)
    views = validate_success_data(response, AdminRewardedAdViews)
    assert views.total >= len(views.items)
    assert len(views.items) <= 10
    tokens = [view.placement_token for view in views.items]
    assert len(tokens) == len(set(tokens))
    assert all(view.account_uuid == api_test_user_uuid for view in views.items)
    assert all(view.started_at <= view.callback_accept_until for view in views.items)


@allure.title("Ads admin stats expose coherent non-negative aggregates")
@pytest.mark.smoke
def test_admin_stats_are_coherent(ads_admin_client: AdsClient) -> None:
    summary_response = ads_admin_client.admin_get_stats("summary")
    assert_response_status(summary_response, 200)
    summary = validate_success_data(summary_response, AdminRewardedStatsSummary)
    assert summary.callbacks_received <= summary.views_total
    assert summary.rewarded + summary.rejected + summary.failed <= summary.views_total
    assert summary.reward_attempts_failed <= summary.reward_attempts_total

    for dimension in (
        "timeseries",
        "by-source",
        "by-provider",
        "by-source-provider",
        "reject-reasons",
    ):
        response = ads_admin_client.admin_get_stats(dimension)
        assert_response_status(response, 200)
        stats = validate_success_data(response, AdminRewardedGroupStats)
        assert stats.total == len(stats.items)
        keys = [item.key for item in stats.items]
        assert len(keys) == len(set(keys))


@allure.title("Ads admin user diagnostics identify and consistently aggregate the test user")
@pytest.mark.regression
def test_admin_user_diagnostics_are_consistent(
    ads_admin_client: AdsClient,
    api_test_user_uuid: UUID,
) -> None:
    summary_response = ads_admin_client.admin_get_user_summary(api_test_user_uuid)
    views_response = ads_admin_client.admin_get_user_views(api_test_user_uuid)
    limits_response = ads_admin_client.admin_get_user_limits(api_test_user_uuid)
    attempts_response = ads_admin_client.admin_get_user_reward_attempts(api_test_user_uuid)

    for response in (summary_response, views_response, limits_response, attempts_response):
        assert_response_status(response, 200)
    diagnostics = validate_success_data(summary_response, AdminUserDiagnostics)
    views = validate_success_data(views_response, AdminRewardedAdViews)
    limits = validate_success_data(limits_response, AdminRewardedGroupStats)
    attempts = validate_success_data(attempts_response, AdminRewardIssueAttempts)
    assert diagnostics.account_uuid == api_test_user_uuid
    assert diagnostics.summary.views_total >= len(diagnostics.recent_views)
    assert views.total >= len(views.items)
    assert attempts.total >= len(attempts.items)
    assert limits.total == len(limits.items)
    assert all(view.account_uuid == api_test_user_uuid for view in views.items)


@allure.title("Ads admin lookups return 404 for unknown configuration and placement records")
@pytest.mark.regression
@pytest.mark.parametrize("resource", ["provider", "source", "source-provider", "view"])
def test_admin_lookup_returns_not_found(
    ads_admin_client: AdsClient,
    resource: str,
) -> None:
    if resource == "provider":
        response = ads_admin_client.admin_get_provider(f"qa-missing-{uuid4().hex}")
    elif resource == "source":
        response = ads_admin_client.admin_get_source(f"qa-missing-{uuid4().hex}")
    elif resource == "source-provider":
        response = ads_admin_client.admin_get_source_provider(uuid4())
    else:
        response = ads_admin_client.admin_get_view(uuid4())

    assert_response_status(response, 404)
    validate_error_response(response)


@allure.title("Ads admin user routes reject a malformed account UUID")
@pytest.mark.regression
@pytest.mark.parametrize("operation", ["summary", "views", "limits", "attempts"])
def test_admin_user_routes_reject_malformed_uuid(
    ads_admin_client: AdsClient,
    operation: str,
) -> None:
    if operation == "summary":
        response = ads_admin_client.admin_get_user_summary("not-a-uuid")
    elif operation == "views":
        response = ads_admin_client.admin_get_user_views("not-a-uuid")
    elif operation == "limits":
        response = ads_admin_client.admin_get_user_limits("not-a-uuid")
    else:
        response = ads_admin_client.admin_get_user_reward_attempts("not-a-uuid")

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Ads admin list routes reject malformed pagination")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("route", "filters"),
    [
        ("source-providers", {"limit": "ten"}),
        ("source-providers", {"offset": "minus-one"}),
        ("source-providers", {"limit": -1}),
        ("views", {"limit": "ten"}),
        ("views", {"offset": "minus-one"}),
        ("views", {"offset": -1}),
    ],
)
def test_admin_lists_reject_malformed_pagination(
    ads_admin_client: AdsClient,
    route: str,
    filters: dict[str, str | int],
) -> None:
    typed_filters = cast(dict[str, Any], filters)
    if route == "source-providers":
        response = ads_admin_client.admin_list_source_providers(**typed_filters)
    else:
        response = ads_admin_client.admin_list_views(**typed_filters)

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Ads admin list filters reject malformed typed values")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("route", "field", "value"),
    [
        ("source-providers", "enabled", "not-a-boolean"),
        ("views", "account_uuid", "not-a-uuid"),
        ("views", "client_session_id", "not-a-uuid"),
    ],
)
def test_admin_lists_reject_malformed_typed_filters(
    ads_admin_client: AdsClient,
    route: str,
    field: str,
    value: str,
) -> None:
    filters = cast(dict[str, Any], {field: value})
    if route == "source-providers":
        response = ads_admin_client.admin_list_source_providers(**filters)
    else:
        response = ads_admin_client.admin_list_views(**filters)

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Ads admin views validate documented started time filters")
@pytest.mark.regression
@pytest.mark.parametrize("field", ["started_from", "started_to"])
def test_admin_views_reject_invalid_documented_time_filter(
    ads_admin_client: AdsClient,
    field: str,
) -> None:
    if field == "started_from":
        response = ads_admin_client.admin_list_views(started_from="not-rfc3339")
    else:
        response = ads_admin_client.admin_list_views(started_to="not-rfc3339")

    assert_response_status(response, 400)
    validate_error_response(response)


def _call_protected_operation(
    client: AdsClient,
    account_uuid: UUID,
    operation: str,
    *,
    authenticated: bool,
) -> httpx.Response:
    unknown_uuid = uuid4()
    calls: dict[str, Callable[[], httpx.Response]] = {
        "availability": lambda: client.get_availability(unknown_uuid, authenticated=authenticated),
        "start": lambda: client.start_rewarded_ad({}, authenticated=authenticated),
        "placement": lambda: client.get_placement(unknown_uuid, authenticated=authenticated),
        "admin-get-global-config": lambda: client.admin_get_global_config(
            authenticated=authenticated
        ),
        "admin-patch-global-config": lambda: client.admin_patch_global_config(
            {}, authenticated=authenticated
        ),
        "admin-put-global-config": lambda: client.admin_upsert_global_config(
            {}, authenticated=authenticated
        ),
        "admin-list-providers": lambda: client.admin_list_providers(authenticated=authenticated),
        "admin-create-provider": lambda: client.admin_create_provider(
            {}, authenticated=authenticated
        ),
        "admin-get-provider": lambda: client.admin_get_provider(
            "qa-missing", authenticated=authenticated
        ),
        "admin-patch-provider": lambda: client.admin_patch_provider(
            "qa-missing", {}, authenticated=authenticated
        ),
        "admin-put-provider": lambda: client.admin_upsert_provider(
            "qa-missing", {}, authenticated=authenticated
        ),
        "admin-list-sources": lambda: client.admin_list_sources(authenticated=authenticated),
        "admin-create-source": lambda: client.admin_create_source({}, authenticated=authenticated),
        "admin-get-source": lambda: client.admin_get_source(
            "qa-missing", authenticated=authenticated
        ),
        "admin-patch-source": lambda: client.admin_patch_source(
            "qa-missing", {}, authenticated=authenticated
        ),
        "admin-put-source": lambda: client.admin_upsert_source(
            "qa-missing", {}, authenticated=authenticated
        ),
        "admin-list-source-providers": lambda: client.admin_list_source_providers(
            authenticated=authenticated
        ),
        "admin-create-source-provider": lambda: client.admin_create_source_provider(
            {}, authenticated=authenticated
        ),
        "admin-get-source-provider": lambda: client.admin_get_source_provider(
            unknown_uuid, authenticated=authenticated
        ),
        "admin-patch-source-provider": lambda: client.admin_patch_source_provider(
            unknown_uuid, {}, authenticated=authenticated
        ),
        "admin-put-source-provider": lambda: client.admin_upsert_source_provider(
            unknown_uuid, {}, authenticated=authenticated
        ),
        "admin-list-views": lambda: client.admin_list_views(authenticated=authenticated),
        "admin-get-view": lambda: client.admin_get_view(unknown_uuid, authenticated=authenticated),
        "admin-view-attempts": lambda: client.admin_get_view_reward_attempts(
            unknown_uuid, authenticated=authenticated
        ),
        "admin-user-summary": lambda: client.admin_get_user_summary(
            account_uuid, authenticated=authenticated
        ),
        "admin-user-views": lambda: client.admin_get_user_views(
            account_uuid, authenticated=authenticated
        ),
        "admin-user-limits": lambda: client.admin_get_user_limits(
            account_uuid, authenticated=authenticated
        ),
        "admin-user-attempts": lambda: client.admin_get_user_reward_attempts(
            account_uuid, authenticated=authenticated
        ),
        "admin-stats-summary": lambda: client.admin_get_stats(
            "summary", authenticated=authenticated
        ),
        "admin-stats-timeseries": lambda: client.admin_get_stats(
            "timeseries", authenticated=authenticated
        ),
        "admin-stats-by-source": lambda: client.admin_get_stats(
            "by-source", authenticated=authenticated
        ),
        "admin-stats-by-provider": lambda: client.admin_get_stats(
            "by-provider", authenticated=authenticated
        ),
        "admin-stats-by-source-provider": lambda: client.admin_get_stats(
            "by-source-provider", authenticated=authenticated
        ),
        "admin-stats-reject-reasons": lambda: client.admin_get_stats(
            "reject-reasons", authenticated=authenticated
        ),
    }
    return calls[operation]()


def _assert_limit_state(limit: int, used: int, remaining: int) -> None:
    assert used >= 0
    if limit == 0:
        assert remaining > 0
    else:
        assert remaining == max(limit - used, 0)
