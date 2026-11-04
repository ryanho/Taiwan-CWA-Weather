"""Parsing of CWA responses."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from custom_components.taiwan_cwa.api import (
    CWA_TZ,
    FORECAST_WIND_BEARINGS,
    code_condition,
    current_entry,
    merge_daily,
    observed_wind_bearing,
    parse_cwa_time,
    parse_hourly,
    parse_observation,
    parse_periods,
    text_condition,
    to_number,
)
from custom_components.taiwan_cwa.const import WEATHER_CODES

from .conftest import load_fixture


def _forecast_location(dataid: str) -> dict:
    groups = load_fixture("forecast_zhongli.json")["records"]["Locations"]
    return next(g for g in groups if g["Dataid"] == dataid)["Location"][0]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("150.0", 150.0), ("360.0", 360.0), ("0.0", None), ("990.0", None), ("-99", None), (None, None)],
)
def test_observed_wind_bearing(raw, expected) -> None:
    # 360 is north; 0 is calm, 990 variable, -99 missing.
    assert observed_wind_bearing(raw) == expected


def test_missing_value_sentinels() -> None:
    assert to_number("-99") is None
    assert to_number("-999.0") is None
    assert to_number("X") is None
    assert to_number("0.0") == 0.0


def test_naive_times_are_taiwan_local() -> None:
    assert parse_cwa_time("2026-11-04 12:00:00").isoformat() == "2026-11-04T12:00:00+08:00"
    assert parse_cwa_time("2026-11-04T12:00:00+08:00").utcoffset() == timedelta(hours=8)


@pytest.mark.parametrize(
    ("code", "daytime", "expected"),
    [
        ("01", True, "sunny"),
        ("01", False, "clear-night"),
        ("02", True, "partlycloudy"),
        ("04", True, "partlycloudy"),
        ("07", True, "cloudy"),
        ("08", True, "rainy"),
        ("15", True, "lightning-rainy"),
        ("20", True, "rainy"),
        ("22", True, "lightning-rainy"),
        ("23", True, "snowy-rainy"),
        ("27", True, "fog"),
        ("31", True, "rainy"),
        ("36", True, "lightning-rainy"),
        ("42", True, "snowy"),
        ("40", True, None),
        (None, True, None),
    ],
)
def test_code_condition(code, daytime, expected) -> None:
    assert code_condition(code, daytime) == expected


def test_every_code_has_a_condition() -> None:
    assert all(code_condition(code) for code in WEATHER_CODES)


@pytest.mark.parametrize(
    ("text", "daytime", "expected"),
    [
        ("晴", True, "sunny"),
        ("晴", False, "clear-night"),
        ("多雲", True, "partlycloudy"),
        ("陰", True, "cloudy"),
        ("多雲有雨", True, "rainy"),
        ("陰有雷", True, "lightning-rainy"),
        (None, True, None),
    ],
)
def test_text_condition(text, daytime, expected) -> None:
    assert text_condition(text, daytime) == expected


def test_parse_observation() -> None:
    station = next(
        s for s in load_fixture("observation.json")["records"]["Station"] if s["StationId"] == "466920"
    )
    obs = parse_observation(station)
    assert obs["station_name"] == "臺北"
    assert obs["temperature"] is not None
    assert obs["observation_time"].utcoffset() == timedelta(hours=8)
    assert obs["wind_gust"] is None or obs["wind_gust"] >= 0


def test_parse_hourly() -> None:
    points = parse_hourly(_forecast_location("D0047-005"))
    assert len(points) > 24
    times = [p["datetime"] for p in points]
    assert times == sorted(times)
    # Hourly near-term, 3-hourly later.
    assert times[1] - times[0] == timedelta(hours=1)
    assert times[-1] - times[-2] == timedelta(hours=3)
    assert all(p["weather_code"] in WEATHER_CODES for p in points)
    assert all(p["temperature"] is not None for p in points)
    assert {p["wind_bearing"] for p in points} <= set(FORECAST_WIND_BEARINGS.values())
    assert all(p["precipitation_probability"] is not None for p in points)


def test_parse_periods_and_daily() -> None:
    periods = parse_periods(_forecast_location("D0047-007"))
    assert len(periods) == 14
    assert periods[0]["datetime"].isoformat() == "2026-11-04T12:00:00+08:00"
    assert [p["is_daytime"] for p in periods[:4]] == [True, False, True, False]
    # UV is only forecast for daytime periods.
    assert all(p["uv_index"] is None for p in periods if not p["is_daytime"])
    assert all(p["uv_index"] is not None for p in periods if p["is_daytime"])
    assert all(p["templow"] <= p["temperature"] for p in periods)

    daily = merge_daily(periods)
    assert len(daily) in (7, 8)
    first = daily[0]
    assert first["datetime"] == datetime(2026, 11, 4, tzinfo=CWA_TZ)
    today = [p for p in periods if p["datetime"].date() == first["datetime"].date()]
    assert first["temperature"] == max(p["temperature"] for p in today)
    assert first["templow"] == min(p["templow"] for p in today)
    assert first["weather_code"] == today[0]["weather_code"]


def test_current_entry() -> None:
    start = datetime(2026, 11, 4, 12, tzinfo=CWA_TZ)
    entries = [{"datetime": start + timedelta(hours=h), "v": h} for h in (0, 1, 4)]
    span = timedelta(hours=3)
    assert current_entry(entries, start + timedelta(minutes=30), span)["v"] == 0
    assert current_entry(entries, start + timedelta(hours=2), span)["v"] == 1
    assert current_entry(entries, start + timedelta(hours=8), span) == {}
    assert current_entry(entries, start - timedelta(hours=1), span) == {}
