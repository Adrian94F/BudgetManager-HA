"""Config flow for Budget Manager.

Only the URL, the username and a refresh token are stored; the password is
used once to obtain the token pair and then forgotten.
"""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BudgetManagerApi, BudgetManagerAuthError, BudgetManagerError
from .const import CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_URL = "https://budget.frydmanski.cc"

USER_SCHEMA = vol.Schema({
    vol.Required(CONF_URL): str,
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_VERIFY_SSL, default=True): bool,
})

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class BudgetManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

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
