"""Taiwan CWA Weather sensors."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CITY_SLUGS,
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
)


@dataclass(frozen=True)
class ObservationSensorSpec:
    key: str
    name: str
    icon: str | None = None
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None


OBSERVATION_SENSORS = (
    ObservationSensorSpec(OBS_WEATHER, "Current Weather", icon="mdi:weather-partly-cloudy"),
    ObservationSensorSpec(
        OBS_TEMPERATURE,
        "Temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ObservationSensorSpec(
        OBS_HUMIDITY,
        "Humidity",
        unit=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ObservationSensorSpec(
        OBS_PRESSURE,
        "Pressure",
        unit=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ObservationSensorSpec(
        OBS_WIND_SPEED,
        "Wind Speed",
        unit=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ObservationSensorSpec(
        OBS_WIND_DIRECTION, "Wind Direction", icon="mdi:compass-outline", unit=DEGREE
    ),
    # Accumulated since local midnight, so it resets daily.
    ObservationSensorSpec(
        OBS_PRECIPITATION,
        "Precipitation Today",
        unit=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ObservationSensorSpec(
        OBS_TODAY_HIGH,
        "Today High",
        icon="mdi:thermometer-chevron-up",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    ObservationSensorSpec(
        OBS_TODAY_LOW,
        "Today Low",
        icon="mdi:thermometer-chevron-down",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict = data["forecast"]
    observation = data["observation"]
    entities = []
    for city, coordinator in coordinators.items():
        slug = CITY_SLUGS.get(city, city)
        entities.extend(
            [
                CWAWeatherSensor(coordinator, entry, city, slug),
                CWARainProbSensor(coordinator, entry, city, slug),
                CWAMinTempSensor(coordinator, entry, city, slug),
                CWAMaxTempSensor(coordinator, entry, city, slug),
            ]
        )
        entities.extend(
            CWAObservationSensor(observation, entry, city, slug, spec)
            for spec in OBSERVATION_SENSORS
        )
    async_add_entities(entities)


class CWABaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, city: str, slug: str, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._city = city
        self._slug = slug
        self._entry = entry

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_{self._slug}")},
            "name": f"Taiwan CWA Weather {self._city}",
            "manufacturer": "Central Weather Administration",
            "model": "F-C0032-001 / O-A0001-001",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def _data(self):
        return self.coordinator.data or {}


class CWAWeatherSensor(CWABaseSensor):
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, coordinator, entry, city, slug):
        super().__init__(coordinator, entry, city, slug, "weather")
        self._attr_unique_id = f"{entry.entry_id}_{slug}_weather"
        self._attr_name = f"Taiwan CWA {city} Weather"
        self.entity_id = f"sensor.taiwan_cwa_{slug}_weather"

    @property
    def state(self):
        return self._data.get("weather")


class CWARainProbSensor(CWABaseSensor):
    _attr_icon = "mdi:weather-rainy"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, city, slug):
        super().__init__(coordinator, entry, city, slug, "rain_prob")
        self._attr_unique_id = f"{entry.entry_id}_{slug}_rain_prob"
        self._attr_name = f"Taiwan CWA {city} Rain Probability"
        self.entity_id = f"sensor.taiwan_cwa_{slug}_rain_prob"

    @property
    def native_value(self):
        val = self._data.get("rain_prob")
        try:
            return int(val)
        except (TypeError, ValueError):
            return None


class CWAMinTempSensor(CWABaseSensor):
    _attr_icon = "mdi:thermometer-low"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, city, slug):
        super().__init__(coordinator, entry, city, slug, "min_temp")
        self._attr_unique_id = f"{entry.entry_id}_{slug}_min_temp"
        self._attr_name = f"Taiwan CWA {city} Min Temperature"
        self.entity_id = f"sensor.taiwan_cwa_{slug}_min_temp"

    @property
    def native_value(self):
        val = self._data.get("min_temp")
        try:
            return float(val)
        except (TypeError, ValueError):
            return None


class CWAMaxTempSensor(CWABaseSensor):
    _attr_icon = "mdi:thermometer-high"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, city, slug):
        super().__init__(coordinator, entry, city, slug, "max_temp")
        self._attr_unique_id = f"{entry.entry_id}_{slug}_max_temp"
        self._attr_name = f"Taiwan CWA {city} Max Temperature"
        self.entity_id = f"sensor.taiwan_cwa_{slug}_max_temp"

    @property
    def native_value(self):
        val = self._data.get("max_temp")
        try:
            return float(val)
        except (TypeError, ValueError):
            return None


class CWAObservationSensor(CWABaseSensor):
    """A current-conditions value from the city's O-A0001-001 station."""

    def __init__(self, coordinator, entry, city, slug, spec: ObservationSensorSpec):
        super().__init__(coordinator, entry, city, slug, spec.key)
        self._attr_unique_id = f"{entry.entry_id}_{slug}_{spec.key}"
        self._attr_name = f"Taiwan CWA {city} {spec.name}"
        self.entity_id = f"sensor.taiwan_cwa_{slug}_{spec.key}"
        self._attr_icon = spec.icon
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        self._attr_state_class = spec.state_class

    @property
    def _station(self) -> dict | None:
        return self._data.get(self._city)

    @property
    def available(self) -> bool:
        return super().available and self._station is not None

    @property
    def native_value(self):
        return (self._station or {}).get(self._key)

    @property
    def extra_state_attributes(self):
        station = self._station or {}
        return {
            "station_id": station.get("station_id"),
            "station_name": station.get("station_name"),
            "observation_time": station.get("observation_time"),
        }
