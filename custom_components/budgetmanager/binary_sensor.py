"""Binary sensors for budget alerts and the server connection."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    BudgetManagerConfigEntry,
    BudgetManagerCoordinator,
    BudgetManagerData,
)
from .entity import BudgetManagerEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BudgetManagerBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[BudgetManagerData], bool | None]


def _daily_limit_exceeded(data: BudgetManagerData) -> bool | None:
    percent = data.summary.get("today_percent")
    return None if percent is None else percent > 100


BINARY_SENSORS: tuple[BudgetManagerBinarySensorDescription, ...] = (
    BudgetManagerBinarySensorDescription(
        key="over_budget",
        translation_key="over_budget",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.summary.get("is_over_budget"),
    ),
    BudgetManagerBinarySensorDescription(
        key="daily_limit_exceeded",
        translation_key="daily_limit_exceeded",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_daily_limit_exceeded,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BudgetManagerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([
        *(BudgetManagerBinarySensor(coordinator, d) for d in BINARY_SENSORS),
        BudgetManagerConnectivitySensor(coordinator),
    ])


class BudgetManagerBinarySensor(BudgetManagerEntity, BinarySensorEntity):
    entity_description: BudgetManagerBinarySensorDescription

    def __init__(
        self,
        coordinator: BudgetManagerCoordinator,
        description: BudgetManagerBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)


class BudgetManagerConnectivitySensor(BudgetManagerEntity, BinarySensorEntity):
    """Whether the last poll reached the server; stays available when it did not."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "server"

    def __init__(self, coordinator: BudgetManagerCoordinator) -> None:
        super().__init__(coordinator, "server")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success
