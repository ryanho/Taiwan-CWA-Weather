"""CWA open data API access and response parsing."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import aiohttp
import async_timeout

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import API_BASE_URL, TIME_ZONE, async_get_cwa_ssl_context

CWA_TZ = dt_util.get_time_zone(TIME_ZONE)


class CWAApiError(Exception):
    """The CWA API could not be reached or returned an unexpected response."""


class CWAAuthError(CWAApiError):
    """The API key was rejected."""


async def async_fetch(
    hass: HomeAssistant, api_key: str, dataset: str, params: dict[str, str] | None = None
) -> dict[str, Any]:
    """GET a CWA datastore dataset and return its ``records``."""
    session = async_get_clientsession(hass)
    ssl_context = await async_get_cwa_ssl_context(hass)
    query = {"Authorization": api_key, "format": "JSON", **(params or {})}
    try:
        async with async_timeout.timeout(30):
            async with session.get(
                f"{API_BASE_URL}/{dataset}", params=query, ssl=ssl_context
            ) as resp:
                if resp.status == 401:
                    raise CWAAuthError("CWA API key was rejected")
                if resp.status != 200:
                    raise CWAApiError(f"CWA API returned {resp.status} for {dataset}")
                # CWA serves JSON as application/octet-stream, so skip
                # aiohttp's content-type check with content_type=None.
                data = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        raise CWAApiError(f"CWA API request failed: {err}") from err
    try:
        return data["records"]
    except (KeyError, TypeError) as err:
        raise CWAApiError(f"Unexpected CWA response for {dataset}") from err


# ---------------------------------------------------------------------------
# Value helpers


def to_number(value: Any) -> float | None:
    """Convert a CWA value, mapping missing-data sentinels (-99, -999) to None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number <= -98 else number


def to_percent(value: Any) -> int | None:
    number = to_number(value)
    return None if number is None else round(number)


def observed_wind_bearing(value: Any) -> float | None:
    """Observation wind direction in degrees.

    CWA reports north as 360; 0 means calm, 990 means variable and -99 means
    missing, none of which is a bearing.
    """
    bearing = to_number(value)
    if bearing is None or not 0 < bearing <= 360:
        return None
    return bearing


FORECAST_WIND_BEARINGS = {
    "偏北風": 360.0,
    "東北風": 45.0,
    "偏東風": 90.0,
    "東南風": 135.0,
    "偏南風": 180.0,
    "西南風": 225.0,
    "偏西風": 270.0,
    "西北風": 315.0,
}


def parse_cwa_time(value: str | None) -> datetime | None:
    """Parse a CWA timestamp; naive values are Taiwan local time."""
    if not value:
        return None
    parsed = dt_util.parse_datetime(value.replace(" ", "T"))
    if parsed is not None and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CWA_TZ)
    return parsed


# ---------------------------------------------------------------------------
# Weather conditions

# HA condition per CWA WeatherCode (see const.WEATHER_CODES).
_CODE_CONDITIONS: dict[int, str] = {
    1: ATTR_CONDITION_SUNNY,
    **dict.fromkeys((2, 3, 4), ATTR_CONDITION_PARTLYCLOUDY),
    **dict.fromkeys((5, 6, 7), ATTR_CONDITION_CLOUDY),
    **dict.fromkeys((8, 9, 10, 11, 12, 13, 14), ATTR_CONDITION_RAINY),
    **dict.fromkeys((15, 16, 17, 18), ATTR_CONDITION_LIGHTNING_RAINY),
    **dict.fromkeys((19, 20), ATTR_CONDITION_RAINY),
    **dict.fromkeys((21, 22), ATTR_CONDITION_LIGHTNING_RAINY),
    23: ATTR_CONDITION_SNOWY_RAINY,
    **dict.fromkeys((24, 25, 26, 27, 28), ATTR_CONDITION_FOG),
    **dict.fromkeys((29, 30, 31, 32), ATTR_CONDITION_RAINY),
    **dict.fromkeys((33, 34, 35, 36), ATTR_CONDITION_LIGHTNING_RAINY),
    37: ATTR_CONDITION_SNOWY_RAINY,
    **dict.fromkeys((38, 39), ATTR_CONDITION_RAINY),
    41: ATTR_CONDITION_LIGHTNING_RAINY,
    42: ATTR_CONDITION_SNOWY,
}

# Conditions that only describe sky cover.
SKY_CONDITIONS = frozenset(
    {
        ATTR_CONDITION_SUNNY,
        ATTR_CONDITION_CLEAR_NIGHT,
        ATTR_CONDITION_PARTLYCLOUDY,
        ATTR_CONDITION_CLOUDY,
    }
)

# Station observations only report a handful of sky descriptions.
_OBSERVED_TEXT_CODES = {
    "晴": 1,
    "晴天": 1,
    "晴時多雲": 2,
    "多雲時晴": 3,
    "多雲": 4,
    "多雲時陰": 5,
    "陰時多雲": 6,
    "陰": 7,
    "陰天": 7,
}


