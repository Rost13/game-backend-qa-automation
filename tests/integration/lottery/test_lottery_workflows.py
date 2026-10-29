from __future__ import annotations

import sys
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

import allure
import pytest

from qa_automation.clients.balance import BalanceClient
from qa_automation.clients.base import (
    assert_response_status,
    attach_response_diagnostics,
    validate_error_response,
    validate_success_data,
)
from qa_automation.clients.lottery import LotteryClient
from qa_automation.config import Settings
from qa_automation.models.balance import (
    PXG_MINOR_UNITS,
    BalanceResponse,
    HistoryResponse,
    ReplenishResponse,
)
from qa_automation.models.lottery import (
    ChestConfig,
    ConfigVersion,
    ListOpeningsResponse,
    LotteryResponse,
    OpenChestResponse,
    Opening,
    OpeningResult,
    ProbabilitiesResponse,
    SeasonConfig,
)
from qa_automation.oracles import assert_only_expected_ids_added

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.regression,
    pytest.mark.serial,
    allure.feature("Lottery"),
]


@allure.title("Lottery rejects a chest opening when the account has insufficient keys")
def test_lottery_rejects_chest_opening_without_enough_keys(
    lottery_user_client: LotteryClient,
    lottery_opening_settings: Settings,
    balance_admin_client: BalanceClient,
    balance_test_user_uuid: UUID,
) -> None:
    lottery_before = _get_lottery(lottery_user_client)
    balance_state_before = _get_balance(balance_admin_client, balance_test_user_uuid)
    balance_before = balance_state_before.keys or 0
    assert lottery_before.keys_balance == balance_before, (
        "PRODUCT_DEFECT: Lottery keys_balance disagrees with Balance before opening"
    )
    active_season = _require_active_season(lottery_before)
    unaffordable = [
        chest
        for chest in active_season.chests
        if chest.active and chest.cost_keys > lottery_before.keys_balance
    ]
    if not unaffordable:
        pytest.fail(
            "TEST_DATA_DEFECT: no active chest costs more than the test user's keys balance",
            pytrace=False,
        )
    chest = min(unaffordable, key=lambda item: (item.cost_keys, item.sort_order, item.id))
    history_before = _get_history(lottery_user_client)
    history_ids_before = {opening.opening_id for opening in history_before.items}

    response = lottery_user_client.open_chest(
        chest.id,
        1,
        f"qa-lottery-insufficient-keys-{uuid4()}",
    )

    accepted: OpenChestResponse | None = None
    if response.status_code == 200:
        accepted = validate_success_data(response, OpenChestResponse)
        _wait_for_openings(
            lottery_user_client,
            {opening.opening_id for opening in accepted.openings},
            lottery_opening_settings.lottery_event_timeout.total_seconds(),
        )
    lottery_after = _get_lottery(lottery_user_client)
    balance_after = _get_balance_keys(balance_admin_client, balance_test_user_uuid)
    history_after = _get_history(lottery_user_client)
    history_ids_after = {opening.opening_id for opening in history_after.items}
    violations: list[str] = []
    error_description: str | None = None
    if 400 <= response.status_code < 500:
        error_description = validate_error_response(response).error_description
    if response.status_code != 409:
        violations.append(f"request returned {response.status_code} instead of 409")
    if error_description != "insufficient_keys":
        violations.append(
            f"error_description was {error_description!r} instead of 'insufficient_keys'"
        )
    if lottery_after.keys_balance != lottery_before.keys_balance:
        violations.append(
            f"Lottery keys changed from {lottery_before.keys_balance} "
            f"to {lottery_after.keys_balance}"
        )
    if balance_after != balance_before:
        violations.append(f"Balance keys changed from {balance_before} to {balance_after}")
    new_opening_ids = history_ids_after - history_ids_before
    if new_opening_ids:
        violations.append(f"opening history gained {len(new_opening_ids)} record(s)")
    if accepted is not None:
        violations.append(
            f"service returned open batch {accepted.open_batch_id} with "
            f"{len(accepted.openings)} reward(s)"
        )
    if violations:
        attach_response_diagnostics(response)
    assert not violations, (
        "PRODUCT_DEFECT: insufficient keys did not atomically block chest opening: "
        + "; ".join(violations)
    )


