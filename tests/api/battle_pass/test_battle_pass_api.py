from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

import allure
import httpx
import pytest

from qa_automation.clients.base import assert_response_status, validate_response_model
from qa_automation.clients.battle_pass import BattlePassClient
from qa_automation.models.battle_pass import (
    ArchiveRewardsResponse,
    BannerView,
    BattlePassError,
    LevelWithReward,
    PublicConfigResponse,
    Season,
    SeasonLevel,
    SeasonView,
)

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Battle Pass")]

UnauthenticatedCall = Callable[[BattlePassClient], httpx.Response]


def _get_active_without_auth(client: BattlePassClient) -> httpx.Response:
    return client.get_active(authenticated=False)


def _get_banner_without_auth(client: BattlePassClient) -> httpx.Response:
    return client.get_banner(authenticated=False)


def _get_archive_without_auth(client: BattlePassClient) -> httpx.Response:
    return client.get_archive_rewards(authenticated=False)


def _claim_reward_without_auth(client: BattlePassClient) -> httpx.Response:
    return client.claim_reward(uuid4(), "default", 1, authenticated=False)


def _claim_all_without_auth(client: BattlePassClient) -> httpx.Response:
    return client.claim_all_rewards(uuid4(), authenticated=False)


def _claim_archive_without_auth(client: BattlePassClient) -> httpx.Response:
    return client.claim_all_archive_rewards(authenticated=False)


def _add_test_xp_without_auth(client: BattlePassClient) -> httpx.Response:
    return client.add_test_xp(1, f"qa-unauth-{uuid4()}", authenticated=False)


def _reset_without_auth(client: BattlePassClient) -> httpx.Response:
    return client.reset_test_user(authenticated=False)


