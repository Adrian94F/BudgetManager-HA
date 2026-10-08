"""Sensors with the current month's figures, as the Summary page shows them."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from statistics import mean
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    BudgetManagerConfigEntry,
    BudgetManagerCoordinator,
    BudgetManagerData,
)
from .entity import BudgetManagerEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BudgetManagerSensorDescription(SensorEntityDescription):
    value_fn: Callable[[BudgetManagerData], Any]
    attrs_fn: Callable[[BudgetManagerData], dict[str, Any] | None] = lambda _: None
    #: Amounts take their unit from the user's currency on the server.
    monetary: bool = False


def _summary(key: str) -> Callable[[BudgetManagerData], Any]:
    return lambda data: data.summary.get(key)


def _month_attrs(data: BudgetManagerData) -> dict[str, Any] | None:
    month = data.summary.get("month")
    if month is None:
        return None
    return {
        "month_id": month["id"],
        "start_date": month["start_date"],
        "end_date": month["end_date"],
        "is_actual": data.summary["is_actual"],
        "planned_savings": data.summary["planned_savings"],
        "balance_after_savings": data.summary["balance"],
    }


def _last_expense_attrs(data: BudgetManagerData) -> dict[str, Any] | None:
    expense = data.summary.get("last_expense")
    if expense is None:
        return None
    names = {c["id"]: c["name"] for c in data.categories}
    return {
        "date": expense["date"],
        "category": names.get(expense["category"]),
        "comment": expense["comment"],
        "is_monthly": expense["is_monthly"],
    }


def _history_value(data: BudgetManagerData) -> float | None:
    balances = data.statistics.get("balances") or []
    return round(mean(float(b) for b in balances), 2) if balances else None


def _history_attrs(data: BudgetManagerData) -> dict[str, Any]:
    # For charts, e.g. apexcharts-card's data_generator.
    return {
        "labels": data.statistics.get("labels", []),
        "incomes": data.statistics.get("incomeSums", []),
        "expenses": data.statistics.get("expenseSums", []),
        "balances": data.statistics.get("balances", []),
    }


SENSORS: tuple[BudgetManagerSensorDescription, ...] = (
    BudgetManagerSensorDescription(
        key="balance",
        translation_key="balance",
        monetary=True,
        state_class=SensorStateClass.TOTAL,
        # Planned savings can still change, so the state leaves them out.
        value_fn=_summary("actual_balance"),
        attrs_fn=_month_attrs,
    ),
    BudgetManagerSensorDescription(
        key="max_daily",
        translation_key="max_daily",
        monetary=True,
        state_class=SensorStateClass.TOTAL,
        value_fn=_summary("max_daily"),
    ),
    BudgetManagerSensorDescription(
        key="today_spendings",
        translation_key="today_spendings",
        monetary=True,
        value_fn=_summary("today_spendings"),
    ),
    BudgetManagerSensorDescription(
        key="today_percent",
        translation_key="today_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_summary("today_percent"),
    ),
    BudgetManagerSensorDescription(
        key="days_left",
        translation_key="days_left",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=_summary("days_left"),
    ),
    BudgetManagerSensorDescription(
        key="all_incomes",
        translation_key="all_incomes",
        monetary=True,
        value_fn=_summary("all_incomes"),
    ),
    BudgetManagerSensorDescription(
        key="all_expenses",
        translation_key="all_expenses",
        monetary=True,
        value_fn=_summary("all_expenses"),
    ),
    BudgetManagerSensorDescription(
        key="monthly_expenses",
        translation_key="monthly_expenses",
        monetary=True,
        value_fn=_summary("monthly_expenses"),
    ),
    BudgetManagerSensorDescription(
        key="daily_expenses",
        translation_key="daily_expenses",
        monetary=True,
        value_fn=_summary("daily_expenses"),
    ),
    BudgetManagerSensorDescription(
        key="last_expense",
        translation_key="last_expense",
        monetary=True,
        value_fn=lambda data: (data.summary.get("last_expense") or {}).get("value"),
        attrs_fn=_last_expense_attrs,
    ),
    BudgetManagerSensorDescription(
        key="average_balance",
        translation_key="average_balance",
        monetary=True,
        value_fn=_history_value,
        attrs_fn=_history_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BudgetManagerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BudgetManagerSensor(coordinator, description) for description in SENSORS)

    # One sensor per expense category; categories added later on the server
    # get theirs on the next poll.
    known: set[int] = set()

    @callback
    def add_category_sensors() -> None:
        new = [c for c in coordinator.data.categories if c["id"] not in known]
        known.update(c["id"] for c in new)
        if new:
            async_add_entities(
                BudgetManagerCategorySensor(coordinator, c["id"]) for c in new)

    add_category_sensors()
    entry.async_on_unload(coordinator.async_add_listener(add_category_sensors))


class BudgetManagerSensor(BudgetManagerEntity, SensorEntity):
    entity_description: BudgetManagerSensorDescription

    def __init__(
        self,
        coordinator: BudgetManagerCoordinator,
        description: BudgetManagerSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if description.monetary:
            self._attr_device_class = SensorDeviceClass.MONETARY

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.monetary:
            return self.coordinator.data.currency
        return super().native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self.entity_description.attrs_fn(self.coordinator.data)


class BudgetManagerCategorySensor(BudgetManagerEntity, SensorEntity):
    """What the current month spent on one category."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_translation_key = "category"

    def __init__(
        self, coordinator: BudgetManagerCoordinator, category_id: int
    ) -> None:
        super().__init__(coordinator, f"category_{category_id}")
        self._category_id = category_id

    def _category(self) -> dict[str, Any] | None:
        return next(
            (c for c in self.coordinator.data.categories
             if c["id"] == self._category_id),
            None,
        )

    @property
    def available(self) -> bool:
        return super().available and self._category() is not None

    @property
    def translation_placeholders(self) -> dict[str, str]:
        category = self._category()
        return {"category": category["name"] if category else str(self._category_id)}

    @property
    def native_value(self) -> Any:
        category = self._category()
        return category["sum"] if category else None

    @property
    def native_unit_of_measurement(self) -> str:
        return self.coordinator.data.currency