def code_condition(code: Any, daytime: bool = True) -> str | None:
    """Map a CWA WeatherCode to a Home Assistant weather condition."""
    try:
        condition = _CODE_CONDITIONS.get(int(code))
    except (TypeError, ValueError):
        return None
    if condition == ATTR_CONDITION_SUNNY and not daytime:
        return ATTR_CONDITION_CLEAR_NIGHT
    return condition


def text_condition(text: str | None, daytime: bool = True) -> str | None:
    """Map an observed weather description (e.g. 多雲) to a condition."""
    if not text:
        return None
    if (code := _OBSERVED_TEXT_CODES.get(text)) is not None:
        return code_condition(code, daytime)
    # Rare free-form observations such as 多雲有雨.
    if "雷" in text:
        return ATTR_CONDITION_LIGHTNING_RAINY
    if "雪" in text:
        return ATTR_CONDITION_SNOWY_RAINY if "雨" in text else ATTR_CONDITION_SNOWY
    if "雨" in text:
        return ATTR_CONDITION_RAINY
    if "霧" in text:
        return ATTR_CONDITION_FOG
    if "陰" in text:
        return ATTR_CONDITION_CLOUDY
    if "雲" in text:
        return ATTR_CONDITION_PARTLYCLOUDY
    return None


# ---------------------------------------------------------------------------
# O-A0001-001 observations


def station_coordinates(station: dict[str, Any]) -> tuple[float, float] | None:
    for coord in station.get("GeoInfo", {}).get("Coordinates", []):
        if coord.get("CoordinateName") == "WGS84":
            lat = to_number(coord.get("StationLatitude"))
            lon = to_number(coord.get("StationLongitude"))
            if lat is not None and lon is not None:
                return lat, lon
    return None


def parse_observation(station: dict[str, Any]) -> dict[str, Any]:
    elements = station.get("WeatherElement", {})
    extreme = elements.get("DailyExtreme", {})
    high = extreme.get("DailyHigh", {}).get("TemperatureInfo", {})
    low = extreme.get("DailyLow", {}).get("TemperatureInfo", {})
    weather = elements.get("Weather")
    return {
        "station_id": station.get("StationId"),
        "station_name": station.get("StationName"),
        "observation_time": parse_cwa_time(station.get("ObsTime", {}).get("DateTime")),
        "weather": None if weather in (None, "", "-99", "X") else weather,
        "temperature": to_number(elements.get("AirTemperature")),
        "humidity": to_number(elements.get("RelativeHumidity")),
        "pressure": to_number(elements.get("AirPressure")),
        "wind_speed": to_number(elements.get("WindSpeed")),
        "wind_bearing": observed_wind_bearing(elements.get("WindDirection")),
        "wind_gust": to_number(elements.get("GustInfo", {}).get("PeakGustSpeed")),
        "precipitation": to_number(elements.get("Now", {}).get("Precipitation")),
        "today_high": to_number(high.get("AirTemperature")),
        "today_low": to_number(low.get("AirTemperature")),
    }


# ---------------------------------------------------------------------------
# F-D0047 township forecasts


