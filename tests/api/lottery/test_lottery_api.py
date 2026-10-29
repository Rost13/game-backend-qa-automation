from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import allure
import httpx
import pytest

from qa_automation.clients.base import (
    assert_response_status,
    attach_response_diagnostics,
    validate_error_response,
    validate_success_data,
)
from qa_automation.clients.lottery import LotteryClient
from qa_automation.models.lottery import (
    ChestConfig,
    ConfigVersion,
    ListConfigsResponse,
    ListOpeningsResponse,
    LotteryConfig,
    LotteryResponse,
    ProbabilitiesResponse,
    SeasonConfig,
)

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Lottery")]


@allure.title("Lottery user endpoint requires authentication: {operation}")
@pytest.mark.smoke
@pytest.mark.parametrize("operation", ["lottery", "openings", "open-chest"])
def test_lottery_user_routes_require_authentication(
    lottery_user_client: LotteryClient,
    operation: str,
) -> None:
    if operation == "lottery":
        response = lottery_user_client.get_lottery(authenticated=False)
    elif operation == "openings":
        response = lottery_user_client.list_openings(authenticated=False)
    else:
        response = lottery_user_client.open_chest(
            "qa-missing-chest",
            1,
            f"qa-unauth-{uuid4()}",
            authenticated=False,
        )

    assert_response_status(response, 401)
    _assert_json_error(response)


@allure.title("Lottery admin endpoint requires authentication: {operation}")
@pytest.mark.regression
@pytest.mark.parametrize(
    "operation",
    [
        "list",
        "create",
        "get",
        "update",
        "archive",
        "clone",
        "probabilities",
        "publish",
        "validate",
    ],
)
def test_lottery_admin_routes_require_authentication(
    lottery_admin_client: LotteryClient,
    operation: str,
) -> None:
    response = _call_admin_route(lottery_admin_client, operation, authenticated=False)

    assert_response_status(response, 401)
    _assert_json_error(response)


@allure.title("Ordinary user cannot call Lottery admin endpoint: {operation}")
@pytest.mark.regression
@pytest.mark.parametrize(
    "operation",
    [
        "list",
        "create",
        "get",
        "update",
        "archive",
        "clone",
        "probabilities",
        "publish",
        "validate",
    ],
)
def test_lottery_admin_routes_reject_ordinary_user(
    lottery_user_client: LotteryClient,
    operation: str,
) -> None:
    response = _call_admin_route(lottery_user_client, operation, authenticated=True)

    assert_response_status(response, 403)
    _assert_json_error(response)


@allure.title("User receives a coherent active Lottery season")
@pytest.mark.smoke
def test_active_lottery_season_is_consistent(lottery_user_client: LotteryClient) -> None:
    response = lottery_user_client.get_lottery()

    assert_response_status(response, 200)
    lottery = validate_success_data(response, LotteryResponse)
    assert lottery.config_version > 0
    assert lottery.keys_balance >= 0
    _assert_active_season(_require_active_season(lottery))


@allure.title("Lottery opening history is scoped, unique, and newest first")
@pytest.mark.smoke
def test_lottery_opening_history_is_consistent(
    lottery_user_client: LotteryClient,
    api_test_user_uuid: UUID,
) -> None:
    response = lottery_user_client.list_openings(limit=20)

    assert_response_status(response, 200)
    history = validate_success_data(response, ListOpeningsResponse)
    assert len(history.items) <= 20
    opening_ids = [opening.opening_id for opening in history.items]
    assert len(opening_ids) == len(set(opening_ids)), "opening IDs must be unique"
    assert all(opening.account_uuid == api_test_user_uuid for opening in history.items)
    assert [opening.created_at for opening in history.items] == sorted(
        (opening.created_at for opening in history.items), reverse=True
    )
    for opening in history.items:
        assert opening.chest_id.strip()
        assert opening.season_id.strip()
        assert opening.reward_id.strip()
        assert opening.reward_type.strip()
        assert opening.status.strip()


