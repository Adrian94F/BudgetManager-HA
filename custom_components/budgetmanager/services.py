"""Actions that add expenses and incomes to the month going on."""
from __future__ import annotations

from datetime import date

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .api import BudgetManagerError
from .const import (
    ATTR_CATEGORY,
    ATTR_COMMENT,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DATE,
    ATTR_IS_MONTHLY,
    ATTR_IS_SALARY,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_ADD_EXPENSE,
    SERVICE_ADD_INCOME,
)
from .coordinator import BudgetManagerConfigEntry, BudgetManagerCoordinator

_BASE_SCHEMA = {
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required(ATTR_VALUE): vol.All(vol.Coerce(float), vol.Range(min=0.01)),
    vol.Optional(ATTR_DATE): cv.date,
    vol.Optional(ATTR_COMMENT): cv.string,
}

ADD_EXPENSE_SCHEMA = vol.Schema({
    **_BASE_SCHEMA,
    vol.Required(ATTR_CATEGORY): cv.string,
    vol.Optional(ATTR_IS_MONTHLY, default=False): cv.boolean,
})

ADD_INCOME_SCHEMA = vol.Schema({
    **_BASE_SCHEMA,
    vol.Optional(ATTR_IS_SALARY, default=False): cv.boolean,
})


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> BudgetManagerCoordinator:
    """The account to act on: the one named, or the only one set up."""
    entries: list[BudgetManagerConfigEntry] = [
        entry for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    if entry_id:
        entries = [entry for entry in entries if entry.entry_id == entry_id]
    if len(entries) != 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_single_account",
        )
    return entries[0].runtime_data


def _month_id(coordinator: BudgetManagerCoordinator, entry_date: date) -> int:
    month = coordinator.data.summary.get("month")
    if month is None or not (
        month["start_date"] <= entry_date.isoformat() <= month["end_date"]
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="date_outside_month",
            translation_placeholders={"date": entry_date.isoformat()},
        )
    return month["id"]


def _category_id(coordinator: BudgetManagerCoordinator, category: str) -> int:
    """A category given by name (case-insensitive) or by id."""
    for c in coordinator.data.categories:
        if c["name"].casefold() == category.casefold() or str(c["id"]) == category:
            return c["id"]
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="unknown_category",
        translation_placeholders={"category": category},
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def add_expense(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        entry_date = call.data.get(ATTR_DATE) or dt_util.now().date()
        try:
            await coordinator.api.add_expense(
                month_id=_month_id(coordinator, entry_date),
                category_id=_category_id(coordinator, call.data[ATTR_CATEGORY]),
                value=call.data[ATTR_VALUE],
                expense_date=entry_date,
                comment=call.data.get(ATTR_COMMENT),
                is_monthly=call.data[ATTR_IS_MONTHLY],
            )
        except BudgetManagerError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def add_income(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        entry_date = call.data.get(ATTR_DATE) or dt_util.now().date()
        try:
            await coordinator.api.add_income(
                month_id=_month_id(coordinator, entry_date),
                value=call.data[ATTR_VALUE],
                income_date=entry_date,
                comment=call.data.get(ATTR_COMMENT),
                is_salary=call.data[ATTR_IS_SALARY],
            )
        except BudgetManagerError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_EXPENSE, add_expense, schema=ADD_EXPENSE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_INCOME, add_income, schema=ADD_INCOME_SCHEMA)
