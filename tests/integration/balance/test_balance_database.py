from __future__ import annotations

from threading import Event
from time import monotonic
from uuid import UUID

import allure
import pytest

from qa_automation.clients.balance import BalanceClient
from qa_automation.clients.base import assert_response_status, validate_success_data
from qa_automation.config import Settings
from qa_automation.db.balance import BalanceCurrency, BalanceDatabase, BalanceRecord
from qa_automation.models.balance import BalanceResponse, ReplenishResponse

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    allure.feature("Balance database"),
]


@allure.title("Balance database connection is read-only and can read balances")
@pytest.mark.smoke
def test_balance_database_connection_is_read_only(
    required_balance_database: BalanceDatabase,
    balance_database_settings: Settings | None,
) -> None:
    assert balance_database_settings is not None
    assert required_balance_database.read_only_setting() == "on"
    assert required_balance_database.database_name() == balance_database_settings.balance_db_name
    assert required_balance_database.balances_table_is_readable() is True


@allure.title("Balance API returns the persisted balances for the test user")
@pytest.mark.regression
def test_balance_api_matches_database_records(
    balance_admin_client: BalanceClient,
    balance_test_user_uuid: UUID,
    required_balance_database: BalanceDatabase,
) -> None:
    response = balance_admin_client.get_balance_by_uuid(balance_test_user_uuid)

    assert_response_status(response, 200)
    api_balance = validate_success_data(response, BalanceResponse)
    database_balances = required_balance_database.get_account_balances(balance_test_user_uuid)
    assert _api_amount(api_balance, "soft") == _database_amount(database_balances, "soft")
    assert _api_amount(api_balance, "xp") == _database_amount(database_balances, "xp")
    assert _api_amount(api_balance, "hard") == _database_amount(database_balances, "hard")
    assert _api_amount(api_balance, "keys") == _database_amount(database_balances, "keys")


@allure.title("API replenish persists the exact soft balance delta in PostgreSQL")
@pytest.mark.regression
@pytest.mark.serial
def test_api_replenish_updates_balance_database_record(
    balance_admin_client: BalanceClient,
    balance_test_user_uuid: UUID,
    balance_mutation_settings: Settings,
    required_balance_database: BalanceDatabase,
) -> None:
    amount = balance_mutation_settings.balance_replenish_amount
    before = required_balance_database.get_balance(balance_test_user_uuid, "soft")
    before_amount = before.amount if before else 0

    response = balance_admin_client.replenish({"uuid": str(balance_test_user_uuid), "soft": amount})

    assert_response_status(response, 200)
    result = validate_success_data(response, ReplenishResponse)
    assert result.message == "balance replenished successfully"
    persisted = _wait_for_persisted_balance(
        database=required_balance_database,
        account_uuid=balance_test_user_uuid,
        currency="soft",
        expected_amount=before_amount + amount,
        timeout_seconds=balance_mutation_settings.balance_event_timeout.total_seconds(),
    )
    assert persisted.amount - before_amount == amount
    if before is not None:
        assert persisted.ts > before.ts

    api_response = balance_admin_client.get_balance_by_uuid(balance_test_user_uuid)
    assert_response_status(api_response, 200)
    api_balance = validate_success_data(api_response, BalanceResponse)
    assert api_balance.soft == persisted.amount


def _wait_for_persisted_balance(
    *,
    database: BalanceDatabase,
    account_uuid: UUID,
    currency: BalanceCurrency,
    expected_amount: int,
    timeout_seconds: float,
) -> BalanceRecord:
    deadline = monotonic() + timeout_seconds
    poll_waiter = Event()
    last_record: BalanceRecord | None = None

    while True:
        last_record = database.get_balance(account_uuid, currency)
        if last_record is not None and last_record.amount == expected_amount:
            return last_record
        if last_record is not None and last_record.amount > expected_amount:
            pytest.fail(
                f"TEST_DATA_DEFECT: persisted {currency} balance exceeded expected amount; "
                f"expected {expected_amount}, got {last_record.amount}",
                pytrace=False,
            )

        remaining = deadline - monotonic()
        if remaining <= 0:
            last_amount = last_record.amount if last_record else None
            pytest.fail(
                f"PRODUCT_DEFECT: API replenish was not persisted in balances within "
                f"{timeout_seconds:g}s; expected {expected_amount}, last value {last_amount}",
                pytrace=False,
            )
        poll_waiter.wait(timeout=min(0.25, remaining))


def _api_amount(balance: BalanceResponse, currency: BalanceCurrency) -> int:
    value = getattr(balance, currency)
    assert isinstance(value, int | None)
    return value or 0


def _database_amount(
    balances: dict[BalanceCurrency, BalanceRecord],
    currency: BalanceCurrency,
) -> int:
    record = balances.get(currency)
    return record.amount if record else 0
