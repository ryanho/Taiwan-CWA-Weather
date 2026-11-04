"""Shared fixtures: recorded CWA API responses for 桃園市中壢區."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.taiwan_cwa.const import (
    API_BASE_URL,
    CONF_API_KEY,
    CONF_LOCATION,
    CONF_ZONE,
    DOMAIN,
)

FIXTURES = Path(__file__).parent / "fixtures"
FORECAST_URL = f"{API_BASE_URL}/F-D0047-093"
OBSERVATION_URL = f"{API_BASE_URL}/O-A0001-001"

# 桃園市中壢區; the recorded forecast starts 2026-11-04 12:00 +08:00.
ZHONGLI = (24.9653, 121.2245)
NOW = "2026-11-04T05:30:00+00:00"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
async def taiwan_home(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Asia/Taipei")
    hass.config.latitude, hass.config.longitude = ZHONGLI
    hass.config.elevation = 150
    assert await async_setup_component(hass, "zone", {})
    await hass.async_block_till_done()


def mock_townships(aioclient_mock: AiohttpClientMocker) -> None:
    for i in range(5):
        data = load_fixture(f"townships_{i}.json")
        ids = ",".join(f"F-{g['Dataid']}" for g in data["records"]["Locations"])
        aioclient_mock.get(
            FORECAST_URL, params={"locationId": ids, "ElementName": "天氣現象"}, json=data
        )


@pytest.fixture
def cwa_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """All CWA endpoints answering with the recorded responses."""
    mock_townships(aioclient_mock)
    aioclient_mock.get(
        FORECAST_URL,
        params={"LocationName": "中壢區"},
        json=load_fixture("forecast_zhongli.json"),
    )
    aioclient_mock.get(OBSERVATION_URL, json=load_fixture("observation.json"))
    return aioclient_mock


async def async_resolved_entry(hass: HomeAssistant, **kwargs) -> MockConfigEntry:
    """A config entry whose location was resolved like the config flow does."""
    from custom_components.taiwan_cwa.location import async_resolve_location

    location = await async_resolve_location(hass, "key", *ZHONGLI, 150)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title="Home",
        unique_id="zone.home",
        data={CONF_API_KEY: "key", CONF_ZONE: "zone.home", CONF_LOCATION: location},
        **kwargs,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_entry(hass: HomeAssistant, cwa_api) -> MockConfigEntry:
    entry = await async_resolved_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
