from __future__ import annotations

import sys
from datetime import UTC, datetime
from uuid import UUID, uuid4

import allure
import pytest

from qa_automation.clients.base import (
    assert_response_status,
    attach_response_diagnostics,
    validate_error_response,
    validate_response_model,
    validate_success_data,
)
from qa_automation.clients.profile import ProfileClient
from qa_automation.config import Settings
from qa_automation.models.profile import (
    LocalizationResponse,
    PreparedShareMessage,
    Profile,
    ProfileContextResponse,
    ProfileSearchResults,
    ProfileServiceError,
    ProfileSettings,
    ProfileStatistics,
    PublicProfile,
    PublishedProfile,
    ReferralsPage,
    Squad,
)

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Profile")]


@allure.title("Profile operation requires authentication: {operation}")
@pytest.mark.regression
@pytest.mark.parametrize(
    "operation",
    [
        "me",
        "account",
        "settings",
        "update-settings",
        "referrals",
        "restore-referral",
        "share",
        "room-share",
        "team-share",
        "context",
        "localization",
        "username",
        "delete-me",
        "restore-me",
    ],
)
def test_profile_operations_require_authentication(
    profile_user_client: ProfileClient,
    api_test_user_uuid: UUID,
    operation: str,
) -> None:
    if operation == "me":
        response = profile_user_client.get_me(authenticated=False)
    elif operation == "account":
        response = profile_user_client.get_profile(api_test_user_uuid, authenticated=False)
    elif operation == "settings":
        response = profile_user_client.get_settings(authenticated=False)
    elif operation == "update-settings":
        response = profile_user_client.update_settings({}, authenticated=False)
    elif operation == "referrals":
        response = profile_user_client.get_referrals(authenticated=False)
    elif operation == "restore-referral":
        response = profile_user_client.restore_referral(None, authenticated=False)
    elif operation == "share":
        response = profile_user_client.get_share_message(authenticated=False)
    elif operation == "room-share":
        response = profile_user_client.get_room_share_message("qa-room", authenticated=False)
    elif operation == "team-share":
        response = profile_user_client.get_team_share_message(1, authenticated=False)
    elif operation == "context":
        response = profile_user_client.get_context_info(authenticated=False)
    elif operation == "localization":
        response = profile_user_client.update_localization(None, authenticated=False)
    elif operation == "username":
        response = profile_user_client.update_username(None, authenticated=False)
    elif operation == "delete-me":
        response = profile_user_client.delete_me(authenticated=False)
    else:
        response = profile_user_client.restore_me(authenticated=False)

    assert_response_status(response, 401)
    validate_error_response(response)


@allure.title("Profile /me identifies the JWT subject and exposes consistent state")
@pytest.mark.smoke
def test_profile_me_is_consistent(
    profile_user_client: ProfileClient,
    api_test_user_uuid: UUID,
) -> None:
    response = profile_user_client.get_me()

    assert_response_status(response, 200)
    profile = validate_success_data(response, Profile)
    assert profile.account_uuid == api_test_user_uuid
    assert profile.created_at <= datetime.now(UTC)
    assert profile.deleted_at is None
    if profile.premium.active:
        assert profile.premium.expiration is not None
        assert profile.premium.expiration > datetime.now(UTC)
    else:
        assert profile.premium.expiration is None
    _assert_squad_is_coherent(profile.squad)


@allure.title("Ordinary user profile view omits private Premium state")
@pytest.mark.regression
def test_ordinary_user_profile_view_omits_premium(
    profile_user_client: ProfileClient,
    api_test_user_uuid: UUID,
) -> None:
    me_response = profile_user_client.get_me()
    public_response = profile_user_client.get_profile(api_test_user_uuid)

    assert_response_status(me_response, 200)
    assert_response_status(public_response, 200)
    me = validate_success_data(me_response, Profile)
    public = validate_success_data(public_response, PublicProfile)
    _assert_same_public_profile(me, public)
    assert public.premium is None


@allure.title("Admin profile view exposes the same Premium state as /me")
@pytest.mark.regression
def test_admin_profile_view_matches_me(
    profile_user_client: ProfileClient,
    profile_admin_client: ProfileClient,
    api_test_user_uuid: UUID,
) -> None:
    me_response = profile_user_client.get_me()
    admin_response = profile_admin_client.get_profile(api_test_user_uuid)

    assert_response_status(me_response, 200)
    assert_response_status(admin_response, 200)
    me = validate_success_data(me_response, Profile)
    admin = validate_success_data(admin_response, PublicProfile)
    _assert_same_public_profile(me, admin)
    assert admin.premium == me.premium