@allure.title("Lottery opening history rejects malformed limit: {limit}")
@pytest.mark.regression
@pytest.mark.parametrize("limit", ["ten", -1])
def test_lottery_opening_history_rejects_malformed_limit(
    lottery_user_client: LotteryClient,
    limit: object,
) -> None:
    response = lottery_user_client.list_openings(limit=limit)

    assert_response_status(response, 400)
    _assert_error(response, "invalid_pagination")


@allure.title("Lottery chest opening requires valid request fields: {case}")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("case", "quantity", "idempotency_key"),
    [
        ("missing quantity", None, "qa-invalid-missing-quantity"),
        ("non-integer quantity", "one", "qa-invalid-string-quantity"),
        ("zero quantity", 0, "qa-invalid-zero-quantity"),
        ("negative quantity", -1, "qa-invalid-negative-quantity"),
        ("missing idempotency key", 1, None),
    ],
)
def test_lottery_chest_opening_validates_request(
    lottery_user_client: LotteryClient,
    case: str,
    quantity: object | None,
    idempotency_key: str | None,
) -> None:
    response = lottery_user_client.open_chest(
        "qa-chest-that-does-not-exist",
        quantity,
        idempotency_key,
    )

    assert_response_status(response, 400)
    _assert_error(response, "invalid_request")


@allure.title("Lottery rejects an unknown chest without spending keys")
@pytest.mark.regression
def test_lottery_rejects_unknown_chest(lottery_user_client: LotteryClient) -> None:
    before_response = lottery_user_client.get_lottery()
    assert_response_status(before_response, 200)
    before = validate_success_data(before_response, LotteryResponse)

    response = lottery_user_client.open_chest(
        "qa-chest-that-does-not-exist",
        1,
        f"qa-unknown-chest-{uuid4()}",
    )

    assert_response_status(response, 404)
    _assert_error(response, "not_found")
    after_response = lottery_user_client.get_lottery()
    assert_response_status(after_response, 200)
    assert validate_success_data(after_response, LotteryResponse).keys_balance == (
        before.keys_balance
    )


@allure.title("Lottery admin config list has unique versions and valid configs")
@pytest.mark.smoke
def test_lottery_admin_config_list_is_consistent(
    lottery_admin_client: LotteryClient,
) -> None:
    response = lottery_admin_client.list_configs(limit=10)

    assert_response_status(response, 200)
    configs = validate_success_data(response, ListConfigsResponse)
    assert configs.items, "ENVIRONMENT_DEFECT: Lottery has no config versions in dev"
    assert len(configs.items) <= 10
    versions = [item.version for item in configs.items]
    assert len(versions) == len(set(versions)), "config versions must be unique"
    for item in configs.items:
        assert item.status.strip()
        assert item.created_by.strip()
        assert item.created_at <= item.updated_at
        if item.status.casefold() in {"active", "published"}:
            assert item.config.max_open_quantity > 0
            assert item.config.seasons
        _assert_config(item.config)


@allure.title("Lottery public season is a valid account-filtered config projection")
@pytest.mark.regression
def test_lottery_public_season_matches_account_filtered_admin_config(
    lottery_user_client: LotteryClient,
    lottery_admin_client: LotteryClient,
) -> None:
    lottery_response = lottery_user_client.get_lottery()
    assert_response_status(lottery_response, 200)
    lottery = validate_success_data(lottery_response, LotteryResponse)
    active_season = _require_active_season(lottery)

    config_response = lottery_admin_client.get_config(lottery.config_version)
    assert_response_status(config_response, 200)
    version = validate_success_data(config_response, ConfigVersion)
    assert version.version == lottery.config_version
    matching = [season for season in version.config.seasons if season.id == active_season.id]
    assert len(matching) == 1
    _assert_public_season_matches_config(active_season, matching[0])


