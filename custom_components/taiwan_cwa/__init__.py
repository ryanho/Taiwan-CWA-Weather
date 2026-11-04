"""Taiwan CWA Weather integration for Home Assistant."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

from .api import CWAApiError, CWAAuthError
from .const import (
    CONF_API_KEY,
    CONF_LOCATION,
    CONF_STATION,
    CONF_ZONE,
    DOMAIN,
    STATION_AUTO,
)
from .coordinator import CWAForecastCoordinator, CWAObservationCoordinator
from .location import OutsideTaiwanError, async_resolve_location

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "weather"]

# Re-resolve the township and stations once the zone moves this far (~1 km).
_ZONE_MOVED_DEGREES = 0.01


@dataclass
class CWAData:
    observation: CWAObservationCoordinator
    forecast: CWAForecastCoordinator


type CWAConfigEntry = ConfigEntry[CWAData]


def zone_coordinates(hass: HomeAssistant, zone: str) -> tuple[float, float] | None:
    state = hass.states.get(zone)
    if state is None:
        return None
    lat, lon = state.attributes.get("latitude"), state.attributes.get("longitude")
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def zone_elevation(hass: HomeAssistant, zone: str) -> float | None:
    """Only the home zone has a known elevation."""
    return float(hass.config.elevation) if zone == "zone.home" else None


def station_ids(entry: ConfigEntry) -> list[str]:
    """The station chain to poll: a manual choice first, then the auto picks."""
    auto = [s["id"] for s in entry.data[CONF_LOCATION]["stations"]]
    manual = entry.options.get(CONF_STATION, STATION_AUTO)
    if manual != STATION_AUTO:
        return [manual, *(sid for sid in auto if sid != manual)]
    return auto


async def _async_refresh_location_if_moved(hass: HomeAssistant, entry: ConfigEntry) -> None:
    location: dict[str, Any] = entry.data[CONF_LOCATION]
    coords = zone_coordinates(hass, entry.data[CONF_ZONE])
    if coords is None:
        return
    if (
        abs(coords[0] - location["latitude"]) < _ZONE_MOVED_DEGREES
        and abs(coords[1] - location["longitude"]) < _ZONE_MOVED_DEGREES
    ):
        return
    _LOGGER.info("Zone %s moved; picking a new township and stations", entry.data[CONF_ZONE])
    try:
        new_location = await async_resolve_location(
            hass,
            entry.data[CONF_API_KEY],
            *coords,
            zone_elevation(hass, entry.data[CONF_ZONE]),
        )
    except CWAAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except CWAApiError as err:
        raise ConfigEntryNotReady(str(err)) from err
    except OutsideTaiwanError:
        _LOGGER.warning(
            "Zone %s moved outside Taiwan; keeping the previous location",
            entry.data[CONF_ZONE],
        )
        return
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_LOCATION: new_location}
    )


async def async_setup_entry(hass: HomeAssistant, entry: CWAConfigEntry) -> bool:
    await _async_refresh_location_if_moved(hass, entry)

    api_key = entry.data[CONF_API_KEY]
    observation = CWAObservationCoordinator(hass, entry, api_key, station_ids(entry))
    forecast = CWAForecastCoordinator(hass, entry, api_key, entry.data[CONF_LOCATION])
    await observation.async_config_entry_first_refresh()
    await forecast.async_config_entry_first_refresh()
    entry.runtime_data = CWAData(observation=observation, forecast=forecast)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CWAConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version == 1:
        # 1.x configured a list of cities; 2.0 follows a zone. There is no
        # meaningful conversion, so ask the user to set it up again.
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"legacy_entry_{entry.entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="legacy_entry",
        )
        _LOGGER.error(
            "Taiwan CWA Weather 2.0 cannot use settings from 1.x; delete the "
            "integration and add it again"
        )
        return False
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    ir.async_delete_issue(hass, DOMAIN, f"legacy_entry_{entry.entry_id}")
