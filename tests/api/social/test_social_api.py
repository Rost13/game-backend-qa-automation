from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

import allure
import httpx
import pytest

from qa_automation.clients.base import (
    assert_response_status,
    validate_response_model,
)
from qa_automation.clients.social import SocialClient
from qa_automation.models.social import (
    PaginatedFriendRequestsResponse,
    PaginatedFriendsResponse,
    PublishedPaginatedFriendRequestsResponse,
    PublishedPaginatedFriendsResponse,
    PublishedRecommendationsResponse,
    PublishedSocialErrorResponse,
    RecommendationsResponse,
)

pytestmark = [pytest.mark.api, pytest.mark.live, allure.feature("Social")]

UnauthenticatedCall = Callable[[SocialClient], httpx.Response]


def _get_friends_without_auth(client: SocialClient) -> httpx.Response:
    return client.get_friends(authenticated=False)


def _delete_friend_without_auth(client: SocialClient) -> httpx.Response:
    return client.delete_friend(str(uuid4()), authenticated=False)


def _send_request_without_auth(client: SocialClient) -> httpx.Response:
    return client.send_friend_request(str(uuid4()), authenticated=False)


def _get_incoming_without_auth(client: SocialClient) -> httpx.Response:
    return client.get_incoming_requests(authenticated=False)


def _get_outgoing_without_auth(client: SocialClient) -> httpx.Response:
    return client.get_outgoing_requests(authenticated=False)


def _accept_request_without_auth(client: SocialClient) -> httpx.Response:
    return client.accept_request(str(uuid4()), authenticated=False)


def _decline_request_without_auth(client: SocialClient) -> httpx.Response:
    return client.decline_request(str(uuid4()), authenticated=False)


def _cancel_request_without_auth(client: SocialClient) -> httpx.Response:
    return client.cancel_request(str(uuid4()), authenticated=False)


def _heartbeat_without_auth(client: SocialClient) -> httpx.Response:
    return client.heartbeat(authenticated=False)


def _set_offline_without_auth(client: SocialClient) -> httpx.Response:
    return client.set_offline(authenticated=False)


def _get_recommendations_without_auth(client: SocialClient) -> httpx.Response:
    return client.get_recommendations(authenticated=False)


