"""Config flow for Taiwan CWA Weather integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import zone_coordinates, zone_elevation
from .api import CWAApiError, CWAAuthError, async_fetch
from .const import (
    CONF_API_KEY,
    CONF_LOCATION,
    CONF_RELOCATE,
    CONF_STATION,
    CONF_ZONE,
    DOMAIN,
    OBSERVATION_DATASET,
    STATION_AUTO,
)
from .location import OutsideTaiwanError, async_resolve_location


class CWAWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> CWAWeatherOptionsFlow:
        return CWAWeatherOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            zone = user_input[CONF_ZONE]
            await self.async_set_unique_id(zone)
            self._abort_if_unique_id_configured()

            coords = zone_coordinates(self.hass, zone)
            if coords is None:
                errors[CONF_ZONE] = "zone_not_found"
            else:
                try:
                    location = await async_resolve_location(
                        self.hass,
                        user_input[CONF_API_KEY],
                        *coords,
                        zone_elevation(self.hass, zone),
                    )
                except CWAAuthError:
                    errors[CONF_API_KEY] = "invalid_auth"
                except CWAApiError:
                    errors["base"] = "cannot_connect"
                except OutsideTaiwanError:
                    errors[CONF_ZONE] = "outside_taiwan"
                else:
                    state = self.hass.states.get(zone)
                    return self.async_create_entry(
                        title=state.name if state else zone,
                        data={
                            CONF_API_KEY: user_input[CONF_API_KEY],
                            CONF_ZONE: zone,
                            CONF_LOCATION: location,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_ZONE, default="zone.home"): EntitySelector(
                    EntitySelectorConfig(domain=ZONE_DOMAIN)
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            description_placeholders={
                "opendata_host": "opendata.cwa.gov.tw",
                "opendata_url": "https://opendata.cwa.gov.tw/",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await async_fetch(
                    self.hass,
                    user_input[CONF_API_KEY],
                    OBSERVATION_DATASET,
                    {"StationId": "466920", "WeatherElement": "AirTemperature"},
                )
            except CWAAuthError:
                errors[CONF_API_KEY] = "invalid_auth"
            except CWAApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )


def _station_label(station: dict[str, Any]) -> str:
    altitude = station.get("altitude")
    altitude_text = f"{altitude:.0f} m" if altitude is not None else "?"
    return (
        f"{station['name']} ({station['id']}) · {station['county']}{station['town']}"
        f" · {station['distance']:.1f} km · {altitude_text}"
    )


class CWAWeatherOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.config_entry
        errors: dict[str, str] = {}

        if user_input is not None:
            station = user_input[CONF_STATION]
            if user_input.get(CONF_RELOCATE):
                coords = zone_coordinates(self.hass, entry.data[CONF_ZONE])
                try:
                    if coords is None:
                        raise OutsideTaiwanError
                    location = await async_resolve_location(
                        self.hass,
                        entry.data[CONF_API_KEY],
                        *coords,
                        zone_elevation(self.hass, entry.data[CONF_ZONE]),
                    )
                except CWAApiError:
                    errors["base"] = "cannot_connect"
                except OutsideTaiwanError:
                    errors["base"] = "outside_taiwan"
                else:
                    self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, CONF_LOCATION: location}
                    )
                    # A manual pick may no longer be nearby.
                    if station not in {s["id"] for s in location["nearby_stations"]}:
                        station = STATION_AUTO
            if not errors:
                return self.async_create_entry(data={CONF_STATION: station})

        location = entry.data[CONF_LOCATION]
        auto = location["stations"][0] if location["stations"] else None
        auto_text = "自動" if self.hass.config.language.startswith("zh") else "Auto"
        options = [
            SelectOptionDict(
                value=STATION_AUTO,
                label=f"{auto_text}: {_station_label(auto)}" if auto else auto_text,
            ),
            *(
                SelectOptionDict(value=s["id"], label=_station_label(s))
                for s in location["nearby_stations"]
            ),
        ]
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATION,
                    default=entry.options.get(CONF_STATION, STATION_AUTO),
                ): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                ),
                vol.Optional(CONF_RELOCATE, default=False): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "township": f"{location['county']}{location['township']}",
            },
        )
