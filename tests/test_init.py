"""Tests for setting up Budget Manager and its entities and actions."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.budgetmanager.api import (
    BudgetManagerAuthError,
    BudgetManagerError,
)
from custom_components.budgetmanager.const import CONF_REFRESH_TOKEN, DOMAIN

from .conftest import SUMMARY, setup_integration

PREFIX = "budget_manager_alice"


async def test_sensors(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, config_entry)

    balance = hass.states.get(f"sensor.{PREFIX}_balance")
    assert balance.state == "3945.0"
    assert balance.attributes["balance_after_savings"] == 3645.0
    assert balance.attributes["unit_of_measurement"] == "PLN"
    assert balance.attributes["month_id"] == 7
    assert hass.states.get(f"sensor.{PREFIX}_daily_allowance").state == "151.88"
    assert hass.states.get(f"sensor.{PREFIX}_daily_allowance_used").state == "36"
    assert hass.states.get(f"sensor.{PREFIX}_days_left").state == "24"

    last = hass.states.get(f"sensor.{PREFIX}_last_expense")
    assert last.state == "55.0"
    assert last.attributes["category"] == "Food"
    assert last.attributes["comment"] == "Lunch"

    average = hass.states.get(f"sensor.{PREFIX}_average_monthly_balance")
    assert average.state == "2372.5"
    assert average.attributes["balances"] == [800.0, 3945.0]

    assert hass.states.get(f"sensor.{PREFIX}_spent_on_food").state == "55.0"
    assert hass.states.get(f"sensor.{PREFIX}_spent_on_rent").state == "2000.0"


async def test_binary_sensors(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, config_entry)
    assert hass.states.get(f"binary_sensor.{PREFIX}_over_budget").state == "off"
    assert hass.states.get(
        f"binary_sensor.{PREFIX}_daily_allowance_exceeded").state == "off"
    assert hass.states.get(f"binary_sensor.{PREFIX}_server").state == "on"


async def test_new_category_gets_a_sensor(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, config_entry)
    summary = deepcopy(SUMMARY)
    summary["categories"].append({"id": 3, "name": "Fun", "sum": 12.0})
    mock_api.get_summary.return_value = summary

    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{PREFIX}_spent_on_fun").state == "12.0"


async def test_no_month_yet(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    mock_api.get_summary.return_value = {"month": None, "currency": "PLN"}
    await setup_integration(hass, config_entry)
    assert hass.states.get(f"sensor.{PREFIX}_balance").state == "unknown"
    assert hass.states.get(
        f"number.{PREFIX}_planned_savings").state == "unavailable"


async def test_set_planned_savings(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, config_entry)
    entity_id = f"number.{PREFIX}_planned_savings"
    assert hass.states.get(entity_id).state == "300.0"

    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": 450},
        blocking=True)

    mock_api.set_planned_savings.assert_awaited_once_with(450.0)


async def test_add_expense(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, config_entry)
    calls_before = mock_api.get_summary.await_count

    await hass.services.async_call(
        DOMAIN, "add_expense",
        {"value": 42.5, "category": "food", "comment": "Pizza",
         "date": "2026-10-08"},
        blocking=True)

    mock_api.add_expense.assert_awaited_once_with(
        month_id=7, category_id=1, value=42.5, expense_date=date(2026, 10, 8),
        comment="Pizza", is_monthly=False)
    await hass.async_block_till_done()
    assert mock_api.get_summary.await_count > calls_before


async def test_add_income(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, config_entry)
    await hass.services.async_call(
        DOMAIN, "add_income",
        {"value": 6000, "is_salary": True, "date": "2026-10-10"},
        blocking=True)
    mock_api.add_income.assert_awaited_once_with(
        month_id=7, value=6000.0, income_date=date(2026, 10, 10),
        comment=None, is_salary=True)


@pytest.mark.parametrize(
    ("data", "translation_key"),
    [
        ({"value": 10, "category": "Cars", "date": "2026-10-08"},
         "unknown_category"),
        ({"value": 10, "category": "Food", "date": "2026-11-02"},
         "date_outside_month"),
        ({"value": 10, "category": "Food", "date": "2026-10-08",
          "config_entry_id": "nope"},
         "no_single_account"),
    ],
)
async def test_add_expense_validation(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry,
    data: dict, translation_key: str,
) -> None:
    await setup_integration(hass, config_entry)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "add_expense", data, blocking=True)
    assert err.value.translation_key == translation_key
    mock_api.add_expense.assert_not_awaited()


async def test_server_down_marks_entities_unavailable(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, config_entry)
    mock_api.get_summary.side_effect = BudgetManagerError("down")

    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{PREFIX}_balance").state == "unavailable"
    assert hass.states.get(f"binary_sensor.{PREFIX}_server").state == "off"


async def test_expired_token_starts_reauth(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    mock_api.get_summary.side_effect = BudgetManagerAuthError("expired")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]


async def test_rotated_refresh_token_is_persisted(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, config_entry)
    config_entry.runtime_data.persist_refresh_token("refresh-2")
    assert config_entry.data[CONF_REFRESH_TOKEN] == "refresh-2"


async def test_unload(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_scan_interval_from_options(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    assert coordinator.update_interval == timedelta(minutes=5)
    polls = mock_api.get_summary.await_count

    # a rotated refresh token updates the entry too, but doesn't poll
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_REFRESH_TOKEN: "refresh-2"})
    await hass.async_block_till_done()
    assert mock_api.get_summary.await_count == polls

    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_SCAN_INTERVAL: {"hours": 1, "minutes": 0, "seconds": 30}})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.update_interval == timedelta(hours=1, seconds=30)
    assert config_entry.state is ConfigEntryState.LOADED
