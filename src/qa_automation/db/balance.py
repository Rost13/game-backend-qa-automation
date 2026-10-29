from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from qa_automation.config import Settings

BalanceCurrency = Literal["soft", "xp", "hard", "keys"]


@dataclass(frozen=True)
class BalanceRecord:
    uid: UUID
    currency: BalanceCurrency
    amount: int
    ts: datetime


class BalanceDatabase:
    """Read-only access to Balance persistence for API-to-database assertions."""

    def __init__(self, settings: Settings) -> None:
        missing = settings.missing_balance_database_configuration()
        if missing:
            raise ValueError(f"missing Balance database configuration: {', '.join(missing)}")

        password = settings.balance_db_password
        assert password is not None
        self._connection: psycopg.Connection[dict[str, Any]] = psycopg.connect(
            host=settings.balance_db_host,
            port=settings.balance_db_port,
            dbname=settings.balance_db_name,
            user=settings.balance_db_user,
            password=password.get_secret_value(),
            sslmode=settings.balance_db_sslmode,
            connect_timeout=settings.balance_db_connect_timeout_seconds,
            options=(
                "-c default_transaction_read_only=on -c application_name=game-backend-qa-automation"
            ),
            autocommit=True,
            row_factory=dict_row,
        )
        self._schema = settings.balance_db_schema

    def close(self) -> None:
        self._connection.close()

    def read_only_setting(self) -> str:
        with self._connection.cursor() as cursor:
            cursor.execute("SHOW default_transaction_read_only")
            row = cursor.fetchone()
        if row is None:
            raise AssertionError("PostgreSQL did not return default_transaction_read_only")
        return str(row["default_transaction_read_only"])

    def database_name(self) -> str:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT current_database() AS database_name")
            row = cursor.fetchone()
        if row is None:
            raise AssertionError("PostgreSQL did not return current_database")
        return str(row["database_name"])

    def balances_table_is_readable(self) -> bool:
        qualified_name = f"{self._schema}.balances"
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT to_regclass(%s) IS NOT NULL
                       AND has_table_privilege(current_user, %s, 'SELECT') AS readable
                """,
                (qualified_name, qualified_name),
            )
            row = cursor.fetchone()
        return bool(row and row["readable"])

    def get_balance(self, account_uuid: UUID, currency: BalanceCurrency) -> BalanceRecord | None:
        query = sql.SQL(
            """
            SELECT uid, currency::text AS currency, amount, ts
            FROM {}.{}
            WHERE uid = %s AND currency = %s
            """
        ).format(sql.Identifier(self._schema), sql.Identifier("balances"))
        with self._connection.cursor() as cursor:
            cursor.execute(query, (account_uuid, currency))
            row = cursor.fetchone()
        return BalanceRecord(**row) if row else None

    def get_account_balances(self, account_uuid: UUID) -> dict[BalanceCurrency, BalanceRecord]:
        query = sql.SQL(
            """
            SELECT uid, currency::text AS currency, amount, ts
            FROM {}.{}
            WHERE uid = %s
            ORDER BY currency
            """
        ).format(sql.Identifier(self._schema), sql.Identifier("balances"))
        with self._connection.cursor() as cursor:
            cursor.execute(query, (account_uuid,))
            rows = cursor.fetchall()
        records = [BalanceRecord(**row) for row in rows]
        return {record.currency: record for record in records}
