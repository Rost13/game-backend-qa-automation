from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Event
from time import monotonic
from uuid import UUID

import allure
import pytest

from qa_automation.clients.balance import BalanceClient
from qa_automation.clients.base import (
    assert_response_status,
    validate_response_model,
    validate_success_data,
)
from qa_automation.clients.battle_pass import BattlePassClient
from qa_automation.clients.boosters import BoostersClient
from qa_automation.clients.daily_quests import DailyQuestsClient
from qa_automation.clients.goods import GoodsClient
from qa_automation.clients.inventory import InventoryClient
from qa_automation.clients.profile import ProfileClient
from qa_automation.config import Settings
from qa_automation.models.balance import PXG_MINOR_UNITS, BalanceResponse
from qa_automation.models.battle_pass import SeasonView
from qa_automation.models.boosters import BoosterState, BoosterStates
from qa_automation.models.daily_quests import (
    DailyQuestsResponse,
    DailyRewardClaimResponse,
    DailyRewardsState,
    QuestClaimResponse,
    ReadyClaimCountResponse,
)
from qa_automation.models.goods import CatalogItem
from qa_automation.models.inventory import InventoryItemList
from qa_automation.models.profile import Profile
from qa_automation.oracles import reward_expiration_window

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.regression,
    pytest.mark.serial,
    allure.feature("Daily Quests"),
]


@allure.title("A completed quest grants its exact reward once")
def test_completed_daily_quest_grants_balance_reward_once(
    daily_quests_user_client: DailyQuestsClient,
    daily_quest_claim_settings: Settings,
    daily_quest_claim_balance_context: tuple[BalanceClient, UUID],
    battle_pass_user_client: BattlePassClient,
) -> None:
    balance_admin_client, balance_test_user_uuid = daily_quest_claim_balance_context
    quests_response = daily_quests_user_client.get_quests()
    count_before_response = daily_quests_user_client.get_ready_claim_count()
    assert_response_status(quests_response, 200)
    assert_response_status(count_before_response, 200)
    quests = validate_response_model(quests_response, DailyQuestsResponse)
    count_before = validate_response_model(count_before_response, ReadyClaimCountResponse)
    ready = [
        quest
        for quest in quests.quests
        if (
            not quest.reward.issued
            and quest.progress.current >= quest.progress.target
            and quest.reward.battle_pass_xp > 0
        )
    ]
    if not ready:
        pytest.fail(
            "TEST_DATA_DEFECT: the Daily Quests test user has no completed unclaimed quest "
            "with a positive Battle Pass XP reward",
            pytrace=False,
        )
    assert count_before.ready_claim_count >= len(ready)
    quest = ready[0]
    balance_before = _get_balance(balance_admin_client, balance_test_user_uuid)
    battle_pass_before = _get_battle_pass(battle_pass_user_client)

    claim_response = daily_quests_user_client.claim_quest(str(quest.quest_uuid))

    assert_response_status(claim_response, 200)
    claimed = validate_response_model(claim_response, QuestClaimResponse)
    assert claimed.reward.xp == quest.reward.xp
    assert claimed.reward.soft == quest.reward.soft
    assert claimed.reward.pxg == quest.reward.pxg
    assert claimed.reward.keys == quest.reward.keys
    assert claimed.reward.battle_pass_xp == quest.reward.battle_pass_xp
    expected_balance = _balance_after_quest_reward(balance_before, claimed)
    settled_balance = _wait_for_balance(
        balance_admin_client,
        balance_test_user_uuid,
        expected_balance,
        daily_quest_claim_settings.daily_quests_event_timeout.total_seconds(),
    )
    settled_battle_pass = _wait_for_battle_pass_xp(
        battle_pass_user_client,
        battle_pass_before.progress.total_xp + claimed.reward.battle_pass_xp,
        daily_quest_claim_settings.daily_quests_event_timeout.total_seconds(),
    )

    refreshed_response = daily_quests_user_client.get_quests()
    count_after_response = daily_quests_user_client.get_ready_claim_count()
    assert_response_status(refreshed_response, 200)
    assert_response_status(count_after_response, 200)
    refreshed = validate_response_model(refreshed_response, DailyQuestsResponse)
    count_after = validate_response_model(count_after_response, ReadyClaimCountResponse)
    refreshed_quest = next(item for item in refreshed.quests if item.quest_uuid == quest.quest_uuid)
    assert refreshed_quest.reward.issued is True
    assert count_after.ready_claim_count == count_before.ready_claim_count - 1

    duplicate_response = daily_quests_user_client.claim_quest(str(quest.quest_uuid))
    balance_after_duplicate = _get_balance(balance_admin_client, balance_test_user_uuid)
    battle_pass_after_duplicate = _get_battle_pass(battle_pass_user_client)

    assert _balance_values(balance_after_duplicate) == _balance_values(settled_balance), (
        "duplicate quest claim must not issue a second balance reward"
    )
    assert battle_pass_after_duplicate.progress.total_xp == settled_battle_pass.progress.total_xp, (
        "duplicate quest claim must not issue Battle Pass XP twice"
    )
    assert_response_status(duplicate_response, 409)


