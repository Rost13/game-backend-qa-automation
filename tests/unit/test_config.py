from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from qa_automation.config import Settings


def test_settings_accept_bearer_prefix_without_duplicating_it() -> None:
    settings = Settings(
        _env_file=None,
        promocodes_bearer_token="Bearer secret-value",
        promocodes_admin_bearer_token="Bearer admin-secret-value",
    )

    assert settings.user_bearer_token == "secret-value"
    assert settings.admin_bearer_token == "admin-secret-value"
    assert "secret-value" not in repr(settings)
    assert "admin-secret-value" not in repr(settings)


def test_settings_report_missing_live_api_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_api_configuration() == [
        "PROMOCODES_BASE_URL",
        "PROMOCODES_API_PATH",
        "PROMOCODES_BEARER_TOKEN",
    ]


def test_settings_reject_relative_api_path() -> None:
    with pytest.raises(ValidationError, match="must start with"):
        Settings(_env_file=None, promocodes_api_path="api/v2/promo")


def test_settings_parse_positive_durations() -> None:
    settings = Settings(
        _env_file=None,
        api_test_timeout="20s",
        balance_event_timeout="15s",
        market_proxy_purchase_timeout="90s",
        social_event_timeout="25s",
        daily_quests_event_timeout="30s",
        battle_pass_event_timeout="35s",
        reward_delivery_timeout="40s",
        lottery_event_timeout="45s",
        ads_event_timeout="50s",
        promocodes_db_connect_timeout="10s",
    )

    assert settings.api_test_timeout == timedelta(seconds=20)
    assert settings.balance_event_timeout == timedelta(seconds=15)
    assert settings.market_proxy_purchase_timeout == timedelta(seconds=90)
    assert settings.social_event_timeout == timedelta(seconds=25)
    assert settings.daily_quests_event_timeout == timedelta(seconds=30)
    assert settings.battle_pass_event_timeout == timedelta(seconds=35)
    assert settings.reward_delivery_timeout == timedelta(seconds=40)
    assert settings.lottery_event_timeout == timedelta(seconds=45)
    assert settings.ads_event_timeout == timedelta(seconds=50)
    assert settings.db_connect_timeout_seconds == 10


def test_settings_report_missing_kubernetes_database_values() -> None:
    settings = Settings(_env_file=None, promocodes_db_kube_forward_enabled=True)

    assert settings.missing_kubernetes_database_configuration() == [
        "PROMOCODES_DB_KUBE_CONTEXT",
        "PROMOCODES_DB_KUBE_NAMESPACE",
        "PROMOCODES_DB_KUBE_SERVICE",
        "PROMOCODES_DB_KUBE_DEPLOYMENT",
        "PROMOCODES_DB_KUBE_CONTAINER",
    ]
    assert settings.promocodes_db_kube_container is None


def test_settings_reject_invalid_kubernetes_resource_name() -> None:
    with pytest.raises(ValidationError, match="valid DNS labels"):
        Settings(_env_file=None, promocodes_db_kube_namespace="unity/dev")


def test_generic_api_tokens_take_priority_for_all_services() -> None:
    settings = Settings(
        _env_file=None,
        api_bearer_token="shared-user-token",
        api_admin_bearer_token="shared-admin-token",
        promocodes_bearer_token="legacy-user-token",
        promocodes_admin_bearer_token="legacy-admin-token",
    )

    assert settings.user_bearer_token == "shared-user-token"
    assert settings.admin_bearer_token == "shared-admin-token"


def test_settings_report_missing_balance_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_balance_api_configuration() == [
        "BALANCE_BASE_URL",
        "BALANCE_API_PATH",
        "API_BEARER_TOKEN",
    ]


def test_settings_reject_non_positive_balance_replenish_amount() -> None:
    with pytest.raises(ValidationError, match="BALANCE_REPLENISH_AMOUNT must be positive"):
        Settings(_env_file=None, balance_replenish_amount=0)