@allure.title("Opening a Lottery chest spends keys once and persists one history entry")
def test_lottery_chest_opening_is_idempotent_across_balance_and_history(
    lottery_user_client: LotteryClient,
    lottery_opening_settings: Settings,
    balance_admin_client: BalanceClient,
    balance_test_user_uuid: UUID,
) -> None:
    lottery_before = _get_lottery(lottery_user_client)
    balance_state_before = _get_balance(balance_admin_client, balance_test_user_uuid)
    balance_before = balance_state_before.keys or 0
    assert lottery_before.keys_balance == balance_before, (
        "PRODUCT_DEFECT: Lottery keys_balance disagrees with Balance before opening"
    )
    chest = _select_openable_chest(lottery_before)
    required_keys = chest.cost_keys

    if lottery_before.keys_balance < required_keys:
        if not lottery_opening_settings.lottery_keys_topup_enabled:
            pytest.fail(
                "TEST_DATA_DEFECT: Lottery test user does not have enough keys; enable "
                "LOTTERY_KEYS_TOPUP_ENABLED to add only the missing amount in dev",
                pytrace=False,
            )
        topup = required_keys - lottery_before.keys_balance
        replenish_response = balance_admin_client.replenish(
            {"uuid": str(balance_test_user_uuid), "keys": topup}
        )
        assert_response_status(replenish_response, 200)
        validate_success_data(replenish_response, ReplenishResponse)
        lottery_before = _wait_for_key_balances(
            lottery_user_client,
            balance_admin_client,
            balance_test_user_uuid,
            expected_keys=required_keys,
            timeout_seconds=lottery_opening_settings.lottery_event_timeout.total_seconds(),
        )

    history_before = _get_history(lottery_user_client)
    history_ids_before = {opening.opening_id for opening in history_before.items}
    idempotency_key = f"qa-lottery-open-{uuid4()}"

    open_response = lottery_user_client.open_chest(chest.id, 1, idempotency_key)

    assert_response_status(open_response, 200)
    opened = validate_success_data(open_response, OpenChestResponse)
    assert opened.chest_id == chest.id
    assert opened.season_id == _require_active_season(lottery_before).id
    assert opened.config_version == lottery_before.config_version
    assert opened.quantity == 1
    assert len(opened.openings) == 1
    assert opened.total_cost_keys == required_keys
    assert opened.openings[0].opening_id not in history_ids_before
    expected_keys = lottery_before.keys_balance - required_keys
    _wait_for_key_balances(
        lottery_user_client,
        balance_admin_client,
        balance_test_user_uuid,
        expected_keys=expected_keys,
        timeout_seconds=lottery_opening_settings.lottery_event_timeout.total_seconds(),
    )
    persisted = _wait_for_openings(
        lottery_user_client,
        {result.opening_id for result in opened.openings},
        lottery_opening_settings.lottery_event_timeout.total_seconds(),
    )
    _assert_opening_persistence(opened, persisted, chest)
    returned_ids = {result.opening_id for result in opened.openings}
    history_after_open = _get_history(lottery_user_client)
    history_ids_after_open = {opening.opening_id for opening in history_after_open.items}
    assert_only_expected_ids_added(history_ids_before, history_ids_after_open, returned_ids)
    balance_after_reward = _wait_for_currency_reward_balance(
        balance_admin_client,
        balance_test_user_uuid,
        before=balance_state_before,
        opening=opened.openings[0],
        timeout_seconds=lottery_opening_settings.lottery_event_timeout.total_seconds(),
    )

    duplicate_response = lottery_user_client.open_chest(chest.id, 1, idempotency_key)

    assert duplicate_response.status_code in {200, 409}, (
        "duplicate idempotency key must replay the result or report a conflict; "
        f"got {duplicate_response.status_code}"
    )
    if duplicate_response.status_code == 200:
        assert validate_success_data(duplicate_response, OpenChestResponse) == opened
    else:
        assert isinstance(duplicate_response.json(), dict)
    _wait_for_key_balances(
        lottery_user_client,
        balance_admin_client,
        balance_test_user_uuid,
        expected_keys=expected_keys,
        timeout_seconds=lottery_opening_settings.lottery_event_timeout.total_seconds(),
    )
    history_after_duplicate = _get_history(lottery_user_client)
    history_ids_after_duplicate = {opening.opening_id for opening in history_after_duplicate.items}
    assert_only_expected_ids_added(
        history_ids_after_open,
        history_ids_after_duplicate,
        set(),
    )

    conflict_response = lottery_user_client.open_chest(chest.id, 2, idempotency_key)

    assert_response_status(conflict_response, 409)
    conflict = validate_error_response(conflict_response)
    assert conflict.error_description == "idempotency_conflict"
    _wait_for_key_balances(
        lottery_user_client,
        balance_admin_client,
        balance_test_user_uuid,
        expected_keys=expected_keys,
        timeout_seconds=lottery_opening_settings.lottery_event_timeout.total_seconds(),
    )
    history_after_conflict = _get_history(lottery_user_client)
    history_ids_after_conflict = {opening.opening_id for opening in history_after_conflict.items}
    assert_only_expected_ids_added(
        history_ids_after_duplicate,
        history_ids_after_conflict,
        set(),
    )
    balance_after_conflict = _get_balance(balance_admin_client, balance_test_user_uuid)
    assert balance_after_conflict.soft == balance_after_reward.soft
    assert balance_after_conflict.hard == balance_after_reward.hard
    _assert_single_currency_credit(balance_admin_client, opened.openings[0])


