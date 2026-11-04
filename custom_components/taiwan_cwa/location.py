"""Resolve a zone's coordinates to a CWA township forecast and nearby stations."""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .api import CWA_TZ, async_fetch, station_coordinates, to_number
from .const import (
    AUTO_STATION_COUNT,
    COUNTY_FORECAST_DATASETS,
    HIGHWAY_FALLBACK_RADIUS_KM,
    HIGHWAY_STATION_PREFIX,
    MANUAL_STATION_CHOICES,
    MAX_ALTITUDE_DIFFERENCE_M,
    MAX_TOWNSHIP_DISTANCE_KM,
    MULTI_FORECAST_BATCH,
    MULTI_FORECAST_DATASET,
    OBSERVATION_DATASET,
)


class OutsideTaiwanError(Exception):
    """The coordinates are not near any CWA forecast township."""


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


async def async_fetch_townships(hass: HomeAssistant, api_key: str) -> list[dict[str, Any]]:
    """Every forecast township with its coordinates and datasets."""
    dataset_counties = {
        three_day.removeprefix("F-"): (county, three_day, week)
        for county, (three_day, week) in COUNTY_FORECAST_DATASETS.items()
    }
    ids = [three_day for three_day, _ in COUNTY_FORECAST_DATASETS.values()]
    # Only the coordinates are needed; keep the payload small.
    time_to = (dt_util.now(CWA_TZ) + timedelta(hours=3)).strftime("%Y-%m-%dT%H:00:00")

    townships = []
    for i in range(0, len(ids), MULTI_FORECAST_BATCH):
        records = await async_fetch(
            hass,
            api_key,
            MULTI_FORECAST_DATASET,
            {
                "locationId": ",".join(ids[i : i + MULTI_FORECAST_BATCH]),
                "ElementName": "天氣現象",
                "timeTo": time_to,
            },
        )
        for group in records.get("Locations", []):
            county, three_day, week = dataset_counties.get(
                group.get("Dataid"), (group.get("LocationsName"), None, None)
            )
            if three_day is None:
                continue
            for location in group.get("Location", []):
                lat = to_number(location.get("Latitude"))
                lon = to_number(location.get("Longitude"))
                if lat is None or lon is None:
                    continue
                townships.append(
                    {
                        "county": county,
                        "township": location["LocationName"],
                        "geocode": location.get("Geocode"),
                        "latitude": lat,
                        "longitude": lon,
                        "forecast_3d": three_day,
                        "forecast_1w": week,
                    }
                )
    return townships


def nearest_township(
    townships: list[dict[str, Any]], lat: float, lon: float
) -> dict[str, Any]:
    if not townships:
        raise OutsideTaiwanError
    best = min(townships, key=lambda t: distance_km(lat, lon, t["latitude"], t["longitude"]))
    if distance_km(lat, lon, best["latitude"], best["longitude"]) > MAX_TOWNSHIP_DISTANCE_KM:
        raise OutsideTaiwanError
    return best


async def async_fetch_stations(hass: HomeAssistant, api_key: str) -> list[dict[str, Any]]:
    """Every observation station with its coordinates and altitude."""
    records = await async_fetch(
        hass, api_key, OBSERVATION_DATASET, {"WeatherElement": "AirTemperature"}
    )
    stations = []
    for station in records.get("Station", []):
        coords = station_coordinates(station)
        if coords is None:
            continue
        stations.append(
            {
                "id": station["StationId"],
                "name": station.get("StationName"),
                "county": station.get("GeoInfo", {}).get("CountyName"),
                "town": station.get("GeoInfo", {}).get("TownName"),
                "latitude": coords[0],
                "longitude": coords[1],
                "altitude": to_number(station.get("GeoInfo", {}).get("StationAltitude")),
            }
        )
    return stations


def _with_distance(stations, lat, lon) -> list[dict[str, Any]]:
    ranked = [
        {**s, "distance": round(distance_km(lat, lon, s["latitude"], s["longitude"]), 2)}
        for s in stations
    ]
    ranked.sort(key=lambda s: s["distance"])
    return ranked


def rank_stations(
    stations: list[dict[str, Any]],
    lat: float,
    lon: float,
    elevation: float | None,
) -> list[dict[str, Any]]:
    """Stations best suited to represent the location, nearest first.

    Highway stations (CA...) sit beside expressways and are only used when no
    other station is within HIGHWAY_FALLBACK_RADIUS_KM. When the location's
    elevation is known, stations more than MAX_ALTITUDE_DIFFERENCE_M higher or
    lower are skipped, unless that would leave nothing nearby.
    """
    ranked = _with_distance(stations, lat, lon)
    regular = [s for s in ranked if not s["id"].startswith(HIGHWAY_STATION_PREFIX)]
    if regular and regular[0]["distance"] <= HIGHWAY_FALLBACK_RADIUS_KM:
        ranked = regular

    if elevation is not None:
        similar = [
            s
            for s in ranked
            if s["altitude"] is not None
            and abs(s["altitude"] - elevation) <= MAX_ALTITUDE_DIFFERENCE_M
        ]
        if similar and similar[0]["distance"] <= HIGHWAY_FALLBACK_RADIUS_KM:
            ranked = similar
    return ranked


def station_summary(station: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "name", "county", "town", "altitude", "distance")
    return {key: station.get(key) for key in keys}


async def async_resolve_location(
    hass: HomeAssistant,
    api_key: str,
    lat: float,
    lon: float,
    elevation: float | None,
) -> dict[str, Any]:
    """Pick the forecast township and observation stations for coordinates.

    Raises CWAAuthError / CWAApiError from the API and OutsideTaiwanError.
    """
    township = nearest_township(await async_fetch_townships(hass, api_key), lat, lon)
    stations = await async_fetch_stations(hass, api_key)
    ranked = rank_stations(stations, lat, lon, elevation)
    return {
        # The zone coordinates this was resolved for, to detect a moved zone.
        "latitude": lat,
        "longitude": lon,
        "county": township["county"],
        "township": township["township"],
        "geocode": township["geocode"],
        "forecast_3d": township["forecast_3d"],
        "forecast_1w": township["forecast_1w"],
        "township_distance": round(
            distance_km(lat, lon, township["latitude"], township["longitude"]), 2
        ),
        "stations": [station_summary(s) for s in ranked[:AUTO_STATION_COUNT]],
        "nearby_stations": [
            station_summary(s)
            for s in _with_distance(stations, lat, lon)[:MANUAL_STATION_CHOICES]
        ],
    }
