"""Taiwan CWA Weather sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UV_INDEX,
    EntityCategory,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import CWAConfigEntry
from .api import current_entry
from .const import CONF_LOCATION, WEATHER_CODES
from .entity import object_id_prefix, service_device_info


@dataclass(frozen=True, kw_only=True)
class CWASensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


def _now(forecast: dict[str, Any], key: str, span_hours: int) -> dict[str, Any]:
    return current_entry(forecast.get(key, []), dt_util.now(), timedelta(hours=span_hours))


# Values from the observation station.
OBSERVATION_SENSORS = (
    CWASensorDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda obs: obs.get("temperature"),
    ),
    CWASensorDescription(
        key="humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda obs: obs.get("humidity"),
    ),
    # Accumulated since local midnight, so it resets daily.
    CWASensorDescription(
        key="precipitation",
        translation_key="precipitation",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda obs: obs.get("precipitation"),
    ),
    CWASensorDescription(
        key="pressure",
        translation_key="pressure",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda obs: obs.get("pressure"),
    ),
    CWASensorDescription(
        key="wind_speed",
        translation_key="wind_speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda obs: obs.get("wind_speed"),
    ),
    CWASensorDescription(
        key="wind_direction",
        translation_key="wind_direction",
        icon="mdi:compass-outline",
        native_unit_of_measurement=DEGREE,
        entity_registry_enabled_default=False,
        value_fn=lambda obs: obs.get("wind_bearing"),
    ),
    CWASensorDescription(
        key="today_high",
        translation_key="today_high",
        icon="mdi:thermometer-chevron-up",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        value_fn=lambda obs: obs.get("today_high"),
    ),
    CWASensorDescription(
        key="today_low",
        translation_key="today_low",
        icon="mdi:thermometer-chevron-down",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        value_fn=lambda obs: obs.get("today_low"),
    ),
)

# Values for the current forecast period.
FORECAST_SENSORS = (
    CWASensorDescription(
        key="apparent_temperature",
        translation_key="apparent_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda fc: _now(fc, "hourly", 3).get("apparent_temperature"),
    ),
    CWASensorDescription(
        key="uv_index",
        translation_key="uv_index",
        icon="mdi:sun-wireless",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda fc: (
            period.get("uv_index")
            if (period := _now(fc, "twice_daily", 12)).get("is_daytime")
            else None
        ),
    ),
    CWASensorDescription(
        key="rain_probability",
        translation_key="rain_probability",
        icon="mdi:weather-rainy",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda fc: _now(fc, "hourly", 3).get("precipitation_probability"),
    ),
    CWASensorDescription(
        key="weather_code",
        translation_key="weather_code",
        icon="mdi:weather-partly-cloudy",
        device_class=SensorDeviceClass.ENUM,
        options=WEATHER_CODES,
        entity_registry_enabled_default=False,
        value_fn=lambda fc: (
            code if (code := _now(fc, "hourly", 3).get("weather_code")) in WEATHER_CODES else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CWAConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        [
            *(CWASensor(data.observation, entry, d) for d in OBSERVATION_SENSORS),
            *(CWASensor(data.forecast, entry, d) for d in FORECAST_SENSORS),
            CWAStationSensor(data.observation, entry),
        ]
    )


class CWASensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    entity_description: CWASensorDescription

    def __init__(self, coordinator, entry: CWAConfigEntry, description: CWASensorDescription):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self.entity_id = f"sensor.{object_id_prefix(entry)}_{description.key}"
        self._attr_device_info = service_device_info(entry)

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "weather_code":
            # The exact CWA wording (Chinese only), e.g. 多雲午後短暫雷陣雨.
            return {"description": _now(self.coordinator.data or {}, "hourly", 3).get("weather")}
        return None


class CWAStationSensor(CoordinatorEntity, SensorEntity):
    """Which station and township the data comes from."""

    _attr_has_entity_name = True
    _attr_translation_key = "station"
    _attr_icon = "mdi:map-marker-radius"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: CWAConfigEntry) -> None:
        super().__init__(coordinator)
        self._location = entry.data[CONF_LOCATION]
        self._attr_unique_id = f"{entry.entry_id}_station"
        self.entity_id = f"sensor.{object_id_prefix(entry)}_station"
        self._attr_device_info = service_device_info(entry)

    @property
    def native_value(self) -> str | None:
        return (self.coordinator.data or {}).get("station_name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        obs = self.coordinator.data or {}
        station = next(
            (
                s
                for s in self._location["nearby_stations"] + self._location["stations"]
                if s["id"] == obs.get("station_id")
            ),
            {},
        )
        observed = obs.get("observation_time")
        return {
            "station_id": obs.get("station_id"),
            "altitude": station.get("altitude"),
            "distance_km": station.get("distance"),
            "observation_time": observed.isoformat() if observed else None,
            "is_fallback": obs.get("is_fallback"),
            "forecast_location": f"{self._location['county']}{self._location['township']}",
            "forecast_geocode": self._location["geocode"],
        }