@allure.title("A cloned Lottery draft can be updated, validated, inspected, and archived")
def test_lottery_admin_clone_lifecycle_preserves_active_config(
    lottery_user_client: LotteryClient,
    lottery_admin_client: LotteryClient,
    lottery_config_mutation_settings: Settings,
) -> None:
    del lottery_config_mutation_settings
    active = _get_lottery(lottery_user_client)
    source_response = lottery_admin_client.get_config(active.config_version)
    assert_response_status(source_response, 200)
    source = validate_success_data(source_response, ConfigVersion)
    cloned: ConfigVersion | None = None

    clone_response = lottery_admin_client.clone_config(source.version)
    try:
        assert_response_status(clone_response, 200)
        cloned = validate_success_data(clone_response, ConfigVersion)
        assert cloned.version != source.version
        assert cloned.status.casefold() == "draft"
        assert cloned.config == source.config

        get_response = lottery_admin_client.get_config(cloned.version)
        assert_response_status(get_response, 200)
        assert validate_success_data(get_response, ConfigVersion) == cloned

        invalid_update_response = lottery_admin_client.update_config(cloned.version, {})
        assert_response_status(invalid_update_response, 400)

        update_response = lottery_admin_client.update_config(
            cloned.version,
            {"config": cloned.config.model_dump(mode="json")},
        )
        assert_response_status(update_response, 200)
        updated = validate_success_data(update_response, ConfigVersion)
        assert updated.version == cloned.version
        assert updated.config == source.config

        validate_response = lottery_admin_client.validate_config(cloned.version)
        assert_response_status(validate_response, 200)
        validated = validate_success_data(validate_response, ConfigVersion)
        assert validated.version == cloned.version
        assert not validated.validation_errors

        probabilities_response = lottery_admin_client.get_probabilities(cloned.version)
        assert_response_status(probabilities_response, 200)
        probabilities = validate_success_data(probabilities_response, ProbabilitiesResponse)
        assert probabilities.version == cloned.version
        assert probabilities.config == source.config

        still_active = _get_lottery(lottery_user_client)
        assert still_active.config_version == active.config_version
        assert still_active.season == active.season
    finally:
        active_error = sys.exc_info()[0]
        if cloned is not None:
            archive_response = lottery_admin_client.archive_config(cloned.version)
            if archive_response.status_code != 200:
                attach_response_diagnostics(archive_response)
            if active_error is None:
                assert_response_status(archive_response, 200)
                archived = validate_success_data(archive_response, ConfigVersion)
                assert archived.version == cloned.version
                assert archived.status.casefold() == "archived"


def _get_lottery(client: LotteryClient) -> LotteryResponse:
    response = client.get_lottery()
    assert_response_status(response, 200)
    return validate_success_data(response, LotteryResponse)


def _get_history(client: LotteryClient) -> ListOpeningsResponse:
    response = client.list_openings(limit=50)
    assert_response_status(response, 200)
    return validate_success_data(response, ListOpeningsResponse)


def _get_balance_keys(client: BalanceClient, account_uuid: UUID) -> int:
    return _get_balance(client, account_uuid).keys or 0


def _get_balance(client: BalanceClient, account_uuid: UUID) -> BalanceResponse:
    response = client.get_balance_by_uuid(account_uuid)
    assert_response_status(response, 200)
    return validate_success_data(response, BalanceResponse)


def _select_openable_chest(lottery: LotteryResponse) -> ChestConfig:
    season = _require_active_season(lottery)
    candidates = [chest for chest in season.chests if chest.active and chest.cost_keys > 0]
    if not candidates:
        pytest.fail(
            "TEST_DATA_DEFECT: active Lottery season has no active positive-cost chest",
            pytrace=False,
        )
    return min(candidates, key=lambda chest: (chest.cost_keys, chest.sort_order, chest.id))


