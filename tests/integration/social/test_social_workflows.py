from __future__ import annotations

import json
import sys
from collections.abc import Callable
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

import allure
import httpx
import pytest

from qa_automation.clients.base import (
    assert_response_status,
    attach_response_diagnostics,
    validate_response_model,
)
from qa_automation.clients.social import SocialClient
from qa_automation.config import Settings
from qa_automation.models.social import (
    FriendItem,
    FriendRequestCreatedResponse,
    FriendRequestItem,
    PaginatedFriendRequestsResponse,
    PaginatedFriendsResponse,
    StatusResponse,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.regression,
    pytest.mark.serial,
    allure.feature("Social workflows"),
]


@allure.title("User can transition presence from online to offline")
def test_user_can_transition_presence_online_and_offline(
    social_user_client: SocialClient,
    social_mutation_settings: Settings,
) -> None:
    unique_suffix = uuid4().hex
    try:
        heartbeat_response = social_user_client.heartbeat(
            party_id=f"qa-party-{unique_suffix}",
            match_id=f"qa-match-{unique_suffix}",
        )

        assert_response_status(heartbeat_response, 200)
        heartbeat = validate_response_model(heartbeat_response, StatusResponse)
        assert heartbeat.status == "ok"
    finally:
        original_failure = sys.exc_info()[0] is not None
        offline_response = social_user_client.set_offline()
        if offline_response.status_code != 200:
            attach_response_diagnostics(offline_response)
            if not original_failure:
                pytest.fail(
                    "PRODUCT_DEFECT: Social presence cleanup did not return HTTP 200",
                    pytrace=False,
                )

    assert social_mutation_settings.social_mutations_enabled
    offline = validate_response_model(offline_response, StatusResponse)
    assert offline.status == "offline"


@allure.title("Deleting an existing non-friend returns not found")
def test_deleting_existing_non_friend_returns_not_found(
    social_user_client: SocialClient,
    social_peer_client: SocialClient,
    social_user_uuid: UUID,
    social_peer_uuid: UUID,
    social_peer_settings: Settings,
) -> None:
    cleanup_errors = _cleanup_pair(
        primary_client=social_user_client,
        peer_client=social_peer_client,
        primary_uuid=social_user_uuid,
        peer_uuid=social_peer_uuid,
    )
    assert not cleanup_errors, (
        "TEST_DATA_DEFECT: Social test users could not be prepared for the negative check: "
        + "; ".join(cleanup_errors)
    )
    assert social_peer_settings.social_mutations_enabled

    response = social_user_client.delete_friend(str(social_peer_uuid))

    assert_response_status(response, 404)


