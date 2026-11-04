"""Weather entity, sensors, service device and setup behaviour."""
from __future__ import annotations

import copy

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.taiwan_cwa import _async_refresh_location_if_moved
from custom_components.taiwan_cwa.const import CONF_LOCATION, DOMAIN

from .conftest import (
    FORECAST_URL,
    OBSERVATION_URL,
    async_resolved_entry,
    load_fixture,
    mock_townships,
)

WEATHER = "weather.taiwan_cwa_home"


async def _forecasts(hass: HomeAssistant, kind: str) -> list[dict]:
    response = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": WEATHER, "type": kind},
        blocking=True,
        return_response=True,
    )
    return response[WEATHER]["forecast"]


def _station_observation(entry) -> dict:
    station_id = entry.data[CONF_LOCATION]["stations"][0]["id"]
    return next(
        s for s in load_fixture("observation.json")["records"]["Station"] if s["StationId"] == station_id
    )


async def test_weather_entity(hass: HomeAssistant, setup_entry) -> None:
    station = _station_observation(setup_entry)
    state = hass.states.get(WEATHER)
    assert state.attributes["friendly_name"] == "Home"
    assert state.attributes["temperature"] == float(station["WeatherElement"]["AirTemperature"])
    assert state.attributes["humidity"] == float(station["WeatherElement"]["RelativeHumidity"])
    assert state.attributes["apparent_temperature"] is not None
    assert state.attributes["uv_index"] is not None  # 13:30, a daytime period
    assert state.state in ("sunny", "partlycloudy", "cloudy")
    assert station["StationName"] in state.attributes["attribution"]
    assert "桃園市中壢區" in state.attributes["attribution"]


async def test_forecasts(hass: HomeAssistant, setup_entry) -> None:
    daily = await _forecasts(hass, "daily")
    assert len(daily) >= 7
    assert all("templow" in d and "temperature" in d for d in daily)
    assert daily[0]["datetime"].startswith("2026-11-04T00:00:00+08:00")

    twice = await _forecasts(hass, "twice_daily")
    assert len(twice) == 14
    assert [t["is_daytime"] for t in twice[:2]] == [True, False]

    hourly = await _forecasts(hass, "hourly")
    assert len(hourly) > 24
    assert hourly[0]["datetime"] == "2026-11-04T12:00:00+08:00"
    # Clear nights should not show the sun.
    night = [h for h in hourly if h["datetime"][11:13] in ("00", "03") and h["condition"]]
    assert all(h["condition"] != "sunny" for h in night)


async def test_rain_forecast_overrides_observed_sky(hass: HomeAssistant, aioclient_mock) -> None:
    mock_townships(aioclient_mock)
    forecast = load_fixture("forecast_zhongli.json")
    three_day = next(g for g in forecast["records"]["Locations"] if g["Dataid"] == "D0047-005")
    for element in three_day["Location"][0]["WeatherElement"]:
        if element["ElementName"] == "天氣現象":
            for item in element["Time"]:
                item["ElementValue"][0].update(Weather="多雲午後短暫雷陣雨", WeatherCode="22")
    aioclient_mock.get(FORECAST_URL, params={"LocationName": "中壢區"}, json=forecast)
    aioclient_mock.get(OBSERVATION_URL, json=load_fixture("observation.json"))

    entry = await async_resolved_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(WEATHER).state == "lightning-rainy"


async def test_station_fallback(hass: HomeAssistant, aioclient_mock) -> None:
    mock_townships(aioclient_mock)
    aioclient_mock.get(
        FORECAST_URL, params={"LocationName": "中壢區"}, json=load_fixture("forecast_zhongli.json")
    )
    observation = load_fixture("observation.json")
    aioclient_mock.get(OBSERVATION_URL, json=observation)
    entry = await async_resolved_entry(hass)

    primary, backup = (s["id"] for s in entry.data[CONF_LOCATION]["stations"][:2])
    for station in observation["records"]["Station"]:
        if station["StationId"] == primary:
            station["WeatherElement"]["AirTemperature"] = "-99"
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        FORECAST_URL, params={"LocationName": "中壢區"}, json=load_fixture("forecast_zhongli.json")
    )
    aioclient_mock.get(OBSERVATION_URL, json=observation)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    station_sensor = hass.states.get("sensor.taiwan_cwa_home_station")
    assert station_sensor.attributes["station_id"] == backup
    assert station_sensor.attributes["is_fallback"] is True