@allure.title("Lottery excludes ineligible rewards and recalculates account probabilities")
@pytest.mark.regression
def test_lottery_recalculates_probabilities_after_account_reward_filtering(
    lottery_user_client: LotteryClient,
    lottery_admin_client: LotteryClient,
) -> None:
    lottery_response = lottery_user_client.get_lottery()
    assert_response_status(lottery_response, 200)
    lottery = validate_success_data(lottery_response, LotteryResponse)
    public_season = _require_active_season(lottery)
    config_response = lottery_admin_client.get_config(lottery.config_version)
    assert_response_status(config_response, 200)
    config = validate_success_data(config_response, ConfigVersion)
    configured_season = next(
        (season for season in config.config.seasons if season.id == public_season.id),
        None,
    )
    assert configured_season is not None
    configured_chests = {chest.id: chest for chest in configured_season.chests}
    filtered_chests = [
        public_chest
        for public_chest in public_season.chests
        if len(public_chest.reward_pool) < len(configured_chests[public_chest.id].reward_pool)
    ]
    if not filtered_chests:
        pytest.fail(
            "TEST_DATA_DEFECT: the test account has no filtered one-time Lottery reward",
            pytrace=False,
        )
    for chest in filtered_chests:
        configured_ids = {reward.id for reward in configured_chests[chest.id].reward_pool}
        public_ids = {reward.id for reward in chest.reward_pool}
        assert configured_ids - public_ids, "at least one ineligible reward must be excluded"
        assert public_ids <= configured_ids
        assert sum(reward.probability for reward in chest.reward_pool) == pytest.approx(1.0)
        total_weight = sum(reward.weight for reward in chest.reward_pool)
        for reward in chest.reward_pool:
            assert reward.probability == pytest.approx(reward.weight / total_weight)


@allure.title("Lottery probabilities endpoint agrees with the stored config")
@pytest.mark.regression
def test_lottery_probabilities_match_config(
    lottery_user_client: LotteryClient,
    lottery_admin_client: LotteryClient,
) -> None:
    lottery_response = lottery_user_client.get_lottery()
    assert_response_status(lottery_response, 200)
    lottery = validate_success_data(lottery_response, LotteryResponse)
    config_response = lottery_admin_client.get_config(lottery.config_version)
    probabilities_response = lottery_admin_client.get_probabilities(lottery.config_version)

    assert_response_status(config_response, 200)
    assert_response_status(probabilities_response, 200)
    config = validate_success_data(config_response, ConfigVersion)
    probabilities = validate_success_data(probabilities_response, ProbabilitiesResponse)
    assert probabilities.version == config.version
    assert probabilities.config == config.config


@allure.title("Lottery config status filter returns only the requested status")
@pytest.mark.regression
def test_lottery_admin_config_status_filter_is_applied(
    lottery_admin_client: LotteryClient,
) -> None:
    initial_response = lottery_admin_client.list_configs(limit=10)
    assert_response_status(initial_response, 200)
    initial = validate_success_data(initial_response, ListConfigsResponse)
    if not initial.items:
        pytest.fail("ENVIRONMENT_DEFECT: Lottery has no config versions in dev", pytrace=False)
    selected_status = initial.items[0].status

    filtered_response = lottery_admin_client.list_configs(status=selected_status, limit=10)

    assert_response_status(filtered_response, 200)
    filtered = validate_success_data(filtered_response, ListConfigsResponse)
    assert filtered.items
    assert all(item.status == selected_status for item in filtered.items)


@allure.title("Lottery admin config list rejects malformed pagination: {case}")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("case", "cursor", "limit"),
    [
        ("non-integer cursor", "cursor", 10),
        ("negative cursor", -1, 10),
        ("non-integer limit", None, "ten"),
        ("negative limit", None, -1),
    ],
)
def test_lottery_admin_config_list_rejects_malformed_pagination(
    lottery_admin_client: LotteryClient,
    case: str,
    cursor: object | None,
    limit: object,
) -> None:
    response = lottery_admin_client.list_configs(cursor=cursor, limit=limit)

    assert_response_status(response, 400)
    _assert_error(response, "invalid_pagination")