@allure.title("Daily streak progresses at most once and an available reward is claimed once")
def test_daily_streak_progress_and_claim_are_single_issue(
    daily_quests_user_client: DailyQuestsClient,
    daily_rewards_mutation_settings: Settings,
    daily_reward_balance_context: tuple[BalanceClient, UUID],
    goods_admin_client: GoodsClient,
    boosters_admin_client: BoostersClient,
    inventory_admin_client: InventoryClient,
    profile_user_client: ProfileClient,
) -> None:
    balance_admin_client, balance_test_user_uuid = daily_reward_balance_context
    before_response = daily_quests_user_client.get_daily_rewards()
    assert_response_status(before_response, 200)
    before = validate_response_model(before_response, DailyRewardsState)
    if before.is_config_completed:
        pytest.fail(
            "TEST_DATA_DEFECT: the Daily Quests test user completed the daily-reward config",
            pytrace=False,
        )

    progress_response = daily_quests_user_client.mark_daily_reward_progress()
    assert_response_status(progress_response, 200)
    progressed = validate_response_model(progress_response, DailyRewardsState)
    assert (progressed.current_week, progressed.current_day) >= (
        before.current_week,
        before.current_day,
    )
    assert progressed.streak_total_day - before.streak_total_day in {0, 1}

    repeated_progress_response = daily_quests_user_client.mark_daily_reward_progress()
    assert_response_status(repeated_progress_response, 200)
    repeated_progress = validate_response_model(repeated_progress_response, DailyRewardsState)
    assert _progress_fingerprint(repeated_progress) == _progress_fingerprint(progressed)

    available = next(
        (reward for reward in progressed.rewards if reward.status == "available"),
        None,
    )
    if available is None:
        pytest.fail(
            "TEST_DATA_DEFECT: daily reward progress produced no available reward",
            pytrace=False,
        )
    balance_delta = _daily_reward_balance_delta(available.reward_payload)
    balance_before = (
        _get_balance(balance_admin_client, balance_test_user_uuid)
        if balance_delta is not None
        else None
    )
    goods_context = (
        _prepare_good_reward_context(
            available.reward_type,
            available.reward_payload,
            goods_admin_client,
            boosters_admin_client,
            inventory_admin_client,
            profile_user_client,
            balance_test_user_uuid,
        )
        if balance_delta is None
        else None
    )

    claim_started_at = datetime.now(UTC)
    claim_response = daily_quests_user_client.claim_daily_reward(
        available.week,
        available.day,
    )

    assert_response_status(claim_response, 200)
    claimed = validate_response_model(claim_response, DailyRewardClaimResponse)
    assert claimed.reward.week == available.week
    assert claimed.reward.day == available.day
    assert claimed.reward.reward_type == available.reward_type
    assert claimed.reward.reward_payload == available.reward_payload

    settled_balance: BalanceResponse | None = None
    if balance_before is not None and balance_delta is not None:
        expected_balance = _balance_after_delta(balance_before, balance_delta)
        settled_balance = _wait_for_balance(
            balance_admin_client,
            balance_test_user_uuid,
            expected_balance,
            daily_rewards_mutation_settings.daily_quests_event_timeout.total_seconds(),
        )
    settled_goods = (
        _wait_for_good_reward(
            goods_context,
            boosters_admin_client,
            inventory_admin_client,
            profile_user_client,
            balance_test_user_uuid,
            claim_started_at,
            daily_rewards_mutation_settings.daily_quests_event_timeout.total_seconds(),
        )
        if goods_context is not None
        else None
    )

    refreshed_response = daily_quests_user_client.get_daily_rewards()
    assert_response_status(refreshed_response, 200)
    refreshed = validate_response_model(refreshed_response, DailyRewardsState)
    refreshed_slot = next(
        reward
        for reward in refreshed.rewards
        if (reward.week, reward.day) == (available.week, available.day)
    )
    assert refreshed_slot.status == "claimed"

    duplicate_response = daily_quests_user_client.claim_daily_reward(
        available.week,
        available.day,
    )
    if settled_balance is not None:
        balance_after_duplicate = _get_balance(balance_admin_client, balance_test_user_uuid)
        assert _balance_values(balance_after_duplicate) == _balance_values(settled_balance), (
            "duplicate daily reward claim must not issue a second currency reward"
        )
    if goods_context is not None and settled_goods is not None:
        assert (
            _good_reward_fingerprint(
                goods_context,
                boosters_admin_client,
                inventory_admin_client,
                profile_user_client,
                balance_test_user_uuid,
            )
            == settled_goods
        ), "duplicate daily reward claim must not issue a second goods reward"
    assert_response_status(duplicate_response, 400)


