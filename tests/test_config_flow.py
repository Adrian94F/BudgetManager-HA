"""Tests for the Budget Manager config flow."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.budgetmanager.api import (
    BudgetManagerAuthError,
    BudgetManagerError,
)
from custom_components.budgetmanager.const import CONF_REFRESH_TOKEN, DOMAIN

USER_INPUT = {
    CONF_URL: "http://bm.local/",
    CONF_USERNAME: "alice",
    CONF_PASSWORD: "secret",
    CONF_VERIFY_SSL: True,
}


@pytest.fixture
def flow_api() -> Generator[MagicMock]:
    with patch(
        "custom_components.budgetmanager.config_flow.BudgetManagerApi",
        autospec=True,
    ) as api_class:
        api = api_class.return_value
        api.refresh_token = "refresh-new"
        yield api


@pytest.fixture(autouse=True)
def no_setup() -> Generator[None]:
    with patch(
        "custom_components.budgetmanager.async_setup_entry", return_value=True
    ):
        yield


async def test_user_flow_stores_token_not_password(
    hass: HomeAssistant, flow_api: MagicMock
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Budget Manager (alice)"
    assert result["data"] == {
        CONF_URL: "http://bm.local",
        CONF_USERNAME: "alice",
        CONF_VERIFY_SSL: True,
        CONF_REFRESH_TOKEN: "refresh-new",
    }
    flow_api.login.assert_awaited_once_with("alice", "secret")


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (BudgetManagerAuthError, "invalid_auth"),
        (BudgetManagerError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, flow_api: MagicMock, error: type[Exception],
    expected: str,
) -> None:
    flow_api.login.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    # recovers once the server accepts the login
    flow_api.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_same_account_twice_aborts(
    hass: HomeAssistant, flow_api: MagicMock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_replaces_refresh_token(
    hass: HomeAssistant, flow_api: MagicMock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "secret"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_REFRESH_TOKEN] == "refresh-new"
    flow_api.login.assert_awaited_once_with("alice", "secret")
