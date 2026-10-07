"""Planned savings, editable from Home Assistant."""
from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import BudgetManagerError
from .coordinator import BudgetManagerConfigEntry, BudgetManagerCoordinator
from .entity import BudgetManagerEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BudgetManagerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([PlannedSavingsNumber(entry.runtime_data)])


class PlannedSavingsNumber(BudgetManagerEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.MONETARY
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 1_000_000
    _attr_native_step = 0.01
    _attr_translation_key = "planned_savings"

    def __init__(self, coordinator: BudgetManagerCoordinator) -> None:
        super().__init__(coordinator, "planned_savings")

    @property
    def available(self) -> bool:
        # The summary reports the user's planned savings only for the month
        # going on; for any other it is 0 and says nothing about the setting.
        return super().available and bool(
            self.coordinator.data.summary.get("is_actual"))

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.summary.get("planned_savings")

    @property
    def native_unit_of_measurement(self) -> str:
        return self.coordinator.data.currency

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.api.set_planned_savings(value)
        except BudgetManagerError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
