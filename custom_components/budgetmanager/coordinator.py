"""Polls the Budget Manager server for the current month's figures."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import BudgetManagerApi, BudgetManagerAuthError, BudgetManagerError
from .const import CONF_REFRESH_TOKEN, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type BudgetManagerConfigEntry = ConfigEntry[BudgetManagerCoordinator]


@dataclass
class BudgetManagerData:
    #: ``/api/summary/``: the month going on today and its figures.
    summary: dict[str, Any]
    #: ``/api/statistics/``: per-month sums, oldest month first.
    statistics: dict[str, Any]

    @property
    def has_month(self) -> bool:
        return self.summary.get("month") is not None

    @property
    def currency(self) -> str:
        return self.summary.get("currency", "PLN")

    @property
    def categories(self) -> list[dict[str, Any]]:
        return self.summary.get("categories", [])


class BudgetManagerCoordinator(DataUpdateCoordinator[BudgetManagerData]):
    config_entry: BudgetManagerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BudgetManagerConfigEntry,
        api: BudgetManagerApi,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api

    @callback
    def persist_refresh_token(self, token: str) -> None:
        """Keep the rotated refresh token; the previous one is now blacklisted."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, CONF_REFRESH_TOKEN: token},
        )

    async def _async_update_data(self) -> BudgetManagerData:
        try:
            summary = await self.api.get_summary()
            statistics = await self.api.get_statistics()
        except BudgetManagerAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BudgetManagerError as err:
            raise UpdateFailed(str(err)) from err
        return BudgetManagerData(summary=summary, statistics=statistics)