@allure.title("Profile lookup rejects malformed UUID")
@pytest.mark.regression
def test_profile_lookup_rejects_malformed_uuid(
    profile_user_client: ProfileClient,
) -> None:
    response = profile_user_client.get_profile("not-a-uuid")

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Profile lookup returns not found for an unknown account")
@pytest.mark.regression
def test_profile_lookup_returns_not_found(profile_user_client: ProfileClient) -> None:
    response = profile_user_client.get_profile(uuid4())

    assert_response_status(response, 404)
    validate_error_response(response)


@allure.title("Public Profile statistics exposes a non-negative player count")
@pytest.mark.smoke
def test_profile_statistics_is_public_and_valid(
    profile_user_client: ProfileClient,
) -> None:
    response = profile_user_client.get_statistics()

    assert_response_status(response, 200)
    statistics = validate_success_data(response, ProfileStatistics)
    assert statistics.total_players > 0


@allure.title("Profile referrals respect pagination and response invariants")
@pytest.mark.smoke
def test_profile_referrals_are_consistent(profile_user_client: ProfileClient) -> None:
    response = profile_user_client.get_referrals(limit=1, offset=0)

    assert_response_status(response, 200)
    page = validate_success_data(response, ReferralsPage)
    assert page.limit == 1
    assert page.offset == 0
    assert len(page.referrals) <= 1
    assert page.total >= len(page.referrals)
    ids = [referral.account_uuid for referral in page.referrals]
    assert len(ids) == len(set(ids))
    for referral in page.referrals:
        assert referral.created_at.date() <= datetime.now(UTC).date()


@allure.title("Profile referrals cap the documented maximum page size")
@pytest.mark.regression
def test_profile_referrals_cap_page_size(profile_user_client: ProfileClient) -> None:
    response = profile_user_client.get_referrals(limit=51, offset=0)

    assert_response_status(response, 200)
    page = validate_success_data(response, ReferralsPage)
    assert page.limit == 50
    assert len(page.referrals) <= 50


@allure.title("Profile referrals reject malformed pagination: {case}")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("case", "limit", "offset"),
    [
        ("non-integer limit", "ten", 0),
        ("non-integer offset", 10, "zero"),
        ("negative limit", -1, 0),
        ("negative offset", 10, -1),
    ],
)
def test_profile_referrals_reject_malformed_pagination(
    profile_user_client: ProfileClient,
    case: str,
    limit: object,
    offset: object,
) -> None:
    response = profile_user_client.get_referrals(limit=limit, offset=offset)

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Admin and user referral views agree for the same account")
@pytest.mark.regression
def test_admin_and_user_referral_views_agree(
    profile_user_client: ProfileClient,
    profile_admin_client: ProfileClient,
    api_test_user_uuid: UUID,
) -> None:
    user_response = profile_user_client.get_referrals(limit=10, offset=0)
    admin_response = profile_admin_client.admin_get_referrals(
        api_test_user_uuid, limit=10, offset=0
    )

    assert_response_status(user_response, 200)
    assert_response_status(admin_response, 200)
    assert validate_success_data(admin_response, ReferralsPage) == validate_success_data(
        user_response, ReferralsPage
    )


@allure.title("Profile share endpoints return prepared message identifiers")
@pytest.mark.regression
def test_profile_share_endpoints_return_message_ids(
    profile_share_client: ProfileClient,
) -> None:
    responses = [
        profile_share_client.get_share_message(),
        profile_share_client.get_room_share_message("qa-automation-room"),
        profile_share_client.get_team_share_message(1),
    ]

    for response in responses:
        assert_response_status(response, 200)
        message = validate_success_data(response, PreparedShareMessage)
        assert message.prepared_message_id.strip()


@allure.title("Profile share endpoints reject missing or malformed identifiers")
@pytest.mark.regression
def test_profile_share_endpoints_validate_identifiers(
    profile_user_client: ProfileClient,
) -> None:
    responses = [
        profile_user_client.get_room_share_message(None),
        profile_user_client.get_team_share_message(None),
        profile_user_client.get_team_share_message("team"),
    ]

    for response in responses:
        assert_response_status(response, 400)
        validate_error_response(response)


@allure.title("Profile context endpoint returns a JSON object")
@pytest.mark.regression
def test_profile_context_returns_object(profile_user_client: ProfileClient) -> None:
    response = profile_user_client.get_context_info()

    assert_response_status(response, 200)
    validate_response_model(response, ProfileContextResponse)


