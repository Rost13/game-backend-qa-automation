from __future__ import annotations

from uuid import UUID

import allure
import pytest

from qa_automation.clients.base import (
    assert_response_status,
    validate_error_response,
    validate_success_data,
)
from qa_automation.clients.stat_api import StatApiClient
from qa_automation.models.stat_api import (
    ClanWarsMapsResponse,
    MatchesPlayed,
    PlayerLeaderboardResponse,
    SquadLeaderboardResponse,
    StatHistory,
    StatSummary,
    TeamLeaderboardResponse,
)

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Stat API")]


@allure.title("Documented Stat API endpoints require authentication: {operation}")
@pytest.mark.regression
@pytest.mark.parametrize(
    "operation",
    ["summary", "matches", "history", "players", "clan-maps", "webhook"],
)
def test_stat_endpoints_require_authentication(
    stat_user_client: StatApiClient,
    operation: str,
) -> None:
    if operation == "summary":
        response = stat_user_client.get_summary(authenticated=False)
    elif operation == "matches":
        response = stat_user_client.get_matches_played(authenticated=False)
    elif operation == "history":
        response = stat_user_client.get_history(authenticated=False)
    elif operation == "players":
        response = stat_user_client.get_players_leaderboard(authenticated=False)
    elif operation == "clan-maps":
        response = stat_user_client.get_clan_wars_maps(authenticated=False)
    else:
        response = stat_user_client.send_client_event({}, authenticated=False)

    assert_response_status(response, 401)
    validate_error_response(response)


@allure.title("Stat summary is internally consistent")
@pytest.mark.smoke
@pytest.mark.contract
def test_stat_summary_is_consistent(stat_user_client: StatApiClient) -> None:
    response = stat_user_client.get_summary()

    assert_response_status(response, 200)
    summary = validate_success_data(response, StatSummary)
    assert summary.matches == summary.wins + summary.defeats + summary.draws
    assert 0 <= summary.winrate <= 100
    assert 0 <= summary.accuracy <= 100
    assert summary.headshots >= 0
    assert summary.killrate >= 0
    assert summary.period_start <= summary.period_end


@allure.title("Matches played agrees with the all-time Stat summary")
@pytest.mark.smoke
@pytest.mark.contract
def test_matches_played_agrees_with_summary(stat_user_client: StatApiClient) -> None:
    matches_response = stat_user_client.get_matches_played()
    summary_response = stat_user_client.get_summary()

    assert_response_status(matches_response, 200)
    assert_response_status(summary_response, 200)
    matches = validate_success_data(matches_response, MatchesPlayed)
    summary = validate_success_data(summary_response, StatSummary)
    assert matches.matches_played == summary.matches


@allure.title("Stat history respects pagination and match invariants")
@pytest.mark.contract
def test_stat_history_respects_contract(stat_user_client: StatApiClient) -> None:
    response = stat_user_client.get_history(limit=10, offset=0)

    assert_response_status(response, 200)
    history = validate_success_data(response, StatHistory)
    assert len(history.matches) <= 10
    assert history.total >= len(history.matches)
    for match in history.matches:
        assert match.map_id.strip()
        assert match.mode.strip()
        assert match.result.strip()
        assert match.started_at <= match.finished_at


@allure.title("Stat history accepts every documented period: {period}")
@pytest.mark.regression
@pytest.mark.parametrize("period", ["day", "week", "month"])
def test_stat_history_accepts_documented_periods(
    stat_user_client: StatApiClient,
    period: str,
) -> None:
    response = stat_user_client.get_history(period=period, limit=1, offset=0)

    assert_response_status(response, 200)
    history = validate_success_data(response, StatHistory)
    assert len(history.matches) <= 1


@allure.title("Stat history rejects invalid query input: {case}")
@pytest.mark.regression
@pytest.mark.parametrize(
    ("case", "period", "limit", "offset"),
    [
        ("unknown period", "year", None, None),
        ("non-integer limit", None, "ten", None),
        ("non-integer offset", None, None, "zero"),
        ("negative limit", None, -1, None),
        ("negative offset", None, None, -1),
    ],
)
def test_stat_history_rejects_invalid_query_input(
    stat_user_client: StatApiClient,
    case: str,
    period: str | None,
    limit: object | None,
    offset: object | None,
) -> None:
    response = stat_user_client.get_history(period=period, limit=limit, offset=offset)

    assert_response_status(response, 400)
    validate_error_response(response)