@allure.title("Friend request, acceptance, presence, and removal form a consistent workflow")
def test_users_can_complete_friendship_and_presence_workflow(
    social_user_client: SocialClient,
    social_peer_client: SocialClient,
    social_user_uuid: UUID,
    social_peer_uuid: UUID,
    social_peer_settings: Settings,
) -> None:
    cleanup_errors = _cleanup_pair(
        primary_client=social_user_client,
        peer_client=social_peer_client,
        primary_uuid=social_user_uuid,
        peer_uuid=social_peer_uuid,
    )
    assert not cleanup_errors, (
        "TEST_DATA_DEFECT: Social test users could not be prepared for the workflow: "
        + "; ".join(cleanup_errors)
    )

    unique_suffix = uuid4().hex
    request_id: UUID | None = None
    try:
        create_response = social_user_client.send_friend_request(str(social_peer_uuid))
        assert_response_status(create_response, 201)
        created = validate_response_model(create_response, FriendRequestCreatedResponse)
        request_id = created.id
        assert created.status == "pending"

        duplicate_response = social_user_client.send_friend_request(str(social_peer_uuid))
        if duplicate_response.status_code != 400:
            attach_response_diagnostics(duplicate_response)

        _wait_for_request(
            client=social_user_client,
            request_id=request_id,
            incoming=False,
            timeout_seconds=social_peer_settings.social_event_timeout.total_seconds(),
        )
        incoming = _wait_for_request(
            client=social_peer_client,
            request_id=request_id,
            incoming=True,
            timeout_seconds=social_peer_settings.social_event_timeout.total_seconds(),
        )
        assert incoming.requester_id == social_user_uuid
        assert incoming.addressee_id == social_peer_uuid

        accept_response = social_peer_client.accept_request(str(request_id))
        assert_response_status(accept_response, 200)
        accepted = validate_response_model(accept_response, StatusResponse)
        assert accepted.status == "accepted"
        if accepted.id is not None:
            assert accepted.id == request_id

        _wait_for_friend(
            client=social_user_client,
            player_id=social_peer_uuid,
            timeout_seconds=social_peer_settings.social_event_timeout.total_seconds(),
        )
        _wait_for_friend(
            client=social_peer_client,
            player_id=social_user_uuid,
            timeout_seconds=social_peer_settings.social_event_timeout.total_seconds(),
        )

        party_id = f"qa-party-{unique_suffix}"
        match_id = f"qa-match-{unique_suffix}"
        heartbeat_response = social_user_client.heartbeat(
            party_id=party_id,
            match_id=match_id,
        )
        assert_response_status(heartbeat_response, 200)
        assert validate_response_model(heartbeat_response, StatusResponse).status == "ok"

        online_friend = _wait_for_friend(
            client=social_peer_client,
            player_id=social_user_uuid,
            timeout_seconds=social_peer_settings.social_event_timeout.total_seconds(),
            condition=lambda friend: (
                friend.online
                and friend.presence is not None
                and friend.presence.party_id == party_id
                and friend.presence.match_id == match_id
            ),
            expected_state="online with the heartbeat party and match",
        )
        assert online_friend.presence is not None

        offline_response = social_user_client.set_offline()
        assert_response_status(offline_response, 200)
        assert validate_response_model(offline_response, StatusResponse).status == "offline"
        _wait_for_friend(
            client=social_peer_client,
            player_id=social_user_uuid,
            timeout_seconds=social_peer_settings.social_event_timeout.total_seconds(),
            condition=lambda friend: not friend.online,
            expected_state="offline",
        )

        delete_response = social_user_client.delete_friend(str(social_peer_uuid))
        assert_response_status(delete_response, 200)
        assert validate_response_model(delete_response, StatusResponse).status == "deleted"
        _wait_for_friend_absence(
            client=social_user_client,
            player_id=social_peer_uuid,
            timeout_seconds=social_peer_settings.social_event_timeout.total_seconds(),
        )
        _wait_for_friend_absence(
            client=social_peer_client,
            player_id=social_user_uuid,
            timeout_seconds=social_peer_settings.social_event_timeout.total_seconds(),
        )
        assert_response_status(duplicate_response, 400)
    finally:
        original_failure = sys.exc_info()[0] is not None
        cleanup_errors = _cleanup_pair(
            primary_client=social_user_client,
            peer_client=social_peer_client,
            primary_uuid=social_user_uuid,
            peer_uuid=social_peer_uuid,
        )
        if cleanup_errors:
            allure.attach(
                json.dumps(cleanup_errors, ensure_ascii=False, indent=2),
                "social-cleanup-errors",
                allure.attachment_type.JSON,
            )
            if not original_failure:
                pytest.fail(
                    "TEST_DATA_DEFECT: Social workflow cleanup failed: "
                    + "; ".join(cleanup_errors),
                    pytrace=False,
                )


def _wait_for_request(
    *,
    client: SocialClient,
    request_id: UUID,
    incoming: bool,
    timeout_seconds: float,
) -> FriendRequestItem:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    while True:
        response = (
            client.get_incoming_requests(limit=100)
            if incoming
            else client.get_outgoing_requests(limit=100)
        )
        assert_response_status(response, 200)
        requests = validate_response_model(response, PaginatedFriendRequestsResponse)
        if match := next((item for item in requests.items if item.id == request_id), None):
            assert match.status == "pending"
            return match
        remaining = deadline - monotonic()
        if remaining <= 0:
            direction = "incoming" if incoming else "outgoing"
            pytest.fail(
                f"PRODUCT_DEFECT: request {request_id} did not appear in {direction} requests "
                f"within {timeout_seconds:g}s",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.25, remaining))