async def test_observation_outage_uses_forecast(hass: HomeAssistant, aioclient_mock) -> None:
    mock_townships(aioclient_mock)
    aioclient_mock.get(
        FORECAST_URL, params={"LocationName": "中壢區"}, json=load_fixture("forecast_zhongli.json")
    )
    aioclient_mock.get(OBSERVATION_URL, json=load_fixture("observation.json"))
    entry = await async_resolved_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    aioclient_mock.get(OBSERVATION_URL, status=500)
    await entry.runtime_data.observation.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(WEATHER)
    assert state.state != "unavailable"
    assert state.attributes["temperature"] is not None  # from the hourly forecast
    assert "pressure" not in state.attributes
    assert hass.states.get("sensor.taiwan_cwa_home_temperature").state == "unavailable"


async def test_service_device_and_default_entities(hass: HomeAssistant, setup_entry) -> None:
    device = dr.async_get(hass).async_get_device({(DOMAIN, setup_entry.entry_id)})
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.name == "Home"

    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, setup_entry.entry_id)
    enabled = sorted(e.entity_id for e in entries if not e.disabled_by)
    assert enabled == [
        "sensor.taiwan_cwa_home_humidity",
        "sensor.taiwan_cwa_home_precipitation",
        "sensor.taiwan_cwa_home_station",
        "sensor.taiwan_cwa_home_temperature",
        WEATHER,
    ]
    assert registry.async_get("sensor.taiwan_cwa_home_station").entity_category == "diagnostic"
    assert hass.states.get("sensor.taiwan_cwa_home_temperature").attributes["friendly_name"] == (
        "Home Temperature"
    )


async def test_station_sensor(hass: HomeAssistant, setup_entry) -> None:
    station = setup_entry.data[CONF_LOCATION]["stations"][0]
    state = hass.states.get("sensor.taiwan_cwa_home_station")
    assert state.state == station["name"]
    assert state.attributes["station_id"] == station["id"]
    assert state.attributes["distance_km"] == station["distance"]
    assert state.attributes["is_fallback"] is False
    assert state.attributes["forecast_location"] == "桃園市中壢區"


async def test_disabled_sensors_values(hass: HomeAssistant, cwa_api) -> None:
    entry = await async_resolved_entry(hass)
    registry = er.async_get(hass)
    for key in ("weather_code", "uv_index", "rain_probability", "wind_direction"):
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{entry.entry_id}_{key}",
            config_entry=entry,
            suggested_object_id=f"taiwan_cwa_home_{key}",
        )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    weather_code = hass.states.get("sensor.taiwan_cwa_home_weather_code")
    assert weather_code.state == "01"
    assert weather_code.attributes["description"] == "晴"
    assert "01" in weather_code.attributes["options"]
    assert float(hass.states.get("sensor.taiwan_cwa_home_uv_index").state) >= 0
    assert hass.states.get("sensor.taiwan_cwa_home_rain_probability").state == "0"


async def test_traditional_chinese_names(hass: HomeAssistant, cwa_api) -> None:
    await hass.config.async_update(language="zh-Hant")
    entry = await async_resolved_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.taiwan_cwa_home_temperature").attributes["friendly_name"] == (
        "Home 氣溫"
    )
    assert hass.states.get("sensor.taiwan_cwa_home_station").attributes["friendly_name"] == (
        "Home 觀測測站"
    )


async def test_legacy_entry_is_rejected(hass: HomeAssistant, cwa_api) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, version=1, data={"api_key": "key"}, options={"cities": ["臺北市"]}
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"legacy_entry_{entry.entry_id}")


async def test_zone_moved_relocates(hass: HomeAssistant, cwa_api) -> None:
    entry = await async_resolved_entry(hass)
    old = copy.deepcopy(entry.data[CONF_LOCATION])
    hass.states.async_set("zone.home", "0", {"latitude": 25.0375, "longitude": 121.5637})
    await _async_refresh_location_if_moved(hass, entry)
    new = entry.data[CONF_LOCATION]
    assert (new["county"], new["township"]) == ("臺北市", "信義區")
    assert new["stations"] != old["stations"]
