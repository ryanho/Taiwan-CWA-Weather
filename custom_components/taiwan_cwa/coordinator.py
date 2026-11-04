"""Data update coordinators for the Taiwan CWA Weather integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    CWAApiError,
    CWAAuthError,
    async_fetch,
    merge_daily,
    parse_hourly,
    parse_observation,
    parse_periods,
)
from .const import (
    DOMAIN,
    FORECAST_SCAN_INTERVAL,
    MULTI_FORECAST_DATASET,
    OBSERVATION_DATASET,
    OBSERVATION_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class CWAObservationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls O-A0001-001 for the location's station and its fallbacks.

    The data is the first station, in preference order, that reports a
    temperature, plus ``is_fallback`` when that is not the preferred one.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api_key: str, station_ids: list[str]
    ) -> None:
        self.api_key = api_key
        self.station_ids = station_ids
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_observation",
            update_interval=OBSERVATION_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            records = await async_fetch(
                self.hass,
                self.api_key,
                OBSERVATION_DATASET,
                {"StationId": ",".join(self.station_ids)},
            )
        except CWAAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CWAApiError as err:
            raise UpdateFailed(str(err)) from err

        # The API does not return stations in the requested order.
        by_id = {
            s.get("StationId"): parse_observation(s) for s in records.get("Station", [])
        }
        candidates = [by_id[sid] for sid in self.station_ids if sid in by_id]
        if not candidates:
            raise UpdateFailed("None of the observation stations reported data")
        chosen = next((c for c in candidates if c["temperature"] is not None), candidates[0])
        return {**chosen, "is_fallback": chosen["station_id"] != self.station_ids[0]}


class CWAForecastCoordinator(TimestampDataUpdateCoordinator[dict[str, Any]]):
    """Polls the location's 3-day and 1-week township forecasts in one request."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api_key: str, location: dict[str, Any]
    ) -> None:
        self.api_key = api_key
        self.location = location
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_forecast",
            update_interval=FORECAST_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        three_day = self.location["forecast_3d"]
        week = self.location["forecast_1w"]
        try:
            records = await async_fetch(
                self.hass,
                self.api_key,
                MULTI_FORECAST_DATASET,
                {
                    "locationId": f"{three_day},{week}",
                    "LocationName": self.location["township"],
                },
            )
        except CWAAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CWAApiError as err:
            raise UpdateFailed(str(err)) from err

        by_dataset = {}
        for group in records.get("Locations", []):
            for location in group.get("Location", []):
                if location.get("LocationName") == self.location["township"]:
                    by_dataset[f"F-{group.get('Dataid')}"] = location
        if three_day not in by_dataset or week not in by_dataset:
            raise UpdateFailed(
                f"No forecast for {self.location['county']}{self.location['township']}"
            )

        periods = parse_periods(by_dataset[week])
        return {
            "hourly": parse_hourly(by_dataset[three_day]),
            "twice_daily": periods,
            "daily": merge_daily(periods),
        }
