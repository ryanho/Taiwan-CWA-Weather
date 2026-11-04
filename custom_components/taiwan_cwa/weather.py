"""Taiwan CWA weather entity: station observation plus township forecast."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.weather import (
    CoordinatorWeatherEntity,
    Forecast,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sun import is_up
from homeassistant.util import dt as dt_util

from . import CWAConfigEntry
from .api import (
    CWA_TZ,
    SKY_CONDITIONS,
    code_condition,
    current_entry,
    text_condition,
)
from .const import ATTRIBUTION, CONF_LOCATION, FORECAST_VALID
from .coordinator import CWAForecastCoordinator, CWAObservationCoordinator
from .entity import object_id_prefix, service_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CWAConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities([CWAWeather(data.observation, data.forecast, entry)])


def _forecast(item: dict[str, Any], daytime: bool | None = None) -> Forecast:
    forecast = Forecast(
        datetime=item["datetime"].isoformat(),
        condition=code_condition(
            item["weather_code"], item.get("is_daytime", True) if daytime is None else daytime
        ),
        native_temperature=item.get("temperature"),
        native_apparent_temperature=item.get("apparent_temperature"),
        native_dew_point=item.get("dew_point"),
        humidity=item.get("humidity"),
        precipitation_probability=item.get("precipitation_probability"),
        native_wind_speed=item.get("wind_speed"),
        wind_bearing=item.get("wind_bearing"),
    )
    if item.get("templow") is not None:
        forecast["native_templow"] = item["templow"]
    if item.get("uv_index") is not None:
        forecast["uv_index"] = item["uv_index"]
    if "is_daytime" in item:
        forecast["is_daytime"] = item["is_daytime"]
    return forecast


class CWAWeather(
    CoordinatorWeatherEntity[
        CWAObservationCoordinator,
        CWAForecastCoordinator,
        CWAForecastCoordinator,
        CWAForecastCoordinator,
    ]
):
    """Current conditions from the nearest station, forecast for the township."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY
        | WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    def __init__(
        self,
        observation: CWAObservationCoordinator,
        forecast: CWAForecastCoordinator,
        entry: CWAConfigEntry,
    ) -> None:
        super().__init__(
            observation,
            daily_coordinator=forecast,
            hourly_coordinator=forecast,
            twice_daily_coordinator=forecast,
            daily_forecast_valid=FORECAST_VALID,
            hourly_forecast_valid=FORECAST_VALID,
            twice_daily_forecast_valid=FORECAST_VALID,
        )
        self._forecast = forecast
        self._location = entry.data[CONF_LOCATION]
        self._attr_unique_id = entry.entry_id
        self.entity_id = f"weather.{object_id_prefix(entry)}"
        self._attr_device_info = service_device_info(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Current values fall back to the forecast, so refresh on forecast
        # updates too, not only while a forecast card is subscribed.
        self.async_on_remove(
            self._forecast.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def _obs(self) -> dict[str, Any]:
        if not self.coordinator.last_update_success:
            return {}
        return self.coordinator.data or {}

    @property
    def _forecast_data(self) -> dict[str, Any]:
        return self._forecast.data or {}

    @property
    def _now_hourly(self) -> dict[str, Any]:
        return current_entry(
            self._forecast_data.get("hourly", []), dt_util.now(), timedelta(hours=3)
        )

    @property
    def _now_period(self) -> dict[str, Any]:
        return current_entry(
            self._forecast_data.get("twice_daily", []), dt_util.now(), timedelta(hours=12)
        )

    @property
    def available(self) -> bool:
        return bool(self._obs) or (
            self._forecast.last_update_success and bool(self._forecast_data)
        )

    @property
    def attribution(self) -> str:
        parts = [ATTRIBUTION]
        if name := self._obs.get("station_name"):
            parts.append(f"觀測 Observation: {name}")
        parts.append(
            f"預報 Forecast: {self._location['county']}{self._location['township']}"
        )
        return "｜".join(parts)

    def _observed_or_forecast(self, key: str):
        value = self._obs.get(key)
        return value if value is not None else self._now_hourly.get(key)

    @property
    def condition(self) -> str | None:
        daytime = is_up(self.hass)
        forecast = code_condition(self._now_hourly.get("weather_code"), daytime)
        # Stations report sky cover only and almost never rain, so a
        # precipitation forecast for the current 3 hours takes over.
        if forecast is not None and forecast not in SKY_CONDITIONS:
            return forecast
        return text_condition(self._obs.get("weather"), daytime) or forecast

    @property
    def native_temperature(self) -> float | None:
        return self._observed_or_forecast("temperature")

    @property
    def humidity(self) -> float | None:
        return self._observed_or_forecast("humidity")

    @property
    def native_pressure(self) -> float | None:
        return self._obs.get("pressure")

    @property
    def native_wind_speed(self) -> float | None:
        return self._observed_or_forecast("wind_speed")

    @property
    def wind_bearing(self) -> float | None:
        if self._obs:
            # A calm or variable observed wind has no bearing; don't replace it.
            return self._obs.get("wind_bearing")
        return self._now_hourly.get("wind_bearing")

    @property
    def native_wind_gust_speed(self) -> float | None:
        return self._obs.get("wind_gust")

    @property
    def native_apparent_temperature(self) -> float | None:
        return self._now_hourly.get("apparent_temperature")

    @property
    def native_dew_point(self) -> float | None:
        return self._now_hourly.get("dew_point")

    @property
    def uv_index(self) -> float | None:
        period = self._now_period
        return period.get("uv_index") if period.get("is_daytime") else None

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        return [_forecast(d, daytime=True) for d in self._forecast_data.get("daily", [])]

    @callback
    def _async_forecast_twice_daily(self) -> list[Forecast] | None:
        return [_forecast(p) for p in self._forecast_data.get("twice_daily", [])]

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        return [
            # Clear nights show a moon; approximate daylight as 06-18 local.
            _forecast(point, daytime=6 <= point["datetime"].astimezone(CWA_TZ).hour < 18)
            for point in self._forecast_data.get("hourly", [])
        ]