def _wait_for_friend(
    *,
    client: SocialClient,
    player_id: UUID,
    timeout_seconds: float,
    condition: Callable[[FriendItem], bool] | None = None,
    expected_state: str = "present",
) -> FriendItem:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    while True:
        friends = _get_friends(client)
        friend = next((item for item in friends.items if item.player_id == player_id), None)
        if friend is not None and (condition is None or condition(friend)):
            return friend
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: friend {player_id} did not become {expected_state} within "
                f"{timeout_seconds:g}s",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.25, remaining))


def _wait_for_friend_absence(
    *,
    client: SocialClient,
    player_id: UUID,
    timeout_seconds: float,
) -> None:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    while True:
        if all(friend.player_id != player_id for friend in _get_friends(client).items):
            return
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: removed friend {player_id} remained visible for "
                f"{timeout_seconds:g}s",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.25, remaining))


def _get_friends(client: SocialClient) -> PaginatedFriendsResponse:
    response = client.get_friends(limit=100)
    assert_response_status(response, 200)
    return validate_response_model(response, PaginatedFriendsResponse)


def _cleanup_pair(
    *,
    primary_client: SocialClient,
    peer_client: SocialClient,
    primary_uuid: UUID,
    peer_uuid: UUID,
) -> list[str]:
    errors: list[str] = []
    _record_cleanup_response(errors, "set primary offline", primary_client.set_offline(), {200})
    _cancel_outgoing_to(errors, primary_client, peer_uuid, "primary")
    _cancel_outgoing_to(errors, peer_client, primary_uuid, "peer")
    _record_friend_delete_cleanup_response(
        errors,
        "delete peer from primary friends",
        primary_client.delete_friend(str(peer_uuid)),
    )
    _record_friend_delete_cleanup_response(
        errors,
        "delete primary from peer friends",
        peer_client.delete_friend(str(primary_uuid)),
    )
    return errors


def _cancel_outgoing_to(
    errors: list[str],
    client: SocialClient,
    target_uuid: UUID,
    actor_name: str,
) -> None:
    response = client.get_outgoing_requests(limit=100)
    if response.status_code != 200:
        _record_cleanup_response(errors, f"list {actor_name} outgoing requests", response, {200})
        return
    try:
        requests = validate_response_model(response, PaginatedFriendRequestsResponse)
    except AssertionError as error:
        errors.append(f"list {actor_name} outgoing requests returned invalid data: {error}")
        return
    for request in requests.items:
        if request.addressee_id == target_uuid and request.status == "pending":
            _record_cleanup_response(
                errors,
                f"cancel {actor_name} request {request.id}",
                client.cancel_request(str(request.id)),
                {200, 404},
            )


def _record_cleanup_response(
    errors: list[str],
    operation: str,
    response: httpx.Response,
    expected_statuses: set[int],
) -> None:
    if response.status_code not in expected_statuses:
        attach_response_diagnostics(response)
        errors.append(
            f"{operation} returned {response.status_code}; expected {sorted(expected_statuses)}"
        )


def _record_friend_delete_cleanup_response(
    errors: list[str],
    operation: str,
    response: httpx.Response,
) -> None:
    if response.status_code in {200, 404} or _response_means_friendship_absent(response):
        return
    _record_cleanup_response(errors, operation, response, {200, 404})


def _response_means_friendship_absent(response: httpx.Response) -> bool:
    if response.status_code != 400:
        return False
    try:
        payload: object = response.json()
        return payload == {
            "error": {
                "code": "bad_request",
                "message": "invalid state transition",
            }
        }
    except ValueError:
        return False
