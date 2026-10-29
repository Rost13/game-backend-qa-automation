from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from qa_automation.config import Settings


@dataclass(frozen=True)
class StatReceiveRecord:
    user_uuid: UUID
    event_ts: datetime
    item_type: str
    item_id: UUID
    amount: int
    source_type: str
    source_id: str


class StatClickHouseDatabase:
    """Read-only ClickHouse access for Stat API persistence assertions."""

    def __init__(self, settings: Settings) -> None:
        missing = settings.missing_stat_clickhouse_configuration()
        if missing:
            raise ValueError(f"missing Stat ClickHouse configuration: {', '.join(missing)}")

        password = settings.stat_clickhouse_password
        assert password is not None
        scheme = "https" if settings.stat_clickhouse_secure else "http"
        self._database = settings.stat_clickhouse_database
        self._client = httpx.Client(
            base_url=f"{scheme}://{settings.stat_clickhouse_host}:{settings.stat_clickhouse_http_port}",
            auth=(settings.stat_clickhouse_user or "", password.get_secret_value()),
            timeout=httpx.Timeout(settings.stat_clickhouse_connect_timeout_seconds),
            headers={"User-Agent": "game-backend-qa-automation/0.1"},
        )

    def close(self) -> None:
        self._client.close()

    def database_name(self) -> str:
        rows = self._query("SELECT currentDatabase() AS database FORMAT JSONEachRow")
        if len(rows) != 1:
            raise AssertionError("ClickHouse did not return exactly one current database")
        return str(rows[0]["database"])

    def read_only_setting(self) -> int:
        rows = self._query("SELECT getSetting('readonly') AS readonly FORMAT JSONEachRow")
        if len(rows) != 1:
            raise AssertionError("ClickHouse did not return its readonly setting")
        return int(rows[0]["readonly"])

    def raw_events_table_is_readable(self) -> bool:
        rows = self._query(
            "SELECT count() AS count FROM system.tables "
            "WHERE database = currentDatabase() "
            "AND name = 'raw_events_distributed' FORMAT JSONEachRow"
        )
        return len(rows) == 1 and int(rows[0]["count"]) == 1

    def get_receive_events(
        self,
        *,
        user_uuid: UUID,
        item_id: UUID,
    ) -> list[StatReceiveRecord]:
        rows = self._query(
            """
            SELECT
                toString(user_uuid) AS user_uuid,
                event_ts,
                JSONExtractString(toJSONString(params), 'item_type') AS item_type,
                JSONExtractString(toJSONString(params), 'item_id') AS item_id,
                JSONExtractInt(toJSONString(params), 'amount') AS amount,
                JSONExtractString(toJSONString(params), 'source_type') AS source_type,
                JSONExtractString(toJSONString(params), 'source_id') AS source_id
            FROM raw_events_distributed
            WHERE user_uuid = toUUID({user_uuid:String})
              AND event = 'receive'
              AND JSONExtractString(toJSONString(params), 'item_id') = {item_id:String}
            ORDER BY event_ts
            FORMAT JSONEachRow
            """,
            parameters={"user_uuid": str(user_uuid), "item_id": str(item_id)},
        )
        return [self._receive_record(row) for row in rows]

    def _query(
        self,
        query: str,
        *,
        parameters: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        request_parameters = {
            "database": self._database or "",
            "readonly": "1",
            "max_execution_time": "10",
        }
        request_parameters.update(
            {f"param_{name}": value for name, value in (parameters or {}).items()}
        )
        response = self._client.post("/", params=request_parameters, content=query.strip())
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            raise RuntimeError(
                f"ClickHouse request failed with HTTP {response.status_code}"
            ) from None
        rows: list[dict[str, Any]] = []
        for line in response.text.splitlines():
            if not line.strip():
                continue
            decoded = json.loads(line)
            if not isinstance(decoded, dict):
                raise ValueError("ClickHouse JSONEachRow response contained a non-object row")
            rows.append(decoded)
        return rows

    @staticmethod
    def _receive_record(row: dict[str, Any]) -> StatReceiveRecord:
        timestamp = datetime.fromisoformat(str(row["event_ts"]).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return StatReceiveRecord(
            user_uuid=UUID(str(row["user_uuid"])),
            event_ts=timestamp,
            item_type=str(row["item_type"]),
            item_id=UUID(str(row["item_id"])),
            amount=int(row["amount"]),
            source_type=str(row["source_type"]),
            source_id=str(row["source_id"]),
        )