def _element_series(location: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {e["ElementName"]: e.get("Time", []) for e in location.get("WeatherElement", [])}


def _point_values(series: list[dict[str, Any]], key: str) -> dict[datetime, Any]:
    """{DataTime: value} for an instantaneous element (e.g. 溫度)."""
    values = {}
    for item in series:
        when = parse_cwa_time(item.get("DataTime"))
        if when is not None and item.get("ElementValue"):
            values[when] = item["ElementValue"][0].get(key)
    return values


def _intervals(series: list[dict[str, Any]]) -> list[tuple[datetime, datetime, dict]]:
    """[(start, end, values)] for a period element (e.g. 天氣現象)."""
    result = []
    for item in series:
        start = parse_cwa_time(item.get("StartTime"))
        end = parse_cwa_time(item.get("EndTime"))
        if start and end and item.get("ElementValue"):
            result.append((start, end, item["ElementValue"][0]))
    return result


def _covering(intervals, when: datetime) -> dict:
    for start, end, values in intervals:
        if start <= when < end:
            return values
    return {}


def parse_hourly(location: dict[str, Any]) -> list[dict[str, Any]]:
    """Hourly forecast points from a 3-day township dataset.

    Temperature-type elements are hourly near-term and 3-hourly later; weather,
    rain probability and wind are 3-hourly, so each point takes the 3-hour
    period (or wind sample) covering it.
    """
    series = _element_series(location)
    temperature = _point_values(series.get("溫度", []), "Temperature")
    apparent = _point_values(series.get("體感溫度", []), "ApparentTemperature")
    dew_point = _point_values(series.get("露點溫度", []), "DewPoint")
    humidity = _point_values(series.get("相對濕度", []), "RelativeHumidity")
    wind_speed = _point_values(series.get("風速", []), "WindSpeed")
    wind_dir = _point_values(series.get("風向", []), "WindDirection")
    weather = _intervals(series.get("天氣現象", []))
    pop = _intervals(series.get("3小時降雨機率", []))

    wind_times = sorted(wind_speed)
    points = []
    for when in sorted(temperature):
        # Latest wind sample at or before this hour.
        wind_at = max((t for t in wind_times if t <= when), default=None)
        wx = _covering(weather, when)
        points.append(
            {
                "datetime": when,
                "weather_code": wx.get("WeatherCode"),
                "weather": wx.get("Weather"),
                "temperature": to_number(temperature[when]),
                "apparent_temperature": to_number(apparent.get(when)),
                "dew_point": to_number(dew_point.get(when)),
                "humidity": to_number(humidity.get(when)),
                "precipitation_probability": to_percent(
                    _covering(pop, when).get("ProbabilityOfPrecipitation")
                ),
                "wind_speed": to_number(wind_speed.get(wind_at)) if wind_at else None,
                "wind_bearing": FORECAST_WIND_BEARINGS.get(wind_dir.get(wind_at))
                if wind_at
                else None,
            }
        )
    return points


def parse_periods(location: dict[str, Any]) -> list[dict[str, Any]]:
    """12-hour day/night periods from a 1-week township dataset."""
    series = _element_series(location)

    def by_start(name: str) -> dict[datetime, dict]:
        return {start: values for start, _, values in _intervals(series.get(name, []))}

    max_t = by_start("最高溫度")
    min_t = by_start("最低溫度")
    max_apparent = by_start("最高體感溫度")
    dew_point = by_start("平均露點溫度")
    humidity = by_start("平均相對濕度")
    wind_speed = by_start("風速")
    wind_dir = by_start("風向")
    pop = by_start("12小時降雨機率")
    uv = by_start("紫外線指數")

    periods = []
    for start, end, wx in _intervals(series.get("天氣現象", [])):
        periods.append(
            {
                "datetime": start,
                "end": end,
                # Day periods run 06-18 and night periods 18-06; the first one
                # may be shortened to start at the issue time.
                "is_daytime": 6 <= start.astimezone(CWA_TZ).hour < 18,
                "weather_code": wx.get("WeatherCode"),
                "weather": wx.get("Weather"),
                "temperature": to_number(max_t.get(start, {}).get("MaxTemperature")),
                "templow": to_number(min_t.get(start, {}).get("MinTemperature")),
                "apparent_temperature": to_number(
                    max_apparent.get(start, {}).get("MaxApparentTemperature")
                ),
                "dew_point": to_number(dew_point.get(start, {}).get("DewPoint")),
                "humidity": to_number(humidity.get(start, {}).get("RelativeHumidity")),
                "precipitation_probability": to_percent(
                    pop.get(start, {}).get("ProbabilityOfPrecipitation")
                ),
                "wind_speed": to_number(wind_speed.get(start, {}).get("WindSpeed")),
                "wind_bearing": FORECAST_WIND_BEARINGS.get(
                    wind_dir.get(start, {}).get("WindDirection")
                ),
                "uv_index": to_number(uv.get(start, {}).get("UVIndex")),
            }
        )
    return periods


def _max(values):
    values = [v for v in values if v is not None]
    return max(values) if values else None


def _min(values):
    values = [v for v in values if v is not None]
    return min(values) if values else None


def merge_daily(periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine each local date's day and night periods into one day."""
    days: dict[Any, list[dict[str, Any]]] = {}
    for period in periods:
        days.setdefault(period["datetime"].astimezone(CWA_TZ).date(), []).append(period)

    daily = []
    for date, items in days.items():
        day = next((p for p in items if p["is_daytime"]), None)
        lead = day or items[0]
        daily.append(
            {
                "datetime": datetime(date.year, date.month, date.day, tzinfo=CWA_TZ),
                "weather_code": lead["weather_code"],
                "weather": lead["weather"],
                "temperature": _max(p["temperature"] for p in items),
                "templow": _min(p["templow"] for p in items),
                "apparent_temperature": _max(p["apparent_temperature"] for p in items),
                "precipitation_probability": _max(
                    p["precipitation_probability"] for p in items
                ),
                "humidity": lead["humidity"],
                "dew_point": lead["dew_point"],
                "wind_speed": lead["wind_speed"],
                "wind_bearing": lead["wind_bearing"],
                "uv_index": day["uv_index"] if day else None,
            }
        )
    return daily


def current_entry(entries: list[dict[str, Any]], now: datetime, span: timedelta) -> dict:
    """The forecast entry covering ``now``.

    Entries start at ``datetime`` and last until ``end`` when given, otherwise
    until the next entry (at most ``span``).
    """
    for index, entry in enumerate(entries):
        end = entry.get("end")
        if end is None:
            following = entries[index + 1]["datetime"] if index + 1 < len(entries) else None
            end = min(following, entry["datetime"] + span) if following else entry["datetime"] + span
        if entry["datetime"] <= now < end:
            return entry
    return {}