@dataclass(frozen=True)
class GoodRewardContext:
    kind: str
    goods_uuid: UUID
    duration_seconds: int
    booster_type: str | None = None
    category: str | None = None
    item_class: str | None = None
    before: datetime | int | None = None


def _prepare_good_reward_context(
    reward_type: str,
    payload: dict[str, object],
    goods_client: GoodsClient,
    boosters_client: BoostersClient,
    inventory_client: InventoryClient,
    profile_client: ProfileClient,
    user_uuid: UUID,
) -> GoodRewardContext:
    raw_uuid = payload.get("good_uuid")
    if not isinstance(raw_uuid, str):
        pytest.fail(
            f"TEST_DATA_DEFECT: unsupported daily reward {reward_type!r} payload {payload!r}",
            pytrace=False,
        )
    try:
        goods_uuid = UUID(raw_uuid)
    except ValueError:
        pytest.fail("TEST_DATA_DEFECT: daily reward good_uuid is malformed", pytrace=False)
    response = goods_client.get_catalog_item(goods_uuid)
    assert_response_status(response, 200)
    catalog = validate_success_data(response, CatalogItem)
    normalized = reward_type.casefold()
    if normalized == "booster_grant":
        assert catalog.config.booster is not None, (
            "TEST_DATA_DEFECT: booster reward references a non-booster good"
        )
        booster = catalog.config.booster
        states = _get_boosters(boosters_client, user_uuid)
        current = next((state for state in states if state.type == booster.booster_type), None)
        return GoodRewardContext(
            "booster",
            goods_uuid,
            booster.duration_seconds,
            booster_type=booster.booster_type,
            before=current.expires_at if current is not None else None,
        )
    if normalized == "inventory_grant":
        assert catalog.core.is_item and catalog.config.item is not None, (
            "TEST_DATA_DEFECT: inventory reward references a non-item good"
        )
        category = catalog.core.goods_type
        item_class = catalog.config.item.class_
        quantity = _inventory_quantity(
            inventory_client, category, item_class, user_uuid, goods_uuid
        )
        return GoodRewardContext(
            "inventory",
            goods_uuid,
            0,
            category=category,
            item_class=item_class,
            before=quantity,
        )
    if normalized == "premium_extend":
        assert catalog.config.subscription is not None, (
            "TEST_DATA_DEFECT: premium reward references a non-subscription good"
        )
        profile = _get_profile(profile_client)
        return GoodRewardContext(
            "premium",
            goods_uuid,
            catalog.config.subscription.duration_seconds,
            before=profile.premium.expiration,
        )
    pytest.fail(f"TEST_DATA_DEFECT: unsupported daily reward type {reward_type!r}", pytrace=False)


def _wait_for_good_reward(
    context: GoodRewardContext,
    boosters_client: BoostersClient,
    inventory_client: InventoryClient,
    profile_client: ProfileClient,
    user_uuid: UUID,
    observed_at: datetime,
    timeout_seconds: float,
) -> datetime | int:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    expiration_window = (
        reward_expiration_window(
            context.before if isinstance(context.before, datetime) else None,
            observed_at,
            timedelta(seconds=context.duration_seconds),
            timedelta(seconds=2),
        )
        if context.kind != "inventory"
        else None
    )
    while True:
        current = _good_reward_fingerprint(
            context, boosters_client, inventory_client, profile_client, user_uuid
        )
        if context.kind == "inventory":
            assert isinstance(context.before, int)
            if current == context.before + 1:
                return current
        elif isinstance(current, datetime) and expiration_window is not None:
            lower, upper = expiration_window
            if lower <= current <= upper:
                return current
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: {context.kind} daily reward was not delivered within "
                f"{timeout_seconds:g}s",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.25, remaining))


def _good_reward_fingerprint(
    context: GoodRewardContext,
    boosters_client: BoostersClient,
    inventory_client: InventoryClient,
    profile_client: ProfileClient,
    user_uuid: UUID,
) -> datetime | int | None:
    if context.kind == "booster":
        current = next(
            (
                state
                for state in _get_boosters(boosters_client, user_uuid)
                if state.type == context.booster_type
            ),
            None,
        )
        return current.expires_at if current is not None else None
    if context.kind == "inventory":
        assert context.category is not None and context.item_class is not None
        return _inventory_quantity(
            inventory_client,
            context.category,
            context.item_class,
            user_uuid,
            context.goods_uuid,
        )
    return _get_profile(profile_client).premium.expiration