@allure.title("Lottery admin version routes reject a malformed version: {operation}")
@pytest.mark.regression
@pytest.mark.parametrize(
    "operation",
    ["get", "update", "archive", "clone", "probabilities", "publish", "validate"],
)
def test_lottery_admin_version_routes_reject_malformed_version(
    lottery_admin_client: LotteryClient,
    operation: str,
) -> None:
    response = _call_admin_version_route(lottery_admin_client, operation, "not-a-version")

    assert_response_status(response, 400)
    _assert_error(response, "invalid_request")


@allure.title("Lottery admin returns not found for an unknown config version")
@pytest.mark.regression
def test_lottery_admin_rejects_unknown_config_version(
    lottery_admin_client: LotteryClient,
) -> None:
    response = lottery_admin_client.get_config(9_223_372_036_854_775_000)

    assert_response_status(response, 404)
    _assert_error(response, "not_found")


@allure.title("Lottery config creation requires a config body")
@pytest.mark.regression
def test_lottery_admin_config_creation_requires_config(
    lottery_admin_client: LotteryClient,
) -> None:
    response = lottery_admin_client.create_config({})

    if response.status_code == 200:
        created = validate_success_data(response, ConfigVersion)
        archive_response = lottery_admin_client.archive_config(created.version)
        if archive_response.status_code != 200:
            attach_response_diagnostics(archive_response)
    assert_response_status(response, 400)
    _assert_error(response, "invalid_request")


@allure.title("Lottery success body follows the envelope schema published by Swagger")
@pytest.mark.contract
def test_lottery_success_matches_published_envelope_contract(
    lottery_user_client: LotteryClient,
) -> None:
    response = lottery_user_client.get_lottery()

    assert_response_status(response, 200)
    validate_success_data(response, LotteryResponse)


@allure.title("Lottery opening history follows the envelope schema published by Swagger")
@pytest.mark.contract
def test_lottery_history_matches_published_envelope_contract(
    lottery_user_client: LotteryClient,
) -> None:
    response = lottery_user_client.list_openings(limit=1)

    assert_response_status(response, 200)
    validate_success_data(response, ListOpeningsResponse)


@allure.title("Lottery admin config list follows the envelope schema published by Swagger")
@pytest.mark.contract
def test_lottery_config_list_matches_published_envelope_contract(
    lottery_admin_client: LotteryClient,
) -> None:
    response = lottery_admin_client.list_configs(limit=1)

    assert_response_status(response, 200)
    validate_success_data(response, ListConfigsResponse)


def _call_admin_route(
    client: LotteryClient,
    operation: str,
    *,
    authenticated: bool,
) -> httpx.Response:
    if operation == "list":
        return client.list_configs(authenticated=authenticated)
    if operation == "create":
        return client.create_config({}, authenticated=authenticated)
    return _call_admin_version_route(
        client,
        operation,
        9_223_372_036_854_775_000,
        authenticated=authenticated,
    )


def _call_admin_version_route(
    client: LotteryClient,
    operation: str,
    version: object,
    *,
    authenticated: bool = True,
) -> httpx.Response:
    if operation == "get":
        return client.get_config(version, authenticated=authenticated)
    if operation == "update":
        return client.update_config(version, {}, authenticated=authenticated)
    if operation == "archive":
        return client.archive_config(version, authenticated=authenticated)
    if operation == "clone":
        return client.clone_config(version, authenticated=authenticated)
    if operation == "probabilities":
        return client.get_probabilities(version, authenticated=authenticated)
    if operation == "publish":
        return client.publish_config(version, authenticated=authenticated)
    return client.validate_config(version, authenticated=authenticated)


def _assert_active_season(season: SeasonConfig) -> None:
    assert season.id.strip()
    assert season.name.strip()
    assert season.starts_at <= datetime.now(UTC) < season.ends_at
    assert season.theme.id.strip()
    assert len(season.theme.asset_ids) == len(set(season.theme.asset_ids))
    assert season.chests
    chest_ids = [chest.id for chest in season.chests]
    assert len(chest_ids) == len(set(chest_ids)), "chest IDs must be unique within a season"
    assert any(chest.active for chest in season.chests), "active season must expose an active chest"
    for chest in season.chests:
        _assert_chest(chest)


