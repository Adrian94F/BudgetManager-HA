"""Fixtures for Budget Manager tests."""
from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from custom_components.budgetmanager.const import CONF_REFRESH_TOKEN, DOMAIN

SUMMARY: dict[str, Any] = {
    "month": {"id": 7, "start_date": "2026-10-01", "end_date": "2026-10-30"},
    "currency": "PLN",
    "is_actual": True,
    "days_total": 30,
    "days_left": 24,
    "salaries": 6000.0,
    "other_incomes": 0.0,
    "all_incomes": 6000.0,
    "monthly_expenses": 2000.0,
    "daily_expenses": 55.0,
    "all_expenses": 2055.0,
    "incomes_for_daily_expenses": 4000.0,
    "planned_savings": 300.0,
    "actual_balance": 3945.0,
    "balance": 3645.0,
    "is_over_budget": False,
    "max_daily": 151.88,
    "today_spendings": 55.0,
    "today_percent": 36,
    "categories": [
        {"id": 1, "name": "Food", "sum": 55.0},
        {"id": 2, "name": "Rent", "sum": 2000.0},
    ],
    "last_expense": {
        "id": 3, "value": 55.0, "date": "2026-10-07", "comment": "Lunch",
        "category": 1, "is_monthly": False,
    },
}

STATISTICS: dict[str, Any] = {
    "incomeSums": [5800.0, 6000.0],
    "expenseSums": [5000.0, 2055.0],
    "balances": [800.0, 3945.0],
    "labels": ["1.09-30.09.2026", "1.10-30.10.2026"],
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Budget Manager (alice)",
        unique_id="http://bm.local|alice",
        data={
            CONF_URL: "http://bm.local",
            CONF_USERNAME: "alice",
            CONF_VERIFY_SSL: True,
            CONF_REFRESH_TOKEN: "refresh-1",
        },
    )


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """The API client used by the set-up entry, answering with SUMMARY."""
    with patch(
        "custom_components.budgetmanager.BudgetManagerApi", autospec=True
    ) as api_class:
        api = api_class.return_value
        api.get_summary.return_value = deepcopy(SUMMARY)
        api.get_statistics.return_value = deepcopy(STATISTICS)
        yield api


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
