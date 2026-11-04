"""Shared entity helpers for the Taiwan CWA Weather integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import CONF_ZONE, DOMAIN


def service_device_info(entry: ConfigEntry) -> DeviceInfo:
    """One service per configured zone, like other weather integrations."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="中央氣象署 Central Weather Administration",
        model="O-A0001-001 / F-D0047",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://www.cwa.gov.tw/",
    )


def object_id_prefix(entry: ConfigEntry) -> str:
    """ASCII entity id prefix from the zone (zone.home -> taiwan_cwa_home).

    Zone names are often Chinese, which HA would transliterate into pinyin.
    """
    return f"taiwan_cwa_{entry.data[CONF_ZONE].removeprefix('zone.')}"
