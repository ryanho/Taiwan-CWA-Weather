"""Config, options and reauth flows."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.taiwan_cwa.const import (
    CONF_API_KEY,
    CONF_LOCATION,
    CONF_RELOCATE,
    CONF_STATION,
    CONF_ZONE,
    DOMAIN,
    STATION_AUTO,
)

from .conftest import FORECAST_URL, OBSERVATION_URL, async_resolved_entry, mock_townships


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow(hass: HomeAssistant, cwa_api) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "key", CONF_ZONE: "zone.home"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test home"
    assert result["data"][CONF_ZONE] == "zone.home"
    location = result["data"][CONF_LOCATION]
    assert location["township"] == "中壢區"
    assert len(location["stations"]) == 3
    assert result["result"].unique_id == "zone.home"


async def test_user_flow_invalid_key(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(FORECAST_URL, status=401)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad", CONF_ZONE: "zone.home"}
    )
    assert result["errors"] == {CONF_API_KEY: "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant, aioclient_mock) -> None:
    mock_townships(aioclient_mock)
    aioclient_mock.get(OBSERVATION_URL, status=500)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "key", CONF_ZONE: "zone.home"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_outside_taiwan(hass: HomeAssistant, cwa_api) -> None:
    hass.states.async_set("zone.tokyo", "0", {"latitude": 35.68, "longitude": 139.69})
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "key", CONF_ZONE: "zone.tokyo"}
    )
    assert result["errors"] == {CONF_ZONE: "outside_taiwan"}


async def test_user_flow_already_configured(hass: HomeAssistant, cwa_api) -> None:
    await async_resolved_entry(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "key", CONF_ZONE: "zone.home"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_manual_station(hass: HomeAssistant, setup_entry) -> None:
    entry = setup_entry
    nearby = entry.data[CONF_LOCATION]["nearby_stations"]
    manual = nearby[-1]["id"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_STATION: manual, CONF_RELOCATE: False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options[CONF_STATION] == manual
    observation = entry.runtime_data.observation
    assert observation.station_ids[0] == manual
    # The automatic picks remain as fallbacks.
    assert observation.station_ids[1:] == [s["id"] for s in entry.data[CONF_LOCATION]["stations"]]


async def test_options_relocate(hass: HomeAssistant, setup_entry) -> None:
    entry = setup_entry
    entry.data[CONF_LOCATION]["stations"].clear()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_STATION: STATION_AUTO, CONF_RELOCATE: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(entry.data[CONF_LOCATION]["stations"]) == 3


async def test_reauth(hass: HomeAssistant, setup_entry, aioclient_mock) -> None:
    entry = setup_entry
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new-key"
