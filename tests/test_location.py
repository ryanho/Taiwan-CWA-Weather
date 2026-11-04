"""Choosing the forecast township and observation stations."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.taiwan_cwa.location import (
    OutsideTaiwanError,
    async_fetch_townships,
    async_resolve_location,
    nearest_township,
    rank_stations,
)

from .conftest import ZHONGLI


def _station(sid: str, lat: float, lon: float, altitude: float) -> dict:
    return {"id": sid, "name": sid, "latitude": lat, "longitude": lon, "altitude": altitude}


# ~0.009 degrees latitude per km.
HOME = (25.0, 121.5)


def test_highway_station_skipped_when_regular_one_nearby() -> None:
    stations = [
        _station("CAX010", 25.001, 121.5, 50),  # ~0.1 km, beside an expressway
        _station("C0X010", 25.03, 121.5, 50),  # ~3.3 km
    ]
    assert [s["id"] for s in rank_stations(stations, *HOME, None)] == ["C0X010"]


def test_highway_station_used_when_nothing_else_nearby() -> None:
    stations = [
        _station("CAX010", 25.001, 121.5, 50),
        _station("C0X010", 25.2, 121.5, 50),  # ~22 km
    ]
    assert rank_stations(stations, *HOME, None)[0]["id"] == "CAX010"


def test_altitude_filter() -> None:
    stations = [
        _station("C0MTN1", 25.01, 121.5, 900),  # nearest, but on a mountain
        _station("C0LOW1", 25.04, 121.5, 40),
    ]
    assert rank_stations(stations, *HOME, 20)[0]["id"] == "C0LOW1"
    # Without a known elevation, distance alone decides.
    assert rank_stations(stations, *HOME, None)[0]["id"] == "C0MTN1"


def test_altitude_filter_ignored_when_it_leaves_nothing_nearby() -> None:
    stations = [
        _station("C0MTN1", 25.01, 121.5, 900),
        _station("C0LOW1", 25.3, 121.5, 40),  # ~33 km
    ]
    assert rank_stations(stations, *HOME, 20)[0]["id"] == "C0MTN1"


async def test_nearest_township(hass: HomeAssistant, cwa_api) -> None:
    townships = await async_fetch_townships(hass, "key")
    assert len(townships) == 368
    assert {t["county"] for t in townships} >= {"臺北市", "金門縣", "連江縣", "澎湖縣"}

    zhongli = nearest_township(townships, *ZHONGLI)
    assert (zhongli["county"], zhongli["township"]) == ("桃園市", "中壢區")
    assert (zhongli["forecast_3d"], zhongli["forecast_1w"]) == ("F-D0047-005", "F-D0047-007")

    kinmen = nearest_township(townships, 24.43, 118.32)
    assert kinmen["county"] == "金門縣"

    with pytest.raises(OutsideTaiwanError):
        nearest_township(townships, 35.68, 139.69)  # Tokyo
    with pytest.raises(OutsideTaiwanError):
        nearest_township(townships, 20.70, 116.72)  # Pratas (東沙), no township forecast


async def test_resolve_location(hass: HomeAssistant, cwa_api) -> None:
    location = await async_resolve_location(hass, "key", *ZHONGLI, 150)
    assert (location["latitude"], location["longitude"]) == ZHONGLI
    assert (location["county"], location["township"]) == ("桃園市", "中壢區")
    assert len(location["stations"]) == 3
    assert len(location["nearby_stations"]) == 10
    distances = [s["distance"] for s in location["stations"]]
    assert distances == sorted(distances)
    assert not any(s["id"].startswith("CA") for s in location["stations"])
    assert all(abs(s["altitude"] - 150) <= 300 for s in location["stations"])
    print([(s["id"], s["name"], s["distance"], s["altitude"]) for s in location["stations"]])