def _require_active_season(lottery: LotteryResponse) -> SeasonConfig:
    if lottery.season is None:
        pytest.fail(
            "ENVIRONMENT_DEFECT: the active Lottery config has no season for the current time",
            pytrace=False,
        )
    return lottery.season


def _assert_config(config: LotteryConfig) -> None:
    assert config.max_open_quantity >= 0
    season_ids = [season.id for season in config.seasons]
    assert len(season_ids) == len(set(season_ids)), "season IDs must be unique"
    for season in config.seasons:
        assert season.starts_at < season.ends_at
        if season.starts_at <= datetime.now(UTC) < season.ends_at:
            _assert_active_season(season)
        for chest in season.chests:
            _assert_chest(chest)


def _assert_chest(chest: ChestConfig) -> None:
    assert chest.id.strip()
    assert chest.name.strip()
    assert len(chest.asset_ids) == len(set(chest.asset_ids))
    reward_ids = [reward.id for reward in chest.reward_pool]
    assert len(reward_ids) == len(set(reward_ids)), "reward IDs must be unique within a chest"
    if chest.active:
        assert chest.reward_pool, "active chest must have a reward pool"
        assert sum(reward.weight for reward in chest.reward_pool) > 0
    for reward in chest.reward_pool:
        assert reward.id.strip()
        assert reward.type.strip()


def _assert_public_season_matches_config(
    public: SeasonConfig,
    configured: SeasonConfig,
) -> None:
    assert public.id == configured.id
    assert public.name == configured.name
    assert public.starts_at == configured.starts_at
    assert public.ends_at == configured.ends_at
    assert public.theme == configured.theme
    assert len(public.chests) == len(configured.chests)
    configured_chests = {chest.id: chest for chest in configured.chests}
    for public_chest in public.chests:
        configured_chest = configured_chests[public_chest.id]
        assert public_chest.name == configured_chest.name
        assert public_chest.active is configured_chest.active
        assert public_chest.asset_ids == configured_chest.asset_ids
        assert public_chest.cost_keys == configured_chest.cost_keys
        assert public_chest.sort_order == configured_chest.sort_order
        configured_rewards = {reward.id: reward for reward in configured_chest.reward_pool}
        public_reward_ids = {reward.id for reward in public_chest.reward_pool}
        assert public_reward_ids <= configured_rewards.keys(), (
            "public reward pool must contain only rewards from the active admin config"
        )
        total_weight = sum(reward.weight for reward in public_chest.reward_pool)
        assert total_weight > 0, "public active chest must retain at least one eligible reward"
        assert sum(reward.probability for reward in public_chest.reward_pool) == pytest.approx(1.0)
        for public_reward in public_chest.reward_pool:
            configured_reward = configured_rewards[public_reward.id]
            assert public_reward.type == configured_reward.type
            assert public_reward.weight == configured_reward.weight
            assert public_reward.probability == pytest.approx(public_reward.weight / total_weight)
            assert public_reward.display_metadata == configured_reward.display_metadata
            _assert_public_reward_payload(public_reward.payload, configured_reward.payload)


def _assert_public_reward_payload(
    public: dict[str, object] | None,
    configured: dict[str, object] | None,
) -> None:
    if configured is not None and isinstance(configured.get("good_uuid"), str):
        assert public is not None
        item = public.get("item")
        assert isinstance(item, dict)
        assert item.get("uuid") == configured["good_uuid"]
        return
    if configured is not None and isinstance(configured.get("weapon_def_uuid"), str):
        assert public is not None
        item = public.get("item")
        assert isinstance(item, dict)
        assert item.get("uuid") == configured["weapon_def_uuid"]
        assert public.get("quantity") == configured.get("quantity")
        return
    assert public == configured


def _assert_json_error(response: httpx.Response) -> None:
    validate_error_response(response)


def _assert_error(response: httpx.Response, expected_description: str) -> None:
    error = validate_error_response(response)
    assert error.error_description == expected_description, (
        f"expected Lottery error_description={expected_description!r}, "
        f"got {error.error_description!r}"
    )
