"""Config flow for Budget Manager.

Only the URL, the username and a refresh token are stored; the password is
used once to obtain the token pair and then forgotten.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import DurationSelector, DurationSelectorConfig

from .api import BudgetManagerApi, BudgetManagerAuthError, BudgetManagerError
from .const import CONF_REFRESH_TOKEN, DOMAIN, MIN_SCAN_INTERVAL
from .coordinator import scan_interval

_LOGGER = logging.getLogger(__name__)

DEFAULT_URL = "https://budget.frydmanski.cc"

USER_SCHEMA = vol.Schema({
    vol.Required(CONF_URL): str,
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_VERIFY_SSL, default=True): bool,
})

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})

OPTIONS_SCHEMA = vol.Schema({
    vol.Required(CONF_SCAN_INTERVAL): DurationSelector(
        DurationSelectorConfig(enable_day=False)),
})


def _as_duration(interval: timedelta) -> dict[str, int]:
    total = int(interval.total_seconds())
    return {
        "hours": total // 3600,
        "minutes": total % 3600 // 60,
        "seconds": total % 60,
    }


class BudgetManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return BudgetManagerOptionsFlow()

    async def _async_login(
        self, url: str, username: str, password: str, verify_ssl: bool
    ) -> tuple[str | None, dict[str, str]]:
        """The new refresh token, or the form errors."""
        api = BudgetManagerApi(
            async_get_clientsession(self.hass, verify_ssl), url)
        try:
            await api.login(username, password)
        except BudgetManagerAuthError:
            return None, {"base": "invalid_auth"}
        except BudgetManagerError:
            return None, {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error while logging in")
            return None, {"base": "unknown"}
        return api.refresh_token, {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            username = user_input[CONF_USERNAME]
            await self.async_set_unique_id(f"{url}|{username}".lower())
            self._abort_if_unique_id_configured()

            token, errors = await self._async_login(
                url, username, user_input[CONF_PASSWORD],
                user_input[CONF_VERIFY_SSL])
            if token:
                return self.async_create_entry(
                    title=f"Budget Manager ({username})",
                    data={
                        CONF_URL: url,
                        CONF_USERNAME: username,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                        CONF_REFRESH_TOKEN: token,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, user_input or {CONF_URL: DEFAULT_URL}),
            # hassfest forbids URLs in translation strings.
            description_placeholders={"example_url": DEFAULT_URL},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """The refresh token expired (7 days without a poll) or was revoked."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token, errors = await self._async_login(
                entry.data[CONF_URL], entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD], entry.data.get(CONF_VERIFY_SSL, True))
            if token:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_REFRESH_TOKEN: token})

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )


class BudgetManagerOptionsFlow(OptionsFlow):
    """How often the server is polled."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            interval = timedelta(**user_input[CONF_SCAN_INTERVAL])
            if interval < MIN_SCAN_INTERVAL:
                errors[CONF_SCAN_INTERVAL] = "interval_too_short"
            else:
                # Normalised, so 90 minutes shows as 1:30:00 next time.
                return self.async_create_entry(
                    data={CONF_SCAN_INTERVAL: _as_duration(interval)})

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                user_input or {
                    CONF_SCAN_INTERVAL: _as_duration(
                        scan_interval(self.config_entry))},
            ),
            description_placeholders={
                "min_seconds": str(int(MIN_SCAN_INTERVAL.total_seconds()))},
            errors=errors,
        )
