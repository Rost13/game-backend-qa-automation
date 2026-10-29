from __future__ import annotations

import allure
import pytest

from qa_automation.config import Settings
from qa_automation.db.promocodes import PromocodesDatabase

pytestmark = [pytest.mark.integration, pytest.mark.live, allure.feature("Promocodes database")]


@allure.title("Promocodes database connection is read-only and can read required tables")
@pytest.mark.smoke
def test_promocodes_database_connection_is_read_only(
    required_promo_database: PromocodesDatabase,
    promo_database_settings: Settings | None,
) -> None:
    assert promo_database_settings is not None
    assert required_promo_database.read_only_setting() == "on"
    assert required_promo_database.database_name() == promo_database_settings.promocodes_db_name
    assert required_promo_database.readable_tables() == {
        "promocodes": True,
        "promocode_applications": True,
    }