@allure.title("Profile settings expose a versioned JSON object")
@pytest.mark.smoke
def test_profile_settings_are_versioned(profile_user_client: ProfileClient) -> None:
    response = profile_user_client.get_settings()

    assert_response_status(response, 200)
    settings = validate_success_data(response, ProfileSettings)
    if settings.version == 0:
        assert settings.updated_at is None
        assert settings.settings == {}
    else:
        assert settings.updated_at is not None


@allure.title("Profile settings reject invalid patches: {case}")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("case", "payload_kind"),
    [
        ("missing version", "missing-version"),
        ("missing settings", "missing-settings"),
        ("unknown top-level key", "unknown-key"),
        ("null setting", "null-setting"),
        ("non-object settings", "non-object"),
    ],
)
def test_profile_settings_reject_invalid_patches(
    profile_user_client: ProfileClient,
    case: str,
    payload_kind: str,
) -> None:
    current_response = profile_user_client.get_settings()
    assert_response_status(current_response, 200)
    version = validate_success_data(current_response, ProfileSettings).version
    payloads: dict[str, dict[str, object]] = {
        "missing-version": {"settings": {}},
        "missing-settings": {"version": version},
        "unknown-key": {"version": version, "settings": {"unknown": {}}},
        "null-setting": {"version": version, "settings": {"audio": {"volume": None}}},
        "non-object": {"version": version, "settings": []},
    }

    response = profile_user_client.update_settings(payloads[payload_kind])

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Profile settings reject a stale optimistic-lock version")
@pytest.mark.regression
def test_profile_settings_reject_version_conflict(
    profile_user_client: ProfileClient,
) -> None:
    current_response = profile_user_client.get_settings()
    assert_response_status(current_response, 200)
    current = validate_success_data(current_response, ProfileSettings)

    response = profile_user_client.update_settings(
        {
            "version": current.version + 1,
            "settings": {"notifications": {"qa_profile_probe": True}},
        }
    )

    assert_response_status(response, 409)
    validate_error_response(response)


@allure.title("Profile localization validates a non-empty locale: {locale}")
@pytest.mark.regression
@pytest.mark.parametrize("locale", [None, "", "   "])
def test_profile_localization_rejects_empty_locale(
    profile_user_client: ProfileClient,
    locale: str | None,
) -> None:
    response = profile_user_client.update_localization(locale)

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Profile username validates documented format: {username}")
@pytest.mark.regression
@pytest.mark.parametrize("username", [None, "abcd", "a" * 33, "invalid name"])
def test_profile_username_rejects_invalid_format(
    profile_user_client: ProfileClient,
    username: str | None,
) -> None:
    response = profile_user_client.update_username(username)

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Ordinary user cannot call Profile admin read route: {operation}")
@pytest.mark.regression
@pytest.mark.parametrize(
    "operation",
    ["search", "referrals"],
)
def test_profile_admin_read_routes_reject_ordinary_user(
    profile_user_client: ProfileClient,
    api_test_user_uuid: UUID,
    operation: str,
) -> None:
    if operation == "search":
        response = profile_user_client.admin_search(str(api_test_user_uuid))
    else:
        response = profile_user_client.admin_get_referrals(api_test_user_uuid)

    assert_response_status(response, 403)
    validate_error_response(response)


@allure.title("Ordinary user cannot call destructive Profile admin mutation: {operation}")
@pytest.mark.regression
@pytest.mark.serial
@pytest.mark.parametrize("operation", ["assign", "delete-referral", "ban", "unban", "delete"])
def test_profile_admin_mutations_reject_ordinary_user_safely(
    profile_user_client: ProfileClient,
    destructive_rbac_target_uuid: UUID,
    operation: str,
) -> None:
    if operation == "assign":
        response = profile_user_client.admin_assign_referral(
            destructive_rbac_target_uuid, str(uuid4())
        )
    elif operation == "delete-referral":
        response = profile_user_client.admin_delete_referral(destructive_rbac_target_uuid)
    elif operation == "ban":
        response = profile_user_client.admin_ban(destructive_rbac_target_uuid)
    elif operation == "unban":
        response = profile_user_client.admin_unban(destructive_rbac_target_uuid)
    else:
        response = profile_user_client.admin_delete_account(destructive_rbac_target_uuid)

    assert_response_status(response, 403)
    validate_error_response(response)


@allure.title("Profile admin search finds the test account by UUID")
@pytest.mark.smoke
def test_profile_admin_search_finds_test_account(
    profile_admin_client: ProfileClient,
    api_test_user_uuid: UUID,
) -> None:
    response = profile_admin_client.admin_search(str(api_test_user_uuid))

    assert_response_status(response, 200)
    results = validate_success_data(response, ProfileSearchResults).root
    assert any(profile.account_uuid == api_test_user_uuid for profile in results)