@allure.title("Social endpoint requires authentication: {operation}")
@pytest.mark.smoke
@pytest.mark.parametrize(
    ("operation", "call"),
    [
        ("get friends", _get_friends_without_auth),
        ("delete friend", _delete_friend_without_auth),
        ("send friend request", _send_request_without_auth),
        ("get incoming requests", _get_incoming_without_auth),
        ("get outgoing requests", _get_outgoing_without_auth),
        ("accept request", _accept_request_without_auth),
        ("decline request", _decline_request_without_auth),
        ("cancel request", _cancel_request_without_auth),
        ("heartbeat", _heartbeat_without_auth),
        ("set offline", _set_offline_without_auth),
        ("get recommendations", _get_recommendations_without_auth),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_social_endpoint_requires_authentication(
    social_user_client: SocialClient,
    operation: str,
    call: UnauthenticatedCall,
) -> None:
    response = call(social_user_client)

    assert_response_status(response, 401)


@allure.title("User can get friends sorted online first and then by nickname")
@pytest.mark.smoke
def test_user_can_get_sorted_friends(
    social_user_client: SocialClient,
    social_user_uuid: UUID,
) -> None:
    response = social_user_client.get_friends()

    assert_response_status(response, 200)
    friends = validate_response_model(response, PaginatedFriendsResponse)
    player_ids = [friend.player_id for friend in friends.items]
    assert len(player_ids) == len(set(player_ids)), "friend player_id values must be unique"
    assert social_user_uuid not in player_ids, "current user must not appear in their friend list"
    assert [friend.online for friend in friends.items] == sorted(
        (friend.online for friend in friends.items), reverse=True
    ), "online friends must precede offline friends"
    for online in (True, False):
        nicknames = [friend.nickname for friend in friends.items if friend.online is online]
        assert all(nickname.strip() for nickname in nicknames)
        assert nicknames == sorted(nicknames, key=str.casefold), (
            f"friends with online={online} must be sorted by nickname"
        )


@allure.title("Friends endpoint accepts the documented maximum page size")
@pytest.mark.regression
def test_friends_accept_documented_maximum_limit(
    social_user_client: SocialClient,
) -> None:
    response = social_user_client.get_friends(limit=100)

    assert_response_status(response, 200)
    friends = validate_response_model(response, PaginatedFriendsResponse)
    assert len(friends.items) <= 100


@allure.title("Incoming friend requests belong to the current user")
@pytest.mark.regression
def test_user_can_get_incoming_friend_requests(
    social_user_client: SocialClient,
    social_user_uuid: UUID,
) -> None:
    response = social_user_client.get_incoming_requests(limit=100)

    assert_response_status(response, 200)
    requests = validate_response_model(response, PaginatedFriendRequestsResponse)
    request_ids = [request.id for request in requests.items]
    assert len(request_ids) == len(set(request_ids)), "incoming request IDs must be unique"
    assert all(request.addressee_id == social_user_uuid for request in requests.items)
    assert all(request.status == "pending" for request in requests.items)


@allure.title("Outgoing friend requests belong to the current user")
@pytest.mark.regression
def test_user_can_get_outgoing_friend_requests(
    social_user_client: SocialClient,
    social_user_uuid: UUID,
) -> None:
    response = social_user_client.get_outgoing_requests(limit=100)

    assert_response_status(response, 200)
    requests = validate_response_model(response, PaginatedFriendRequestsResponse)
    request_ids = [request.id for request in requests.items]
    assert len(request_ids) == len(set(request_ids)), "outgoing request IDs must be unique"
    assert all(request.requester_id == social_user_uuid for request in requests.items)
    assert all(request.status == "pending" for request in requests.items)


@allure.title("Friend recommendations exclude the current user and duplicates")
@pytest.mark.smoke
def test_user_can_get_friend_recommendations(
    social_user_client: SocialClient,
    social_user_uuid: UUID,
) -> None:
    response = social_user_client.get_recommendations()

    assert_response_status(response, 200)
    recommendations = validate_response_model(response, RecommendationsResponse)
    player_ids = [recommendation.player_id for recommendation in recommendations.items]
    assert len(player_ids) == len(set(player_ids)), "recommendation player IDs must be unique"
    assert social_user_uuid not in player_ids, "current user must not be recommended"
    assert all(item.nickname.strip() for item in recommendations.items)
    assert all(item.reason.strip() for item in recommendations.items)


@allure.title("User cannot send a friend request to themselves")
@pytest.mark.regression
def test_user_cannot_send_friend_request_to_self(
    social_user_client: SocialClient,
    social_user_uuid: UUID,
) -> None:
    response = social_user_client.send_friend_request(str(social_user_uuid))

    assert_response_status(response, 400)


@allure.title("Friend request rejects a missing target_player_id")
@pytest.mark.regression
def test_friend_request_rejects_missing_target_player_id(
    social_user_client: SocialClient,
) -> None:
    response = social_user_client.send_friend_request(None)

    assert_response_status(response, 400)


@allure.title("Friend request rejects a malformed target_player_id")
@pytest.mark.regression
def test_friend_request_rejects_malformed_target_player_id(
    social_user_client: SocialClient,
) -> None:
    response = social_user_client.send_friend_request("not-a-uuid")

    assert_response_status(response, 400)


@allure.title("Deleting an unknown friend returns not found")
@pytest.mark.regression
def test_deleting_unknown_friend_returns_not_found(
    social_user_client: SocialClient,
) -> None:
    response = social_user_client.delete_friend(str(uuid4()))

    assert_response_status(response, 404)


@allure.title("Friends response follows the published OpenAPI schema")
@pytest.mark.contract
def test_friends_response_matches_openapi_contract(
    social_user_client: SocialClient,
) -> None:
    response = social_user_client.get_friends()

    assert_response_status(response, 200)
    validate_response_model(response, PublishedPaginatedFriendsResponse)


@allure.title("Incoming requests response follows the published OpenAPI schema")
@pytest.mark.contract
def test_incoming_requests_response_matches_openapi_contract(
    social_user_client: SocialClient,
) -> None:
    response = social_user_client.get_incoming_requests()

    assert_response_status(response, 200)
    validate_response_model(response, PublishedPaginatedFriendRequestsResponse)


@allure.title("Recommendations response follows the published OpenAPI schema")
@pytest.mark.contract
def test_recommendations_response_matches_openapi_contract(
    social_user_client: SocialClient,
) -> None:
    response = social_user_client.get_recommendations()

    assert_response_status(response, 200)
    validate_response_model(response, PublishedRecommendationsResponse)


@allure.title("Unauthorized Social error follows the published OpenAPI schema")
@pytest.mark.contract
def test_unauthorized_social_error_matches_openapi_contract(
    social_user_client: SocialClient,
) -> None:
    response = social_user_client.get_friends(authenticated=False)

    assert_response_status(response, 401)
    validate_response_model(response, PublishedSocialErrorResponse)