def _require_active_season(lottery: LotteryResponse) -> SeasonConfig:
    if lottery.season is None:
        pytest.fail(
            "ENVIRONMENT_DEFECT: the active Lottery config has no season for the current time",
            pytrace=False,
        )
    return lottery.season


def _wait_for_key_balances(
    lottery_client: LotteryClient,
    balance_client: BalanceClient,
    account_uuid: UUID,
    *,
    expected_keys: int,
    timeout_seconds: float,
) -> LotteryResponse:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    last_lottery: LotteryResponse | None = None
    last_balance: int | None = None
    while True:
        last_lottery = _get_lottery(lottery_client)
        last_balance = _get_balance_keys(balance_client, account_uuid)
        if last_lottery.keys_balance == expected_keys and last_balance == expected_keys:
            return last_lottery
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                "PRODUCT_DEFECT: Lottery and Balance keys did not settle to "
                f"{expected_keys} within {timeout_seconds:g}s; "
                f"Lottery={last_lottery.keys_balance}, Balance={last_balance}",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.25, remaining))


def _wait_for_openings(
    client: LotteryClient,
    expected_ids: set[UUID],
    timeout_seconds: float,
) -> list[Opening]:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    while True:
        history = _get_history(client)
        matching = [item for item in history.items if item.opening_id in expected_ids]
        if {item.opening_id for item in matching} == expected_ids:
            return matching
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: Lottery openings {sorted(map(str, expected_ids))} "
                f"were not persisted within {timeout_seconds:g}s",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.25, remaining))


def _wait_for_currency_reward_balance(
    client: BalanceClient,
    account_uuid: UUID,
    *,
    before: BalanceResponse,
    opening: Opening | OpeningResult,
    timeout_seconds: float,
) -> BalanceResponse:
    if opening.reward_type != "currency":
        return _get_balance(client, account_uuid)
    payload = opening.reward_payload
    assert isinstance(payload, dict), "currency reward must have an object payload"
    currency = payload.get("currency")
    amount = payload.get("amount")
    assert isinstance(amount, int) and amount > 0, "currency reward amount must be positive"
    if currency == "SFT":
        field = "soft"
        expected = (before.soft or 0) + amount
    elif currency == "PXG":
        field = "hard"
        expected = (before.hard or 0) + amount * PXG_MINOR_UNITS
    else:
        pytest.fail(f"PRODUCT_DEFECT: unsupported Lottery currency reward {currency!r}")
    deadline = monotonic() + timeout_seconds
    waiter = Event()
    while True:
        current = _get_balance(client, account_uuid)
        if (getattr(current, field) or 0) == expected:
            return current
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: Lottery {currency} reward did not settle to {expected} "
                f"within {timeout_seconds:g}s",
                pytrace=False,
            )
        waiter.wait(timeout=min(0.25, remaining))


def _assert_single_currency_credit(client: BalanceClient, opening: Opening | OpeningResult) -> None:
    if opening.reward_type != "currency":
        return
    payload = opening.reward_payload
    assert isinstance(payload, dict)
    currency = payload.get("currency")
    assert isinstance(currency, str)
    balance_currency = {"SFT": "soft", "PXG": "hard"}.get(currency)
    assert balance_currency is not None
    response = client.get_history(limit=50, currency=balance_currency)
    assert_response_status(response, 200)
    history = validate_success_data(response, HistoryResponse)
    matching = [
        transaction
        for transaction in history.items
        if transaction.source_type == "lottery_reward_credit"
        and transaction.source_id is not None
        and str(opening.opening_id) in transaction.source_id
    ]
    assert len(matching) == 1, "idempotent opening must create exactly one currency credit"


def _assert_opening_persistence(
    opened: OpenChestResponse,
    persisted: list[Opening],
    chest: ChestConfig,
) -> None:
    by_id = {opening.opening_id: opening for opening in persisted}
    assert len(by_id) == opened.quantity
    for result in opened.openings:
        stored = by_id[result.opening_id]
        assert stored.open_batch_id == opened.open_batch_id
        assert stored.chest_id == opened.chest_id
        assert stored.season_id == opened.season_id
        assert stored.cost_keys == chest.cost_keys
        assert stored.open_index == result.open_index
        assert stored.reward_id == result.reward_id
        assert stored.reward_type == result.reward_type
        assert stored.reward_payload == result.reward_payload
        assert stored.reward_probability == result.reward_probability
        assert stored.status.strip()
