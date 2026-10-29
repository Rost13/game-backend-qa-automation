from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from qa_automation.config import Settings


@dataclass(frozen=True)
class PromoRecord:
    uuid: str
    code: str
    is_active: bool
    reward_currency: str
    reward_amount: int | None
    max_claims: int | None
    claims_used: int


class PromocodesDatabase:
    """Read-only PostgreSQL access used only for meaningful persistence checks."""

    def __init__(self, settings: Settings) -> None:
        missing = settings.missing_database_configuration()
        if missing:
            raise ValueError(f"missing database configuration: {', '.join(missing)}")

        password = settings.promocodes_db_password
        assert password is not None
        self._connection: psycopg.Connection[dict[str, Any]] = psycopg.connect(
            host=settings.promocodes_db_host,
            port=settings.promocodes_db_port,
            dbname=settings.promocodes_db_name,
            user=settings.promocodes_db_user,
            password=password.get_secret_value(),
            sslmode=settings.promocodes_db_sslmode,
            connect_timeout=settings.db_connect_timeout_seconds,
            options=(
                "-c default_transaction_read_only=on -c application_name=game-backend-qa-automation"
            ),
            autocommit=True,
            row_factory=dict_row,
        )
        self._schema = settings.promocodes_db_schema

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

    def readable_tables(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for table in ("promocodes", "promocode_applications"):
            qualified_name = f"{self._schema}.{table}"
            query = sql.SQL(
                """
                SELECT to_regclass(%s) IS NOT NULL
                       AND has_table_privilege(current_user, %s, 'SELECT') AS readable
                """
            )
            with self._connection.cursor() as cursor:
                cursor.execute(query, (qualified_name, qualified_name))
                row = cursor.fetchone()
            results[table] = bool(row and row["readable"])
        return results

    def get_promo(self, promo_uuid: str) -> PromoRecord | None:
        query = sql.SQL(
            """
            SELECT uuid::text, code, is_active, reward_currency, reward_amount,
                   max_claims, claims_used
            FROM {}.{}
            WHERE uuid = %s::uuid
            """
        ).format(sql.Identifier(self._schema), sql.Identifier("promocodes"))
        with self._connection.cursor() as cursor:
            cursor.execute(query, (promo_uuid,))
            row = cursor.fetchone()
        return PromoRecord(**row) if row else None

    def application_count(self, promo_uuid: str) -> int:
        query = sql.SQL("SELECT COUNT(*) AS count FROM {}.{} WHERE promo_uuid = %s::uuid").format(
            sql.Identifier(self._schema), sql.Identifier("promocode_applications")
        )
        with self._connection.cursor() as cursor:
            cursor.execute(query, (promo_uuid,))
            row = cursor.fetchone()
        if row is None:
            raise AssertionError("PostgreSQL did not return application count")
        return int(row["count"])