@allure.title("Battle Pass endpoint requires authentication: {operation}")
@pytest.mark.smoke
@pytest.mark.parametrize(
    ("operation", "call"),
    [
        ("active season", _get_active_without_auth),
        ("banner", _get_banner_without_auth),
        ("archive", _get_archive_without_auth),
        ("claim reward", _claim_reward_without_auth),
        ("claim all", _claim_all_without_auth),
        ("claim archive", _claim_archive_without_auth),
        ("add test XP", _add_test_xp_without_auth),
        ("reset test user", _reset_without_auth),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_battle_pass_endpoint_requires_authentication(
    battle_pass_user_client: BattlePassClient,
    operation: str,
    call: UnauthenticatedCall,
) -> None:
    response = call(battle_pass_user_client)

    assert_response_status(response, 401)


@allure.title("Public Battle Pass config is internally consistent")
@pytest.mark.smoke
@pytest.mark.contract
def test_public_battle_pass_config_is_consistent(
    battle_pass_user_client: BattlePassClient,
) -> None:
    response = battle_pass_user_client.get_config(authenticated=False)

    assert_response_status(response, 200)
    config = validate_response_model(response, PublicConfigResponse)
    assert config.enabled is True, "ENVIRONMENT_DEFECT: Battle Pass is disabled in dev"
    assert config.battle_pass is not None
    assert config.rewards is not None
    assert config.battle_pass.seasons
    assert config.rewards.items
    reward_ids = [reward.id for reward in config.rewards.items]
    assert len(reward_ids) == len(set(reward_ids)), "reward IDs must be unique"
    known_reward_ids = set(reward_ids)
    active_seasons = [season for season in config.battle_pass.seasons if season.status == "active"]
    assert len(active_seasons) == 1, "config must contain exactly one active season"
    now = datetime.now(UTC)
    assert active_seasons[0].starts_at <= now < active_seasons[0].ends_at
    for season in config.battle_pass.seasons:
        _assert_config_season(
            season,
            levels_count=config.battle_pass.levels_count,
            known_reward_ids=known_reward_ids,
        )


@allure.title("User receives a consistent active Battle Pass state")
@pytest.mark.smoke
@pytest.mark.contract
def test_user_receives_consistent_active_battle_pass(
    battle_pass_user_client: BattlePassClient,
) -> None:
    response = battle_pass_user_client.get_active()

    assert_response_status(response, 200)
    active = validate_response_model(response, SeasonView)
    assert active.status == "active"
    assert active.starts_at <= datetime.now(UTC) < active.ends_at
    _assert_view_levels(active.default_levels, active.progress.total_xp, premium_locked=False)
    _assert_view_levels(
        active.premium_levels,
        active.progress.total_xp,
        premium_locked=not active.progress.has_premium,
    )
    ready_count = sum(
        level.available and not level.claimed
        for level in [*active.default_levels, *active.premium_levels]
    )
    assert active.progress.ready_to_claim_count == ready_count


@allure.title("Battle Pass banner agrees with active player state")
@pytest.mark.regression
def test_battle_pass_banner_agrees_with_active_state(
    battle_pass_user_client: BattlePassClient,
) -> None:
    active_response = battle_pass_user_client.get_active()
    banner_response = battle_pass_user_client.get_banner()

    assert_response_status(active_response, 200)
    assert_response_status(banner_response, 200)
    active = validate_response_model(active_response, SeasonView)
    banner = validate_response_model(banner_response, BannerView)
    assert banner.season.uuid == active.uuid
    assert banner.season.status == active.status
    assert banner.player.level == active.progress.level
    assert banner.player.has_premium is active.progress.has_premium
    assert banner.player.ready_to_claim_count == active.progress.ready_to_claim_count


@allure.title("User can inspect unclaimed archive rewards")
@pytest.mark.regression
@pytest.mark.contract
def test_user_can_inspect_battle_pass_archive(
    battle_pass_user_client: BattlePassClient,
) -> None:
    response = battle_pass_user_client.get_archive_rewards()

    assert_response_status(response, 200)
    archive = validate_response_model(response, ArchiveRewardsResponse)
    positions = [(item.season_uuid, item.track, item.level) for item in archive.items]
    assert len(positions) == len(set(positions)), "archive reward positions must be unique"
    assert all(item.available for item in archive.items)


@allure.title("Battle Pass rejects unavailable reward coordinates: {case}")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("case", "track", "level"),
    [
        ("unsupported track", "vip", 1),
        ("zero level", "default", 0),
        ("malformed level", "default", "one"),
    ],
)
def test_battle_pass_rejects_invalid_reward_coordinates(
    battle_pass_user_client: BattlePassClient,
    case: str,
    track: str,
    level: object,
) -> None:
    response = battle_pass_user_client.claim_reward(uuid4(), track, level)

    expected_status = 400 if case == "malformed level" else 404
    assert_response_status(response, expected_status)
    validate_response_model(response, BattlePassError)


@allure.title("Battle Pass test XP endpoint rejects non-positive XP")
@pytest.mark.regression
@pytest.mark.parametrize("xp", [0, -1])
def test_battle_pass_test_xp_rejects_non_positive_amount(
    battle_pass_user_client: BattlePassClient,
    xp: int,
) -> None:
    response = battle_pass_user_client.add_test_xp(xp, f"qa-invalid-{uuid4()}")

    assert_response_status(response, 400)
    error = validate_response_model(response, BattlePassError)
    assert error.error == "xp must be positive"


def _assert_config_season(
    season: Season,
    *,
    levels_count: int,
    known_reward_ids: set[int],
) -> None:
    assert season.starts_at < season.ends_at
    assert len(season.default_levels) == levels_count
    assert len(season.premium_levels) == levels_count
    if season.premium_levels:
        assert season.premium_goods_uuid.strip()
    _assert_config_levels(season.default_levels, known_reward_ids)
    _assert_config_levels(season.premium_levels, known_reward_ids)


def _assert_config_levels(levels: list[SeasonLevel], known_reward_ids: set[int]) -> None:
    assert [level.level for level in levels] == list(range(1, len(levels) + 1))
    previous_total = 0
    for level in levels:
        assert level.id in known_reward_ids
        assert level.total_xp_required >= previous_total
        assert level.xp_from_previous == level.total_xp_required - previous_total
        previous_total = level.total_xp_required


def _assert_view_levels(
    levels: list[LevelWithReward],
    total_xp: int,
    *,
    premium_locked: bool,
) -> None:
    for level in levels:
        expected_available = total_xp >= level.total_xp_required and not premium_locked
        assert level.available is expected_available