@allure.title("Stat player leaderboard follows the published contract")
@pytest.mark.smoke
@pytest.mark.contract
def test_player_leaderboard_follows_contract(stat_user_client: StatApiClient) -> None:
    response = stat_user_client.get_players_leaderboard(range_="day", page=1, limit=10)

    assert_response_status(response, 200)
    result = validate_success_data(response, PlayerLeaderboardResponse).leaderboard
    assert result.range == "day"
    assert result.list.page == 1
    assert len(result.list.players) <= 10
    assert result.list.total >= len(result.list.players)
    _assert_unique([entry.uuid for entry in result.list.players])


@allure.title("Stat squad and team leaderboards follow the published contracts")
@pytest.mark.contract
def test_group_leaderboards_follow_contract(stat_user_client: StatApiClient) -> None:
    squads_response = stat_user_client.get_squads_leaderboard(range_="week", page=1, limit=10)
    teams_response = stat_user_client.get_teams_leaderboard(range_="week", page=1, limit=10)

    assert_response_status(squads_response, 200)
    assert_response_status(teams_response, 200)
    squads = validate_success_data(squads_response, SquadLeaderboardResponse).leaderboard
    teams = validate_success_data(teams_response, TeamLeaderboardResponse).leaderboard
    assert squads.range == teams.range == "week"
    assert squads.list.total >= len(squads.list.squads)
    assert teams.list.total >= len(teams.list.teams)
    _assert_unique([entry.squad_id for entry in squads.list.squads])
    _assert_unique([entry.team_id for entry in teams.list.teams])


@allure.title("Stat leaderboards reject an unsupported range")
@pytest.mark.regression
def test_stat_leaderboards_reject_invalid_range(stat_user_client: StatApiClient) -> None:
    responses = [
        stat_user_client.get_players_leaderboard(range_="year"),
        stat_user_client.get_squads_leaderboard(range_="year"),
        stat_user_client.get_teams_leaderboard(range_="year"),
    ]

    for response in responses:
        assert_response_status(response, 400)
        validate_error_response(response)


@allure.title("Clan Wars map list follows the published contract")
@pytest.mark.contract
def test_clan_wars_maps_follow_contract(stat_user_client: StatApiClient) -> None:
    response = stat_user_client.get_clan_wars_maps()

    assert_response_status(response, 200)
    maps = validate_success_data(response, ClanWarsMapsResponse).maps
    _assert_unique([map_.map_id for map_ in maps])
    for map_ in maps:
        assert map_.map_id.strip()
        assert map_.segment_started_at <= map_.segment_ends_at


@allure.title("Ordinary user cannot read another account through Stat admin history")
@pytest.mark.regression
def test_stat_admin_history_rejects_ordinary_user(
    stat_user_client: StatApiClient,
    api_test_user_uuid: UUID,
) -> None:
    response = stat_user_client.get_admin_history(api_test_user_uuid)

    assert_response_status(response, 403)
    validate_error_response(response)


@allure.title("Stat admin history matches the authenticated user's history")
@pytest.mark.regression
def test_stat_admin_history_matches_user_history(
    stat_user_client: StatApiClient,
    stat_admin_client: StatApiClient,
    api_test_user_uuid: UUID,
) -> None:
    user_response = stat_user_client.get_history(limit=10, offset=0)
    admin_response = stat_admin_client.get_admin_history(api_test_user_uuid, limit=10, offset=0)

    assert_response_status(user_response, 200)
    assert_response_status(admin_response, 200)
    assert validate_success_data(admin_response, StatHistory) == validate_success_data(
        user_response, StatHistory
    )


@allure.title("Stat client webhook validates its request body")
@pytest.mark.regression
def test_stat_client_webhook_rejects_invalid_payload(stat_user_client: StatApiClient) -> None:
    response = stat_user_client.send_client_event(
        {"request_id": "qa-invalid", "name": "receive", "data": {}}
    )

    assert_response_status(response, 400)
    validate_error_response(response)


def _assert_unique(values: list[object]) -> None:
    assert len(values) == len(set(values))
