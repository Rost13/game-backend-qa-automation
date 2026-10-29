from __future__ import annotations

from datetime import UTC, datetime
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

import allure
import pytest
from fixtures.inventory import GrantedInventoryItem

from qa_automation.clients.base import assert_response_status, validate_success_data
from qa_automation.clients.stat_api import StatApiClient
from qa_automation.config import Settings
from qa_automation.db.stat_api import StatClickHouseDatabase, StatReceiveRecord
from qa_automation.models.stat_api import StatStatus

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.regression,
    pytest.mark.serial,
    allure.feature("Stat API ClickHouse"),
]


@allure.title("Stat ClickHouse connection is read-only and can read raw events")
@pytest.mark.smoke
def test_stat_clickhouse_connection_is_read_only(
    required_stat_database: StatClickHouseDatabase,
    stat_clickhouse_settings: Settings | None,
) -> None:
    assert stat_clickhouse_settings is not None
    assert required_stat_database.read_only_setting() == 1
    assert (
        required_stat_database.database_name() == stat_clickhouse_settings.stat_clickhouse_database
    )
    assert required_stat_database.raw_events_table_is_readable() is True


@allure.title("Stat receive webhook is persisted exactly once for one request ID")
def test_receive_webhook_is_idempotently_persisted(
    stat_event_settings: Settings,
    stat_user_client: StatApiClient,
    api_test_user_uuid: UUID,
    required_stat_database: StatClickHouseDatabase,
) -> None:
    item_id = uuid4()
    request_id = f"qa-stat-{uuid4()}"
    payload: dict[str, object] = {
        "request_id": request_id,
        "name": "receive",
        "data": {
            "user_uuid": str(api_test_user_uuid),
            "event_ts": datetime.now(UTC).isoformat(),
            "version": "qa-automation",
            "geo": "",
            "platform": "api-test",
            "device": "pytest",
            "level": 0,
            "item_type": "qa_test_item",
            "item_id": str(item_id),
            "amount": 1,
            "source_type": "qa_automation",
            "source_id": request_id,
        },
    }

    first_response = stat_user_client.send_client_event(payload)
    duplicate_response = stat_user_client.send_client_event(payload)

    assert_response_status(first_response, 200)
    assert_response_status(duplicate_response, 200)
    assert validate_success_data(first_response, StatStatus).status == "ok"
    assert validate_success_data(duplicate_response, StatStatus).status == "ok"
    events = _wait_for_exactly_one_stable_receive_event(
        required_stat_database,
        api_test_user_uuid,
        item_id,
        stat_event_settings.stat_event_timeout.total_seconds(),
    )
    event = events[0]
    assert event.item_type == "qa_test_item"
    assert event.amount == 1
    assert event.source_type == "qa_automation"
    assert event.source_id == request_id


@allure.title("Goods to Inventory records the created user item in Stat ClickHouse")
def test_inventory_delivery_records_user_item_in_stat_clickhouse(
    granted_inventory_item: GrantedInventoryItem,
    api_test_user_uuid: UUID,
    stat_live_settings: Settings,
    required_stat_database: StatClickHouseDatabase,
) -> None:
    events = _wait_for_exactly_one_stable_receive_event(
        required_stat_database,
        api_test_user_uuid,
        granted_inventory_item.item_uuid,
        stat_live_settings.stat_event_timeout.total_seconds(),
    )

    event = events[0]
    assert event.user_uuid == api_test_user_uuid
    assert event.item_id == granted_inventory_item.item_uuid
    assert event.item_type == granted_inventory_item.item_type
    assert event.amount == 1
    assert event.source_type == "item_receive_inventory"
    assert event.source_id == "inventory_service"


def _wait_for_exactly_one_stable_receive_event(
    database: StatClickHouseDatabase,
    user_uuid: UUID,
    item_id: UUID,
    timeout_seconds: float,
) -> list[StatReceiveRecord]:
    deadline = monotonic() + timeout_seconds
    stable_since: float | None = None
    waiter = Event()
    last_events: list[StatReceiveRecord] = []
    while True:
        last_events = database.get_receive_events(user_uuid=user_uuid, item_id=item_id)
        if len(last_events) > 1:
            pytest.fail(
                f"PRODUCT_DEFECT: Stat persisted {len(last_events)} receive events for "
                f"one item {item_id}",
                pytrace=False,
            )
        now = monotonic()
        if len(last_events) == 1:
            stable_since = stable_since or now
            if now - stable_since >= 1.0:
                return last_events
        else:
            stable_since = None

        remaining = deadline - now
        if remaining <= 0:
            pytest.fail(
                f"PRODUCT_DEFECT: Stat did not persist one receive event for item {item_id} "
                f"within {timeout_seconds:g}s; last count {len(last_events)}",
                pytrace=False,
            )
        waiter.wait(timeout=min(0.25, remaining))
