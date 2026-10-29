from __future__ import annotations

import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KUBERNETES_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")
_ALLOWED_SSL_MODES = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}


class Settings(BaseSettings):
    """Environment-backed configuration with no committed service credentials."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_prefix="",
        extra="ignore",
    )

    api_tests_enabled: bool = False
    api_test_timeout: timedelta = timedelta(seconds=20)
    api_bearer_token: SecretStr | None = None
    api_admin_bearer_token: SecretStr | None = None
    destructive_rbac_tests_enabled: bool = False
    rbac_disposable_account_uuid: UUID | None = None

    promocodes_base_url: AnyHttpUrl | None = None
    promocodes_api_path: str | None = None
    promocodes_bearer_token: SecretStr | None = None
    promocodes_admin_bearer_token: SecretStr | None = None
    promocodes_mutations_enabled: bool = False
    promocodes_code_prefix: str = "AT"
    promocodes_reward_amount: int = 1
    promocodes_max_claims: int = 5

    balance_base_url: AnyHttpUrl | None = None
    balance_api_path: str | None = None
    balance_mutations_enabled: bool = False
    balance_replenish_amount: int = 1
    balance_event_timeout: timedelta = timedelta(seconds=20)

    balance_db_assertions_enabled: bool = False
    balance_db_host: str | None = None
    balance_db_port: int = Field(default=5432, ge=1, le=65535)
    balance_db_name: str | None = None
    balance_db_schema: str = "public"
    balance_db_user: str | None = None
    balance_db_password: SecretStr | None = None
    balance_db_sslmode: str = "require"
    balance_db_connect_timeout: timedelta = timedelta(seconds=10)
    balance_db_kube_forward_enabled: bool = False
    balance_db_kubectl_path: str = "kubectl"
    balance_db_kube_context: str | None = None
    balance_db_kube_namespace: str | None = None
    balance_db_kube_service: str | None = None
    balance_db_kube_deployment: str | None = None
    balance_db_kube_container: str | None = None
    balance_db_kube_local_port: int = Field(default=15433, ge=1, le=65535)
    balance_db_kube_remote_port: int = Field(default=5432, ge=1, le=65535)
    balance_db_kube_start_timeout: timedelta = timedelta(seconds=20)

    market_proxy_base_url: AnyHttpUrl | None = None
    market_proxy_api_path: str | None = None
    market_proxy_purchases_enabled: bool = False
    market_proxy_purchase_timeout: timedelta = timedelta(seconds=90)

    social_base_url: AnyHttpUrl | None = None
    social_api_path: str | None = None
    social_mutations_enabled: bool = False
    social_peer_bearer_token: SecretStr | None = None
    social_event_timeout: timedelta = timedelta(seconds=20)

    daily_quests_base_url: AnyHttpUrl | None = None
    daily_quests_api_path: str | None = None
    daily_quest_claims_enabled: bool = False
    daily_rewards_mutations_enabled: bool = False
    daily_quests_event_timeout: timedelta = timedelta(seconds=20)

    battle_pass_base_url: AnyHttpUrl | None = None
    battle_pass_api_path: str | None = None
    battle_pass_mutations_enabled: bool = False
    battle_pass_test_xp_amount: int = 1
    battle_pass_event_timeout: timedelta = timedelta(seconds=20)

    boosters_base_url: AnyHttpUrl | None = None
    boosters_api_path: str | None = None
    booster_grants_enabled: bool = False
    booster_test_goods_uuid: UUID | None = None

    inventory_base_url: AnyHttpUrl | None = None
    inventory_api_path: str | None = None
    inventory_test_category: str | None = None
    inventory_test_class: str | None = None
    inventory_grants_enabled: bool = False
    inventory_test_goods_uuid: UUID | None = None

    stat_api_base_url: AnyHttpUrl | None = None
    stat_api_path: str | None = None
    stat_events_enabled: bool = False
    stat_event_timeout: timedelta = timedelta(seconds=30)

    stat_clickhouse_assertions_enabled: bool = False
    stat_clickhouse_host: str | None = None
    stat_clickhouse_http_port: int = Field(default=8123, ge=1, le=65535)
    stat_clickhouse_database: str | None = None
    stat_clickhouse_user: str | None = None
    stat_clickhouse_password: SecretStr | None = None
    stat_clickhouse_secure: bool = False
    stat_clickhouse_connect_timeout: timedelta = timedelta(seconds=10)
    stat_clickhouse_kube_forward_enabled: bool = False
    stat_clickhouse_kubectl_path: str = "kubectl"
    stat_clickhouse_kube_context: str | None = None
    stat_clickhouse_kube_service_namespace: str | None = None
    stat_clickhouse_kube_service: str | None = None
    stat_clickhouse_kube_deployment_namespace: str | None = None
    stat_clickhouse_kube_deployment: str | None = None
    stat_clickhouse_kube_container: str | None = None
    stat_clickhouse_kube_local_port: int = Field(default=18123, ge=1, le=65535)
    stat_clickhouse_kube_remote_port: int = Field(default=8123, ge=1, le=65535)
    stat_clickhouse_kube_start_timeout: timedelta = timedelta(seconds=20)

    goods_base_url: AnyHttpUrl | None = None
    goods_api_path: str | None = None
    goods_catalog_currency: str = "SFT"

    profile_base_url: AnyHttpUrl | None = None
    profile_api_path: str | None = None
    profile_share_bearer_token: SecretStr | None = None
    profile_mutations_enabled: bool = False
    premium_grants_enabled: bool = False
    premium_test_goods_uuid: UUID | None = None
    reward_delivery_timeout: timedelta = timedelta(seconds=20)

    lottery_base_url: AnyHttpUrl | None = None
    lottery_api_path: str | None = None
    lottery_openings_enabled: bool = False
    lottery_keys_topup_enabled: bool = False
    lottery_config_mutations_enabled: bool = False
    lottery_event_timeout: timedelta = timedelta(seconds=20)

    ads_base_url: AnyHttpUrl | None = None
    ads_api_path: str | None = None
    ads_starts_enabled: bool = False
    ads_admin_mutations_enabled: bool = False
    ads_callbacks_enabled: bool = False
    ads_applovin_event_key: SecretStr | None = None
    ads_event_timeout: timedelta = timedelta(seconds=20)

    promocodes_db_assertions_enabled: bool = False
    promocodes_db_host: str | None = None
    promocodes_db_port: int = Field(default=5432, ge=1, le=65535)
    promocodes_db_name: str | None = None
    promocodes_db_schema: str = "public"
    promocodes_db_user: str | None = None
    promocodes_db_password: SecretStr | None = None
    promocodes_db_sslmode: str = "require"
    promocodes_db_connect_timeout: timedelta = timedelta(seconds=10)
    promocodes_db_kube_forward_enabled: bool = False
    promocodes_db_kubectl_path: str = "kubectl"
    promocodes_db_kube_context: str | None = None
    promocodes_db_kube_namespace: str | None = None
    promocodes_db_kube_service: str | None = None
    promocodes_db_kube_deployment: str | None = None
    promocodes_db_kube_container: str | None = None
    promocodes_db_kube_local_port: int = Field(default=15432, ge=1, le=65535)
    promocodes_db_kube_remote_port: int = Field(default=5432, ge=1, le=65535)
    promocodes_db_kube_start_timeout: timedelta = timedelta(seconds=20)

    @field_validator(
        "api_test_timeout",
        "balance_event_timeout",
        "balance_db_connect_timeout",
        "balance_db_kube_start_timeout",
        "market_proxy_purchase_timeout",
        "social_event_timeout",
        "daily_quests_event_timeout",
        "battle_pass_event_timeout",
        "reward_delivery_timeout",
        "lottery_event_timeout",
        "ads_event_timeout",
        "stat_event_timeout",
        "stat_clickhouse_connect_timeout",
        "stat_clickhouse_kube_start_timeout",
        "promocodes_db_connect_timeout",
        "promocodes_db_kube_start_timeout",
        mode="before",
    )
    @classmethod
    def parse_seconds_duration(cls, value: Any) -> Any:
        if isinstance(value, str) and value.endswith("s"):
            try:
                return timedelta(seconds=float(value[:-1]))
            except ValueError:
                return value
        return value

    @field_validator(
        "api_test_timeout",
        "balance_event_timeout",
        "balance_db_connect_timeout",
        "balance_db_kube_start_timeout",
        "market_proxy_purchase_timeout",
        "social_event_timeout",
        "daily_quests_event_timeout",
        "battle_pass_event_timeout",
        "reward_delivery_timeout",
        "lottery_event_timeout",
        "ads_event_timeout",
        "stat_event_timeout",
        "stat_clickhouse_connect_timeout",
        "stat_clickhouse_kube_start_timeout",
        "promocodes_db_connect_timeout",
        "promocodes_db_kube_start_timeout",
    )
    @classmethod
    def duration_must_be_positive(cls, value: timedelta) -> timedelta:
        if value.total_seconds() <= 0:
            raise ValueError("duration must be positive")
        return value

    @field_validator(
        "promocodes_api_path",
        "balance_api_path",
        "market_proxy_api_path",
        "social_api_path",
        "daily_quests_api_path",
        "battle_pass_api_path",
        "boosters_api_path",
        "inventory_api_path",
        "stat_api_path",
        "goods_api_path",
        "profile_api_path",
        "lottery_api_path",
        "ads_api_path",
    )
    @classmethod
    def api_path_must_be_absolute(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        if not normalized.startswith("/"):
            raise ValueError("API path must start with '/'")
        return normalized

    @field_validator("promocodes_code_prefix")
    @classmethod
    def code_prefix_must_be_safe(cls, value: str) -> str:
        normalized = value.strip().upper()
        if (
            not normalized
            or len(normalized) > 4
            or not normalized.isascii()
            or not normalized.isalnum()
        ):
            raise ValueError("PROMOCODES_CODE_PREFIX must be 1-4 ASCII letters or digits")
        return normalized

    @field_validator("promocodes_reward_amount")
    @classmethod
    def reward_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("PROMOCODES_REWARD_AMOUNT must be positive")
        return value

    @field_validator("balance_replenish_amount")
    @classmethod
    def balance_replenish_amount_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("BALANCE_REPLENISH_AMOUNT must be positive")
        return value

    @field_validator("battle_pass_test_xp_amount")
    @classmethod
    def battle_pass_test_xp_amount_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("BATTLE_PASS_TEST_XP_AMOUNT must be positive")
        return value

    @field_validator("promocodes_max_claims")
    @classmethod
    def max_claims_must_allow_duplicate_check(cls, value: int) -> int:
        if value <= 1:
            raise ValueError("PROMOCODES_MAX_CLAIMS must be greater than one")
        return value

    @field_validator("promocodes_db_schema", "balance_db_schema")
    @classmethod
    def schema_must_be_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not _IDENTIFIER_PATTERN.fullmatch(normalized):
            raise ValueError("PROMOCODES_DB_SCHEMA must be a PostgreSQL identifier")
        return normalized

    @field_validator("promocodes_db_sslmode", "balance_db_sslmode")
    @classmethod
    def sslmode_must_be_supported(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in _ALLOWED_SSL_MODES:
            raise ValueError(f"unsupported PROMOCODES_DB_SSLMODE: {normalized}")
        return normalized

    @field_validator(
        "promocodes_db_kube_namespace",
        "promocodes_db_kube_service",
        "promocodes_db_kube_deployment",
        "promocodes_db_kube_container",
        "balance_db_kube_namespace",
        "balance_db_kube_service",
        "balance_db_kube_deployment",
        "balance_db_kube_container",
        "stat_clickhouse_kube_service_namespace",
        "stat_clickhouse_kube_service",
        "stat_clickhouse_kube_deployment_namespace",
        "stat_clickhouse_kube_deployment",
        "stat_clickhouse_kube_container",
    )
    @classmethod
    def kubernetes_name_must_be_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) > 63 or not _KUBERNETES_NAME_PATTERN.fullmatch(normalized):
            raise ValueError("Kubernetes resource names must be valid DNS labels")
        return normalized

    @field_validator(
        "promocodes_db_kube_context",
        "balance_db_kube_context",
        "stat_clickhouse_kube_context",
    )
    @classmethod
    def kubernetes_context_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("PROMOCODES_DB_KUBE_CONTEXT must not be blank")
        return normalized

    @field_validator(
        "promocodes_db_kubectl_path",
        "balance_db_kubectl_path",
        "stat_clickhouse_kubectl_path",
    )
    @classmethod
    def kubectl_path_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("PROMOCODES_DB_KUBECTL_PATH must not be blank")
        return normalized

    @property
    def timeout_seconds(self) -> float:
        return self.api_test_timeout.total_seconds()

    @property
    def db_connect_timeout_seconds(self) -> int:
        return max(1, int(self.promocodes_db_connect_timeout.total_seconds()))

    @property
    def balance_db_connect_timeout_seconds(self) -> int:
        return max(1, int(self.balance_db_connect_timeout.total_seconds()))

    @property
    def stat_clickhouse_connect_timeout_seconds(self) -> float:
        return self.stat_clickhouse_connect_timeout.total_seconds()

    @property
    def db_kube_start_timeout_seconds(self) -> float:
        return self.promocodes_db_kube_start_timeout.total_seconds()

    @property
    def user_bearer_token(self) -> str | None:
        return self._normalized_token(self.api_bearer_token or self.promocodes_bearer_token)

    @property
    def admin_bearer_token(self) -> str | None:
        return self._normalized_token(
            self.api_admin_bearer_token or self.promocodes_admin_bearer_token
        )

    @property
    def social_peer_token(self) -> str | None:
        return self._normalized_token(self.social_peer_bearer_token)

    @property
    def profile_share_token(self) -> str | None:
        return self._normalized_token(self.profile_share_bearer_token)

    @property
    def ads_applovin_event_key_value(self) -> str | None:
        if self.ads_applovin_event_key is None:
            return None
        value = self.ads_applovin_event_key.get_secret_value().strip()
        return value or None

    @staticmethod
    def _normalized_token(secret: SecretStr | None) -> str | None:
        if secret is None:
            return None
        token = secret.get_secret_value().strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        return token or None

    def missing_api_configuration(self) -> list[str]:
        missing: list[str] = []
        if self.promocodes_base_url is None:
            missing.append("PROMOCODES_BASE_URL")
        if self.promocodes_api_path is None:
            missing.append("PROMOCODES_API_PATH")
        if self.user_bearer_token is None:
            missing.append("PROMOCODES_BEARER_TOKEN")
        return missing

    def missing_admin_api_configuration(self) -> list[str]:
        missing: list[str] = []
        if self.promocodes_base_url is None:
            missing.append("PROMOCODES_BASE_URL")
        if self.promocodes_api_path is None:
            missing.append("PROMOCODES_API_PATH")
        if self.admin_bearer_token is None:
            missing.append("PROMOCODES_ADMIN_BEARER_TOKEN")
        return missing

    def missing_balance_api_configuration(self) -> list[str]:
        missing: list[str] = []
        if self.balance_base_url is None:
            missing.append("BALANCE_BASE_URL")
        if self.balance_api_path is None:
            missing.append("BALANCE_API_PATH")
        if self.user_bearer_token is None:
            missing.append("API_BEARER_TOKEN")
        return missing

    def missing_balance_admin_api_configuration(self) -> list[str]:
        missing = self.missing_balance_api_configuration()
        if self.admin_bearer_token is None:
            missing.append("API_ADMIN_BEARER_TOKEN")
        return missing

    def missing_market_proxy_api_configuration(self) -> list[str]:
        missing: list[str] = []
        if self.market_proxy_base_url is None:
            missing.append("MARKET_PROXY_BASE_URL")
        if self.market_proxy_api_path is None:
            missing.append("MARKET_PROXY_API_PATH")
        if self.user_bearer_token is None:
            missing.append("API_BEARER_TOKEN")
        return missing

    def missing_social_api_configuration(self) -> list[str]:
        missing: list[str] = []
        if self.social_base_url is None:
            missing.append("SOCIAL_BASE_URL")
        if self.social_api_path is None:
            missing.append("SOCIAL_API_PATH")
        if self.user_bearer_token is None:
            missing.append("API_BEARER_TOKEN")
        return missing

    def missing_social_peer_configuration(self) -> list[str]:
        missing = self.missing_social_api_configuration()
        if self.social_peer_token is None:
            missing.append("SOCIAL_PEER_BEARER_TOKEN")
        return missing

    def missing_daily_quests_api_configuration(self) -> list[str]:
        missing: list[str] = []
        if self.daily_quests_base_url is None:
            missing.append("DAILY_QUESTS_BASE_URL")
        if self.daily_quests_api_path is None:
            missing.append("DAILY_QUESTS_API_PATH")
        if self.user_bearer_token is None:
            missing.append("API_BEARER_TOKEN")
        return missing

    def missing_battle_pass_api_configuration(self) -> list[str]:
        missing: list[str] = []
        if self.battle_pass_base_url is None:
            missing.append("BATTLE_PASS_BASE_URL")
        if self.battle_pass_api_path is None:
            missing.append("BATTLE_PASS_API_PATH")
        if self.user_bearer_token is None:
            missing.append("API_BEARER_TOKEN")
        return missing

    def missing_boosters_api_configuration(self) -> list[str]:
        return self._missing_service_configuration(
            "BOOSTERS", self.boosters_base_url, self.boosters_api_path
        )

    def missing_inventory_api_configuration(self) -> list[str]:
        missing = self._missing_service_configuration(
            "INVENTORY", self.inventory_base_url, self.inventory_api_path
        )
        if self.inventory_test_category is None:
            missing.append("INVENTORY_TEST_CATEGORY")
        if self.inventory_test_class is None:
            missing.append("INVENTORY_TEST_CLASS")
        return missing

    def missing_stat_api_configuration(self) -> list[str]:
        missing: list[str] = []
        if self.stat_api_base_url is None:
            missing.append("STAT_API_BASE_URL")
        if self.stat_api_path is None:
            missing.append("STAT_API_PATH")
        if self.user_bearer_token is None:
            missing.append("API_BEARER_TOKEN")
        return missing

    def missing_goods_api_configuration(self) -> list[str]:
        return self._missing_service_configuration(
            "GOODS", self.goods_base_url, self.goods_api_path
        )

    def missing_profile_api_configuration(self) -> list[str]:
        return self._missing_service_configuration(
            "PROFILE", self.profile_base_url, self.profile_api_path
        )

    def missing_lottery_api_configuration(self) -> list[str]:
        return self._missing_service_configuration(
            "LOTTERY", self.lottery_base_url, self.lottery_api_path
        )

    def missing_lottery_admin_configuration(self) -> list[str]:
        missing = self.missing_lottery_api_configuration()
        if self.admin_bearer_token is None:
            missing.append("API_ADMIN_BEARER_TOKEN")
        return missing

    def missing_lottery_opening_configuration(self) -> list[str]:
        missing = self.missing_lottery_api_configuration()
        missing.extend(self.missing_balance_admin_api_configuration())
        return list(dict.fromkeys(missing))

    def missing_ads_api_configuration(self) -> list[str]:
        return self._missing_service_configuration("ADS", self.ads_base_url, self.ads_api_path)

    def missing_ads_admin_configuration(self) -> list[str]:
        missing = self.missing_ads_api_configuration()
        if self.admin_bearer_token is None:
            missing.append("API_ADMIN_BEARER_TOKEN")
        return missing

    def missing_ads_callback_configuration(self) -> list[str]:
        missing = self.missing_ads_admin_configuration()
        missing.extend(self.missing_balance_api_configuration())
        if self.ads_applovin_event_key_value is None:
            missing.append("ADS_APPLOVIN_EVENT_KEY")
        return list(dict.fromkeys(missing))

    def missing_booster_grant_configuration(self) -> list[str]:
        missing = self.missing_boosters_api_configuration()
        missing.extend(self.missing_goods_api_configuration())
        if self.admin_bearer_token is None:
            missing.append("API_ADMIN_BEARER_TOKEN")
        if self.booster_test_goods_uuid is None:
            missing.append("BOOSTER_TEST_GOODS_UUID")
        return list(dict.fromkeys(missing))

    def missing_inventory_grant_configuration(self) -> list[str]:
        missing = self.missing_inventory_api_configuration()
        missing.extend(self.missing_goods_api_configuration())
        if self.admin_bearer_token is None:
            missing.append("API_ADMIN_BEARER_TOKEN")
        if self.inventory_test_goods_uuid is None:
            missing.append("INVENTORY_TEST_GOODS_UUID")
        return list(dict.fromkeys(missing))

    def missing_premium_grant_configuration(self) -> list[str]:
        missing = self.missing_goods_api_configuration()
        missing.extend(self.missing_profile_api_configuration())
        if self.admin_bearer_token is None:
            missing.append("API_ADMIN_BEARER_TOKEN")
        if self.premium_test_goods_uuid is None:
            missing.append("PREMIUM_TEST_GOODS_UUID")
        return list(dict.fromkeys(missing))

    def _missing_service_configuration(
        self,
        service: str,
        base_url: AnyHttpUrl | None,
        api_path: str | None,
    ) -> list[str]:
        missing: list[str] = []
        if base_url is None:
            missing.append(f"{service}_BASE_URL")
        if api_path is None:
            missing.append(f"{service}_API_PATH")
        if self.user_bearer_token is None:
            missing.append("API_BEARER_TOKEN")
        return missing

    def missing_database_configuration(self) -> list[str]:
        required = {
            "PROMOCODES_DB_HOST": self.promocodes_db_host,
            "PROMOCODES_DB_NAME": self.promocodes_db_name,
            "PROMOCODES_DB_USER": self.promocodes_db_user,
            "PROMOCODES_DB_PASSWORD": self.promocodes_db_password,
        }
        return [name for name, value in required.items() if value is None]

    def missing_kubernetes_database_configuration(self) -> list[str]:
        required = {
            "PROMOCODES_DB_KUBE_CONTEXT": self.promocodes_db_kube_context,
            "PROMOCODES_DB_KUBE_NAMESPACE": self.promocodes_db_kube_namespace,
            "PROMOCODES_DB_KUBE_SERVICE": self.promocodes_db_kube_service,
            "PROMOCODES_DB_KUBE_DEPLOYMENT": self.promocodes_db_kube_deployment,
            "PROMOCODES_DB_KUBE_CONTAINER": self.promocodes_db_kube_container,
        }
        return [name for name, value in required.items() if value is None]

    def missing_balance_database_configuration(self) -> list[str]:
        required = {
            "BALANCE_DB_HOST": self.balance_db_host,
            "BALANCE_DB_NAME": self.balance_db_name,
            "BALANCE_DB_USER": self.balance_db_user,
            "BALANCE_DB_PASSWORD": self.balance_db_password,
        }
        return [name for name, value in required.items() if value is None]

    def missing_balance_kubernetes_database_configuration(self) -> list[str]:
        required = {
            "BALANCE_DB_KUBE_CONTEXT": self.balance_db_kube_context,
            "BALANCE_DB_KUBE_NAMESPACE": self.balance_db_kube_namespace,
            "BALANCE_DB_KUBE_SERVICE": self.balance_db_kube_service,
            "BALANCE_DB_KUBE_DEPLOYMENT": self.balance_db_kube_deployment,
            "BALANCE_DB_KUBE_CONTAINER": self.balance_db_kube_container,
        }
        return [name for name, value in required.items() if value is None]

    def missing_stat_clickhouse_configuration(self) -> list[str]:
        required = {
            "STAT_CLICKHOUSE_HOST": self.stat_clickhouse_host,
            "STAT_CLICKHOUSE_DATABASE": self.stat_clickhouse_database,
            "STAT_CLICKHOUSE_USER": self.stat_clickhouse_user,
            "STAT_CLICKHOUSE_PASSWORD": self.stat_clickhouse_password,
        }
        return [name for name, value in required.items() if value is None]

    def missing_stat_clickhouse_kubernetes_configuration(self) -> list[str]:
        required = {
            "STAT_CLICKHOUSE_KUBE_CONTEXT": self.stat_clickhouse_kube_context,
            "STAT_CLICKHOUSE_KUBE_SERVICE_NAMESPACE": (self.stat_clickhouse_kube_service_namespace),
            "STAT_CLICKHOUSE_KUBE_SERVICE": self.stat_clickhouse_kube_service,
            "STAT_CLICKHOUSE_KUBE_DEPLOYMENT_NAMESPACE": (
                self.stat_clickhouse_kube_deployment_namespace
            ),
            "STAT_CLICKHOUSE_KUBE_DEPLOYMENT": self.stat_clickhouse_kube_deployment,
            "STAT_CLICKHOUSE_KUBE_CONTAINER": self.stat_clickhouse_kube_container,
        }
        return [name for name, value in required.items() if value is None]


def load_settings() -> Settings:
    configured_path = os.getenv("QA_ENV_FILE")
    env_file = Path(configured_path) if configured_path else Path.cwd() / ".env"
    selected_file: Path | None = env_file if env_file.is_file() else None
    return Settings(_env_file=selected_file, _env_file_encoding="utf-8")
