"""Every user-facing string exists in both English and Traditional Chinese."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.taiwan_cwa.const import WEATHER_CODES
from custom_components.taiwan_cwa.sensor import FORECAST_SENSORS, OBSERVATION_SENSORS

TRANSLATIONS = Path(__file__).parents[1] / "custom_components" / "taiwan_cwa" / "translations"


def _load(language: str) -> dict:
    return json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))


def _keys(tree: dict, prefix: str = "") -> set[str]:
    keys = set()
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else key
        keys |= _keys(value, path) if isinstance(value, dict) else {path}
    return keys


def test_only_languages_home_assistant_loads() -> None:
    # Home Assistant uses zh-Hant for Traditional Chinese; zh-TW is never read.
    assert sorted(p.name for p in TRANSLATIONS.iterdir()) == ["en.json", "zh-Hant.json"]


def test_languages_have_the_same_keys() -> None:
    assert _keys(_load("en")) == _keys(_load("zh-Hant"))


@pytest.mark.parametrize("language", ["en", "zh-Hant"])
def test_sensor_names_and_weather_codes(language: str) -> None:
    sensors = _load(language)["entity"]["sensor"]
    for description in (*OBSERVATION_SENSORS, *FORECAST_SENSORS):
        assert sensors[description.translation_key]["name"]
    assert sensors["station"]["name"]
    assert sorted(sensors["weather_code"]["state"]) == WEATHER_CODES