@allure.title("Profile admin search requires a non-empty query")
@pytest.mark.regression
def test_profile_admin_search_requires_query(
    profile_admin_client: ProfileClient,
) -> None:
    response = profile_admin_client.admin_search(None)

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Profile admin mutations validate account UUID before changing state")
@pytest.mark.regression
def test_profile_admin_mutations_reject_malformed_uuid(
    profile_admin_client: ProfileClient,
) -> None:
    responses = [
        profile_admin_client.admin_ban("not-a-uuid"),
        profile_admin_client.admin_unban("not-a-uuid"),
        profile_admin_client.admin_delete_account("not-a-uuid"),
        profile_admin_client.admin_assign_referral("not-a-uuid", str(uuid4())),
        profile_admin_client.admin_delete_referral("not-a-uuid"),
    ]

    for response in responses:
        assert_response_status(response, 400)
        validate_error_response(response)


@allure.title("Profile locale can be changed and restored")
@pytest.mark.serial
def test_profile_locale_can_be_changed_and_restored(
    profile_user_client: ProfileClient,
    profile_mutation_settings: Settings,
) -> None:
    del profile_mutation_settings
    before_response = profile_user_client.get_me()
    assert_response_status(before_response, 200)
    before = validate_success_data(before_response, Profile)
    if not before.locale.strip():
        pytest.skip(
            "TEST_DATA_DEFECT: original locale is empty and cannot be restored through the API"
        )
    temporary_locale = "en" if before.locale != "en" else "ru"

    update_response = profile_user_client.update_localization(temporary_locale)
    try:
        assert_response_status(update_response, 200)
        update = validate_success_data(update_response, LocalizationResponse)
        assert update.locale == temporary_locale
        changed_response = profile_user_client.get_me()
        assert_response_status(changed_response, 200)
        assert validate_success_data(changed_response, Profile).locale == temporary_locale
    finally:
        active_error = sys.exc_info()[0]
        restore_response = profile_user_client.update_localization(before.locale)
        if restore_response.status_code != 200:
            attach_response_diagnostics(restore_response)
        if active_error is None:
            assert_response_status(restore_response, 200)
            restored_response = profile_user_client.get_me()
            assert_response_status(restored_response, 200)
            assert validate_success_data(restored_response, Profile).locale == before.locale


@allure.title("Profile /me success follows its published OpenAPI top-level schema")
@pytest.mark.contract
def test_profile_me_matches_published_openapi_contract(
    profile_user_client: ProfileClient,
) -> None:
    response = profile_user_client.get_me()

    assert_response_status(response, 200)
    validate_response_model(response, Profile)


@allure.title("Profile /me data follows the published OpenAPI field schema")
@pytest.mark.contract
def test_profile_me_data_matches_published_openapi_contract(
    profile_user_client: ProfileClient,
) -> None:
    response = profile_user_client.get_me()

    assert_response_status(response, 200)
    validate_success_data(response, PublishedProfile)


@allure.title("Profile unauthorized response follows its published OpenAPI schema")
@pytest.mark.contract
def test_profile_error_matches_published_openapi_contract(
    profile_user_client: ProfileClient,
) -> None:
    response = profile_user_client.get_me(authenticated=False)

    assert_response_status(response, 401)
    validate_response_model(response, ProfileServiceError)


@allure.title("Published Profile account-restore route is protected and callable")
@pytest.mark.contract
def test_documented_profile_restore_route_is_callable(
    profile_user_client: ProfileClient,
    api_test_user_uuid: UUID,
) -> None:
    response = profile_user_client.restore_documented_account(
        api_test_user_uuid, authenticated=False
    )

    assert_response_status(response, 401)
    validate_error_response(response)


def _assert_same_public_profile(private: Profile, public: PublicProfile) -> None:
    assert public.account_uuid == private.account_uuid
    assert public.username == private.username
    assert public.first_name == private.first_name
    assert public.last_name == private.last_name
    assert public.locale == private.locale
    assert public.avatar == private.avatar
    assert public.created_at == private.created_at
    assert public.is_guest is private.is_guest
    assert public.squad == private.squad


def _assert_squad_is_coherent(squad: Squad | None) -> None:
    if squad is None:
        return
    if squad.id is None:
        assert squad.name is None
        assert squad.slug is None
        assert squad.logo is None
        return
    assert squad.id > 0
    assert squad.name is not None and squad.name.strip()
    assert squad.slug is not None and squad.slug.strip()
    assert squad.logo is not None and squad.logo.strip()
