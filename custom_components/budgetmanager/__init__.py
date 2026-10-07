"""The Budget Manager integration."""
from __future__ import annotations

from homeassistant.const import CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import BudgetManagerApi
from .const import CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import BudgetManagerConfigEntry, BudgetManagerCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: BudgetManagerConfigEntry
) -> bool:
    session = async_get_clientsession(hass, entry.data.get(CONF_VERIFY_SSL, True))
    api = BudgetManagerApi(
        session, entry.data[CONF_URL], entry.data[CONF_REFRESH_TOKEN])
    coordinator = BudgetManagerCoordinator(hass, entry, api)
    api.set_refresh_token_listener(coordinator.persist_refresh_token)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_entry_updated(
    hass: HomeAssistant, entry: BudgetManagerConfigEntry
) -> None:
    entry.runtime_data.apply_options()


async def async_unload_entry(
    hass: HomeAssistant, entry: BudgetManagerConfigEntry
) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