def test_settings_report_missing_balance_database_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_balance_database_configuration() == [
        "BALANCE_DB_HOST",
        "BALANCE_DB_NAME",
        "BALANCE_DB_USER",
        "BALANCE_DB_PASSWORD",
    ]
    assert settings.missing_balance_kubernetes_database_configuration() == [
        "BALANCE_DB_KUBE_CONTEXT",
        "BALANCE_DB_KUBE_NAMESPACE",
        "BALANCE_DB_KUBE_SERVICE",
        "BALANCE_DB_KUBE_DEPLOYMENT",
        "BALANCE_DB_KUBE_CONTAINER",
    ]
    assert settings.balance_db_kube_container is None


def test_settings_reject_invalid_balance_kubernetes_resource_name() -> None:
    with pytest.raises(ValidationError, match="valid DNS labels"):
        Settings(_env_file=None, balance_db_kube_deployment="balance/dev")


def test_settings_report_missing_market_proxy_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_market_proxy_api_configuration() == [
        "MARKET_PROXY_BASE_URL",
        "MARKET_PROXY_API_PATH",
        "API_BEARER_TOKEN",
    ]


def test_settings_report_missing_social_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_social_api_configuration() == [
        "SOCIAL_BASE_URL",
        "SOCIAL_API_PATH",
        "API_BEARER_TOKEN",
    ]
    assert settings.missing_social_peer_configuration() == [
        "SOCIAL_BASE_URL",
        "SOCIAL_API_PATH",
        "API_BEARER_TOKEN",
        "SOCIAL_PEER_BEARER_TOKEN",
    ]


def test_settings_normalize_social_peer_token_without_exposing_it() -> None:
    settings = Settings(_env_file=None, social_peer_bearer_token="Bearer peer-secret")

    assert settings.social_peer_token == "peer-secret"
    assert "peer-secret" not in repr(settings)


def test_settings_report_missing_daily_quests_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_daily_quests_api_configuration() == [
        "DAILY_QUESTS_BASE_URL",
        "DAILY_QUESTS_API_PATH",
        "API_BEARER_TOKEN",
    ]


def test_settings_reject_relative_daily_quests_api_path() -> None:
    with pytest.raises(ValidationError, match="must start with"):
        Settings(_env_file=None, daily_quests_api_path="api/v2/daily-quests")


def test_settings_report_missing_battle_pass_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_battle_pass_api_configuration() == [
        "BATTLE_PASS_BASE_URL",
        "BATTLE_PASS_API_PATH",
        "API_BEARER_TOKEN",
    ]


def test_settings_reject_invalid_battle_pass_values() -> None:
    with pytest.raises(ValidationError, match="must start with"):
        Settings(_env_file=None, battle_pass_api_path="api/v2/battlepass")
    with pytest.raises(ValidationError, match="BATTLE_PASS_TEST_XP_AMOUNT must be positive"):
        Settings(_env_file=None, battle_pass_test_xp_amount=0)


def test_settings_report_missing_boosters_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_boosters_api_configuration() == [
        "BOOSTERS_BASE_URL",
        "BOOSTERS_API_PATH",
        "API_BEARER_TOKEN",
    ]


def test_settings_report_missing_inventory_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_inventory_api_configuration() == [
        "INVENTORY_BASE_URL",
        "INVENTORY_API_PATH",
        "API_BEARER_TOKEN",
        "INVENTORY_TEST_CATEGORY",
        "INVENTORY_TEST_CLASS",
    ]


def test_settings_report_missing_goods_and_profile_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_goods_api_configuration() == [
        "GOODS_BASE_URL",
        "GOODS_API_PATH",
        "API_BEARER_TOKEN",
    ]
    assert settings.missing_profile_api_configuration() == [
        "PROFILE_BASE_URL",
        "PROFILE_API_PATH",
        "API_BEARER_TOKEN",
    ]
    assert settings.profile_mutations_enabled is False
    assert settings.profile_share_token is None
    assert settings.destructive_rbac_tests_enabled is False
    assert settings.rbac_disposable_account_uuid is None


