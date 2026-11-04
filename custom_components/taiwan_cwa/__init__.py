"""Taiwan CWA Weather integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CITY_SLUGS,
    CITY_STATIONS,
    CONF_API_KEY,
    CONF_CITIES,
    CONF_SCAN_INTERVAL,
    CWA_API_URL,
    CWA_OBS_API_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OBS_HUMIDITY,
    OBS_PRECIPITATION,
    OBS_PRESSURE,
    OBS_TEMPERATURE,
    OBS_TODAY_HIGH,
    OBS_TODAY_LOW,
    OBS_WEATHER,
    OBS_WIND_DIRECTION,
    OBS_WIND_SPEED,
    OBSERVATION_SCAN_INTERVAL,
    async_get_cwa_ssl_context,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api_key = entry.data[CONF_API_KEY]
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    cities = entry.options.get(CONF_CITIES, [])

    _async_cleanup_stale_devices(hass, entry, cities)

    coordinators: dict[str, CWAWeatherCoordinator] = {}
    for city in cities:
        coordinator = CWAWeatherCoordinator(
            hass, api_key=api_key, city=city, scan_interval=scan_interval
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[city] = coordinator

    observation = CWAObservationCoordinator(hass, api_key=api_key, cities=cities)
    await observation.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "forecast": coordinators,
        "observation": observation,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _async_cleanup_stale_devices(
    hass: HomeAssistant, entry: ConfigEntry, cities: list[str]
) -> None:
    """Remove devices for cities that are no longer selected."""
    active_identifiers = {
        f"{entry.entry_id}_{CITY_SLUGS.get(city, city)}" for city in cities
    }
    dev_reg = dr.async_get(hass)
    for device in list(dr.async_entries_for_config_entry(dev_reg, entry.entry_id)):
        if not any(
            domain == DOMAIN and identifier in active_identifiers
            for domain, identifier in device.identifiers
        ):
            dev_reg.async_remove_device(device.id)


async def _async_fetch_cwa(hass: HomeAssistant, url: str, params: dict) -> dict:
    """GET a CWA datastore endpoint and return its decoded JSON body."""
    session = async_get_clientsession(hass)
    ssl_context = await async_get_cwa_ssl_context(hass)
    try:
        async with async_timeout.timeout(30):
            async with session.get(url, params=params, ssl=ssl_context) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"CWA API returned {resp.status}")
                # CWA serves JSON as application/octet-stream, so skip
                # aiohttp's content-type check with content_type=None.
                return await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        raise UpdateFailed(f"CWA API request failed: {err}") from err


def _obs_number(value) -> float | None:
    """Convert an observation value, mapping CWA's -99/-999 sentinels to None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number <= -98 else number


def _obs_text(value) -> str | None:
    if value in (None, "", "-99", "-999", "X"):
        return None
    return value


def _parse_station(station: dict) -> dict:
    elements = station.get("WeatherElement", {})
    extreme = elements.get("DailyExtreme", {})
    high = extreme.get("DailyHigh", {}).get("TemperatureInfo", {})
    low = extreme.get("DailyLow", {}).get("TemperatureInfo", {})
    return {
        "station_id": station.get("StationId"),
        "station_name": station.get("StationName"),
        "observation_time": station.get("ObsTime", {}).get("DateTime"),
        OBS_WEATHER: _obs_text(elements.get("Weather")),
        OBS_TEMPERATURE: _obs_number(elements.get("AirTemperature")),
        OBS_HUMIDITY: _obs_number(elements.get("RelativeHumidity")),
        OBS_PRESSURE: _obs_number(elements.get("AirPressure")),
        OBS_WIND_SPEED: _obs_number(elements.get("WindSpeed")),
        OBS_WIND_DIRECTION: _obs_number(elements.get("WindDirection")),
        OBS_PRECIPITATION: _obs_number(elements.get("Now", {}).get("Precipitation")),
        OBS_TODAY_HIGH: _obs_number(high.get("AirTemperature")),
        OBS_TODAY_LOW: _obs_number(low.get("AirTemperature")),
    }


class CWAWeatherCoordinator(DataUpdateCoordinator):
    """Polls the F-C0032-001 36-hour forecast for one city."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        city: str,
        scan_interval: int,
    ) -> None:
        self.api_key = api_key
        self.city = city
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{city}",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict:
        params = {
            "Authorization": self.api_key,
            "locationName": self.city,
            "format": "JSON",
        }
        data = await _async_fetch_cwa(self.hass, CWA_API_URL, params)

        try:
            location = data["records"]["location"][0]
            # Element order differs between the REST API and the file
            # download, so look elements up by name rather than position.
            elements = {
                element["elementName"]: element["time"][0]["parameter"]["parameterName"]
                for element in location["weatherElement"]
            }
            return {
                "weather": elements["Wx"],
                "rain_prob": elements["PoP"],
                "min_temp": elements["MinT"],
                "max_temp": elements["MaxT"],
            }
        except (KeyError, IndexError) as err:
            raise UpdateFailed(f"Unexpected CWA API response structure: {err}") from err


class CWAObservationCoordinator(DataUpdateCoordinator):
    """Polls O-A0001-001 current observations for all configured cities.

    One request covers every city: the stations are passed as a
    comma-separated StationId list. Data is keyed by city name; a city whose
    stations are all missing from the response is simply absent.
    """

    def __init__(self, hass: HomeAssistant, api_key: str, cities: list[str]) -> None:
        self.api_key = api_key
        self.cities = cities
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_observation",
            update_interval=timedelta(seconds=OBSERVATION_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, dict]:
        station_ids = sorted(
            {sid for city in self.cities for sid in CITY_STATIONS.get(city, [])}
        )
        if not station_ids:
            return {}
        params = {
            "Authorization": self.api_key,
            "StationId": ",".join(station_ids),
            "format": "JSON",
        }
        data = await _async_fetch_cwa(self.hass, CWA_OBS_API_URL, params)

        try:
            stations = data["records"]["Station"]
        except (KeyError, TypeError) as err:
            raise UpdateFailed(f"Unexpected CWA API response structure: {err}") from err
        # The API does not return stations in the requested order.
        by_id = {s.get("StationId"): _parse_station(s) for s in stations}

        result: dict[str, dict] = {}
        for city in self.cities:
            candidates = [by_id[sid] for sid in CITY_STATIONS.get(city, []) if sid in by_id]
            if not candidates:
                _LOGGER.debug("No observation station reported for %s", city)
                continue
            # Prefer the first station that is actually reporting temperature.
            result[city] = next(
                (c for c in candidates if c[OBS_TEMPERATURE] is not None),
                candidates[0],
            )
        return result