def _get_boosters(client: BoostersClient, user_uuid: UUID) -> list[BoosterState]:
    response = client.get_active_by_uuid(user_uuid)
    assert_response_status(response, 200)
    return validate_success_data(response, BoosterStates).root


def _inventory_quantity(
    client: InventoryClient,
    category: str,
    item_class: str,
    user_uuid: UUID,
    goods_uuid: UUID,
) -> int:
    response = client.get_items_by_uuid(category, user_uuid, item_class)
    assert_response_status(response, 200)
    items = validate_success_data(response, InventoryItemList)
    return sum(item.quantity for item in items.items if item.def_uuid == goods_uuid)


def _get_profile(client: ProfileClient) -> Profile:
    response = client.get_me()
    assert_response_status(response, 200)
    return validate_success_data(response, Profile)


def _get_balance(client: BalanceClient, account_uuid: UUID) -> BalanceResponse:
    response = client.get_balance_by_uuid(account_uuid)
    assert_response_status(response, 200)
    return validate_success_data(response, BalanceResponse)


def _get_battle_pass(client: BattlePassClient) -> SeasonView:
    response = client.get_active()
    assert_response_status(response, 200)
    return validate_response_model(response, SeasonView)


def _balance_after_quest_reward(
    balance: BalanceResponse,
    claimed: QuestClaimResponse,
) -> tuple[int, int, int, int]:
    hard_delta = claimed.reward.pxg * PXG_MINOR_UNITS
    assert hard_delta == hard_delta.to_integral_value(), (
        f"PRODUCT_DEFECT: quest PXG reward {claimed.reward.pxg} has invalid precision"
    )
    soft, xp, hard, keys = _balance_values(balance)
    return (
        soft + claimed.reward.soft,
        xp + claimed.reward.xp,
        hard + int(hard_delta),
        keys + claimed.reward.keys,
    )


def _daily_reward_balance_delta(payload: dict[str, object]) -> tuple[int, int] | None:
    raw_currency = payload.get("currency")
    raw_amount = payload.get("amount")
    if not isinstance(raw_currency, str) or raw_amount is None:
        return None
    amount = Decimal(str(raw_amount))
    assert amount > 0, "PRODUCT_DEFECT: currency daily reward amount must be positive"
    currency = raw_currency.casefold()
    if currency in {"soft", "sft"}:
        assert amount == amount.to_integral_value()
        return int(amount), 0
    if currency in {"hard", "pxg"}:
        minor_units = amount * PXG_MINOR_UNITS
        assert minor_units == minor_units.to_integral_value()
        return 0, int(minor_units)
    return None


def _balance_after_delta(
    balance: BalanceResponse,
    delta: tuple[int, int],
) -> tuple[int, int, int, int]:
    soft, xp, hard, keys = _balance_values(balance)
    soft_delta, hard_delta = delta
    return soft + soft_delta, xp, hard + hard_delta, keys


def _wait_for_balance(
    client: BalanceClient,
    account_uuid: UUID,
    expected: tuple[int, int, int, int],
    timeout_seconds: float,
) -> BalanceResponse:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    last: BalanceResponse | None = None
    while True:
        last = _get_balance(client, account_uuid)
        if _balance_values(last) == expected:
            return last
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: balance did not become {expected} within "
                f"{timeout_seconds:g}s; last value {_balance_values(last)}",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.25, remaining))


def _wait_for_battle_pass_xp(
    client: BattlePassClient,
    expected_total_xp: int,
    timeout_seconds: float,
) -> SeasonView:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    last: SeasonView | None = None
    while True:
        last = _get_battle_pass(client)
        if last.progress.total_xp == expected_total_xp:
            return last
        remaining = deadline - monotonic()
        if remaining <= 0:
            pytest.fail(
                "PRODUCT_DEFECT: Battle Pass total_xp did not become "
                f"{expected_total_xp} within {timeout_seconds:g}s; "
                f"last value {last.progress.total_xp}",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.25, remaining))


def _balance_values(balance: BalanceResponse) -> tuple[int, int, int, int]:
    return balance.soft or 0, balance.xp or 0, balance.hard or 0, balance.keys or 0


def _progress_fingerprint(state: DailyRewardsState) -> tuple[object, ...]:
    return (
        state.current_week,
        state.current_day,
        state.streak_total_day,
        state.completed,
        state.has_available_rewards,
        [(reward.week, reward.day, reward.status) for reward in state.rewards],
    )