def test_settings_report_missing_lottery_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_lottery_api_configuration() == [
        "LOTTERY_BASE_URL",
        "LOTTERY_API_PATH",
        "API_BEARER_TOKEN",
    ]
    assert settings.missing_lottery_admin_configuration() == [
        "LOTTERY_BASE_URL",
        "LOTTERY_API_PATH",
        "API_BEARER_TOKEN",
        "API_ADMIN_BEARER_TOKEN",
    ]
    assert settings.lottery_openings_enabled is False
    assert settings.lottery_keys_topup_enabled is False
    assert settings.lottery_config_mutations_enabled is False


def test_settings_reject_relative_lottery_path_and_non_positive_timeout() -> None:
    with pytest.raises(ValidationError, match="must start with"):
        Settings(_env_file=None, lottery_api_path="api/v2/lottery")
    with pytest.raises(ValidationError, match="duration must be positive"):
        Settings(_env_file=None, lottery_event_timeout="0s")


def test_settings_report_missing_ads_values_and_normalize_callback_secret() -> None:
    settings = Settings(_env_file=None, ads_applovin_event_key=" event-secret ")

    assert settings.missing_ads_api_configuration() == [
        "ADS_BASE_URL",
        "ADS_API_PATH",
        "API_BEARER_TOKEN",
    ]
    assert settings.missing_ads_admin_configuration() == [
        "ADS_BASE_URL",
        "ADS_API_PATH",
        "API_BEARER_TOKEN",
        "API_ADMIN_BEARER_TOKEN",
    ]
    assert settings.ads_applovin_event_key_value == "event-secret"
    assert "event-secret" not in repr(settings)
    assert settings.ads_starts_enabled is False
    assert settings.ads_admin_mutations_enabled is False
    assert settings.ads_callbacks_enabled is False


def test_settings_reject_relative_ads_path_and_non_positive_timeout() -> None:
    with pytest.raises(ValidationError, match="must start with"):
        Settings(_env_file=None, ads_api_path="api/v2/ads")
    with pytest.raises(ValidationError, match="duration must be positive"):
        Settings(_env_file=None, ads_event_timeout="0s")


def test_settings_validate_integration_goods_uuids() -> None:
    with pytest.raises(ValidationError, match="valid UUID"):
        Settings(_env_file=None, booster_test_goods_uuid="not-a-uuid")


def test_settings_report_missing_stat_api_and_clickhouse_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_stat_api_configuration() == [
        "STAT_API_BASE_URL",
        "STAT_API_PATH",
        "API_BEARER_TOKEN",
    ]
    assert settings.missing_stat_clickhouse_configuration() == [
        "STAT_CLICKHOUSE_HOST",
        "STAT_CLICKHOUSE_DATABASE",
        "STAT_CLICKHOUSE_USER",
        "STAT_CLICKHOUSE_PASSWORD",
    ]


def test_settings_report_missing_stat_clickhouse_kubernetes_values() -> None:
    settings = Settings(_env_file=None)

    assert settings.missing_stat_clickhouse_kubernetes_configuration() == [
        "STAT_CLICKHOUSE_KUBE_CONTEXT",
        "STAT_CLICKHOUSE_KUBE_SERVICE_NAMESPACE",
        "STAT_CLICKHOUSE_KUBE_SERVICE",
        "STAT_CLICKHOUSE_KUBE_DEPLOYMENT_NAMESPACE",
        "STAT_CLICKHOUSE_KUBE_DEPLOYMENT",
        "STAT_CLICKHOUSE_KUBE_CONTAINER",
    ]
    assert settings.stat_clickhouse_kube_service_namespace is None
    assert settings.stat_clickhouse_kube_service is None
    assert settings.stat_clickhouse_kube_deployment_namespace is None
    assert settings.stat_clickhouse_kube_deployment is None
    assert settings.stat_clickhouse_kube_container is None


def test_settings_reject_invalid_stat_clickhouse_values() -> None:
    with pytest.raises(ValidationError, match="must start with"):
        Settings(_env_file=None, stat_api_path="api/v2/stat")
    with pytest.raises(ValidationError, match="valid DNS labels"):
        Settings(_env_file=None, stat_clickhouse_kube_service="clickhouse/dev")
