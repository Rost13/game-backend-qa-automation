from __future__ import annotations

from uuid import uuid4

import allure
import pytest

from qa_automation.clients.base import assert_response_status, validate_response_model
from qa_automation.clients.battle_pass import BattlePassClient
from qa_automation.config import Settings
from qa_automation.models.battle_pass import SeasonView, XPGrantResponse

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.regression,
    pytest.mark.serial,
    allure.feature("Battle Pass"),
]


@allure.title("Battle Pass test XP grant is applied exactly once")
def test_battle_pass_test_xp_grant_is_idempotent(
    battle_pass_user_client: BattlePassClient,
    battle_pass_mutation_settings: Settings,
) -> None:
    before_response = battle_pass_user_client.get_active()
    assert_response_status(before_response, 200)
    before = validate_response_model(before_response, SeasonView)
    amount = battle_pass_mutation_settings.battle_pass_test_xp_amount
    idempotency_key = f"qa-battle-pass-{uuid4()}"

    first_response = battle_pass_user_client.add_test_xp(amount, idempotency_key)

    assert_response_status(first_response, 200)
    first = validate_response_model(first_response, XPGrantResponse)
    assert first.applied is True
    assert first.progress.total_xp == before.progress.total_xp + amount

    duplicate_response = battle_pass_user_client.add_test_xp(amount, idempotency_key)
    active_response = battle_pass_user_client.get_active()

    assert_response_status(duplicate_response, 200)
    assert_response_status(active_response, 200)
    duplicate = validate_response_model(duplicate_response, XPGrantResponse)
    active = validate_response_model(active_response, SeasonView)
    assert duplicate.applied is False
    assert duplicate.progress.total_xp == first.progress.total_xp
    assert active.progress.total_xp == first.progress.total_xp
