"""Home Assistant serves the integration's icon from its brand/ folder."""
from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

BRAND_DIR = (
    Path(__file__).parent.parent / "custom_components" / "budgetmanager" / "brand")


@pytest.mark.parametrize(
    ("image", "file"),
    [
        ("icon.png", "icon.png"),
        ("icon@2x.png", "icon@2x.png"),
        # no dark variant: the frontend falls back to the regular icon
        ("dark_icon.png", "icon.png"),
        ("logo.png", "icon.png"),
    ],
)
async def test_brand_images(
    hass: HomeAssistant, hass_client, image: str, file: str
) -> None:
    assert await async_setup_component(hass, "brands", {})
    client = await hass_client()

    resp = await client.get(f"/api/brands/integration/budgetmanager/{image}")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == (BRAND_DIR / file).read_bytes()
